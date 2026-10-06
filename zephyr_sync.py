#!/usr/bin/env python3
"""
zephyr_sync.py - send test cases and Playwright results to SmartBear Zephyr (formerly Zephyr Scale)

Commands
  cases    Create Zephyr test cases (with steps) from the JSON, linked to the Jira Story
  results  Create a Zephyr test cycle from a Playwright JSON report, with Pass/Fail per test

Examples
  python zephyr_sync.py cases out/login.json --dry-run
  python zephyr_sync.py cases out/login.json
  python zephyr_sync.py results reports/results.json out/login.json

Needs in .env (besides the Jira settings):
  ZEPHYR_API_TOKEN=...      (Jira -> your profile picture -> Zephyr API keys)
  ZEPHYR_BASE_URL=https://api.zephyrscale.smartbear.com/v2   (EU sites: https://eu.api.zephyrscale.smartbear.com/v2)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if not val:
        sys.exit(f"Missing environment variable: {name} (add it to .env)")
    return val


PRIORITY_MAP = {"high": "High", "medium": "Normal", "normal": "Normal", "low": "Low"}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Zephyr:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.project = env("JIRA_PROJECT_KEY")
        self.base = env("ZEPHYR_BASE_URL", "https://api.zephyrscale.smartbear.com/v2").rstrip("/")
        self._n = 0
        if not dry_run:
            self.s = requests.Session()
            self.s.headers.update({"Authorization": f"Bearer {env('ZEPHYR_API_TOKEN')}",
                                   "Content-Type": "application/json"})

    def post(self, path: str, body: dict, label: str = "") -> dict:
        if self.dry_run:
            self._n += 1
            print(f"[dry-run] POST {path}  {label}")
            return {"key": f"{self.project}-DRY{self._n}", "id": self._n}
        r = self.s.post(self.base + path, json=body, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Zephyr POST {path} -> {r.status_code}: {r.text}")
        return r.json() if r.text else {}


def jira_issue_id(issue_key: str) -> int | None:
    """Zephyr links to Jira issues by their numeric id, not the key."""
    base = env("JIRA_BASE_URL").rstrip("/")
    auth = HTTPBasicAuth(env("JIRA_EMAIL"), env("JIRA_API_TOKEN"))
    r = requests.get(f"{base}/rest/api/3/issue/{issue_key}", params={"fields": "summary"},
                     auth=auth, timeout=30)
    if not r.ok:
        print(f"Warning: could not look up {issue_key} in Jira ({r.status_code}); skipping link")
        return None
    return int(r.json()["id"])


# ---------------------------------------------------------------------------
def cmd_cases(args) -> None:
    path = Path(args.cases)
    data = json.loads(path.read_text(encoding="utf-8"))
    z = Zephyr(dry_run=args.dry_run)
    story_key = data.get("story", {}).get("jira_key")
    story_id = jira_issue_id(story_key) if story_key and not args.dry_run else None

    created = 0
    for tc in data["test_cases"]:
        if tc.get("zephyr_key"):
            continue
        body = {
            "projectKey": z.project,
            "name": f"[{tc['id']}] {tc['title']}"[:255],
            "objective": tc.get("expected_result", ""),
            "precondition": tc.get("preconditions", ""),
            "labels": ["ai-generated", str(tc.get("type", "functional")).lower()],
        }
        prio = PRIORITY_MAP.get(str(tc.get("priority", "")).lower())
        if prio:
            body["priorityName"] = prio
        try:
            res = z.post("/testcases", body, body["name"])
        except RuntimeError as e:
            if "priority" in str(e).lower():  # your Zephyr uses different priority names
                body.pop("priorityName", None)
                res = z.post("/testcases", body, body["name"])
            else:
                raise
        key = res["key"]

        steps = tc.get("steps", [])
        items = []
        for i, step in enumerate(steps):
            last = i == len(steps) - 1
            items.append({"inline": {
                "description": step,
                "testData": tc.get("test_data", "") if i == 0 else "",
                "expectedResult": tc.get("expected_result", "") if last else "",
            }})
        if items:
            z.post(f"/testcases/{key}/teststeps", {"mode": "OVERWRITE", "items": items},
                   f"{len(items)} steps")
        if story_id:
            z.post(f"/testcases/{key}/links/issues", {"issueId": story_id}, f"link to {story_key}")

        if not args.dry_run:
            tc["zephyr_key"] = key
            print(f"Created test case {key}: {body['name']}")
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        created += 1

    print(f"{created} test case(s) {'would be ' if args.dry_run else ''}created in Zephyr.")


# ---------------------------------------------------------------------------
def iter_tests(report: dict):
    """Yield every test in a Playwright JSON report with its final status."""
    def walk(suite):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                results = test.get("results") or [{}]
                last = results[-1]
                err = last.get("error") or (last.get("errors") or [{}])[0]
                yield {
                    "title": spec["title"],
                    "status": test.get("status"),  # expected | unexpected | flaky | skipped
                    "project": test.get("projectName", ""),
                    "duration_ms": sum(r.get("duration", 0) for r in results),
                    "error": ANSI.sub("", (err or {}).get("message", "") or "")[:2000],
                }
        for child in suite.get("suites", []):
            yield from walk(child)

    for s in report.get("suites", []):
        yield from walk(s)


STATUS_MAP = {"expected": "Pass", "flaky": "Pass", "unexpected": "Fail", "skipped": "Not Executed"}


def cmd_results(args) -> None:
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    keys = {tc["id"]: tc.get("zephyr_key") for tc in data["test_cases"]}
    if not any(keys.values()) and not args.dry_run:
        sys.exit("No zephyr_key values in the JSON yet - run 'python zephyr_sync.py cases ...' first")
    z = Zephyr(dry_run=args.dry_run)

    tests = list(iter_tests(report))
    name = args.name or f"Playwright run {datetime.now():%Y-%m-%d %H:%M}"
    cycle = z.post("/testcycles", {
        "projectKey": z.project,
        "name": name,
        "description": f"Automated Playwright results ({len(tests)} tests)",
    }, name)
    cycle_key = cycle["key"]
    if not args.dry_run:
        print(f"Created test cycle {cycle_key}: {name}")

    counts = {"Pass": 0, "Fail": 0, "Not Executed": 0, "skipped (no TC id)": 0}
    for t in tests:
        m = re.match(r"(TC-\d+)", t["title"])
        tc_key = keys.get(m.group(1)) if m else None
        if not tc_key and not args.dry_run:
            counts["skipped (no TC id)"] += 1
            print(f"Skipping '{t['title']}' - no matching Zephyr test case")
            continue
        status = STATUS_MAP.get(t["status"], "Not Executed")
        comment = f"Browser: {t['project'] or 'default'}"
        if t["status"] == "flaky":
            comment += " - passed on retry (flaky)"
        if t["error"]:
            comment += f"<br><br>Error:<br>{t['error'][:1500]}"
        z.post("/testexecutions", {
            "projectKey": z.project,
            "testCaseKey": tc_key or "DRY",
            "testCycleKey": cycle_key,
            "statusName": status,
            "executionTime": int(t["duration_ms"]),
            "comment": comment,
        }, f"{t['title']} -> {status}")
        counts[status] += 1

    print("Summary:", ", ".join(f"{k}: {v}" for k, v in counts.items() if v))
    if not args.dry_run:
        print(f"Open Zephyr -> Test Cycles -> {cycle_key} to see the results.")


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cases", help="create Zephyr test cases from the JSON")
    c.add_argument("cases", help="e.g. out/login.json")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=cmd_cases)

    r = sub.add_parser("results", help="push a Playwright JSON report as a Zephyr test cycle")
    r.add_argument("report", help="e.g. reports/results.json")
    r.add_argument("cases", help="e.g. out/login.json (must contain zephyr_key values)")
    r.add_argument("--name", help="test cycle name (default: 'Playwright run <date time>')")
    r.add_argument("--dry-run", action="store_true")
    r.set_defaults(func=cmd_results)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()