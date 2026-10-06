import os
import requests
from dotenv import load_dotenv

load_dotenv()
base = os.getenv("JIRA_BASE_URL").rstrip("/")
auth = (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))
key = os.getenv("JIRA_PROJECT_KEY")

me = requests.get(base + "/rest/api/3/myself", auth=auth)
print("Login:", me.status_code, me.json().get("displayName") if me.ok else me.text[:200])

print("\nYour projects:")
projects = requests.get(base + "/rest/api/3/project/search", auth=auth).json().get("values", [])
for p in projects:
    print("  ", p["key"], "-", p["name"])
if not projects:
    print("   No projects found - create one in Jira first")

proj = requests.get(base + "/rest/api/3/project/" + str(key), auth=auth)
print("\nProject in .env:", key, "->", proj.status_code)
if proj.ok:
    print("Issue types:", [t["name"] for t in proj.json().get("issueTypes", [])])