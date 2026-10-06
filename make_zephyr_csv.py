import csv, json

d = json.load(open("out/login.json", encoding="utf-8"))
prio = {"high": "High", "medium": "Normal", "low": "Low"}
with open("out/zephyr_import.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["Name", "Objective", "Precondition", "Priority", "Status", "Labels",
                "Coverage (Issues)", "Step", "Test Data", "Expected Result"])
    for tc in d["test_cases"]:
        steps = tc["steps"]
        for i, s in enumerate(steps):
            first, last = i == 0, i == len(steps) - 1
            w.writerow([
                f"[{tc['id']}] {tc['title']}" if first else "",
                tc["expected_result"] if first else "",
                tc["preconditions"] if first else "",
                prio.get(tc["priority"].lower(), "Normal") if first else "",
                "Draft" if first else "",
                f"ai-generated,{tc['type']}" if first else "",
                d["story"].get("jira_key", "") if first else "",
                s,
                tc["test_data"] if first else "",
                tc["expected_result"] if last else "",
            ])
print("Saved out/zephyr_import.csv")