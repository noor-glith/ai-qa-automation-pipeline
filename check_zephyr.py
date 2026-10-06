import os, json, base64, datetime
import requests
from dotenv import load_dotenv

load_dotenv()
t = os.getenv("ZEPHYR_API_TOKEN", "").strip()
print("Token length:", len(t))

# Read the token's public label (does not reveal the secret part)
try:
    payload = t.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    info = json.loads(base64.urlsafe_b64decode(payload))
    print("Made for app :", info.get("iss"))
    print("Jira site    :", (info.get("context") or {}).get("baseUrl"))
    if info.get("exp"):
        print("Expires      :", datetime.datetime.fromtimestamp(info["exp"]))
except Exception as e:
    print("Could not read token label:", e)

for name, url in [("Global", "https://api.zephyrscale.smartbear.com/v2"),
                  ("EU", "https://eu.api.zephyrscale.smartbear.com/v2")]:
    r = requests.get(url + "/projects", params={"maxResults": 1},
                     headers={"Authorization": "Bearer " + t}, timeout=30)
    print(f"{name} server:", r.status_code, r.text[:120])