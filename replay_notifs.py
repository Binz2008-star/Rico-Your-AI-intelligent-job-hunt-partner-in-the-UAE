import requests

key = ""
for line in open(".env.sandbox"):
    line = line.strip()
    if line.startswith("PADDLE_API_KEY="):
        key = line.split("=", 1)[1]
        break

all_notifs = []
url = "https://sandbox-api.paddle.com/notifications"
params = {"per_page": 50}
while url:
    r = requests.get(url, headers={"Authorization": "Bearer " + key}, params=params, timeout=10)
    if r.status_code != 200:
        break
    data = r.json()
    all_notifs.extend(data.get("data", []))
    has_more = data.get("meta", {}).get("has_more", False)
    next_cursor = data.get("meta", {}).get("next_cursor")
    if has_more and next_cursor:
        params = {"per_page": 50, "after": next_cursor}
    else:
        break

print(f"Total notifications: {len(all_notifs)}")

replayed = 0
for n in all_notifs:
    nstatus = n.get("status", "")
    if nstatus == "failed":
        nid = n.get("id", "")
        ntype = n.get("type", "")
        sid = nid[:6] + "..." + nid[-4:]
        rr = requests.post(
            "https://sandbox-api.paddle.com/notifications/" + nid + "/replay",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            timeout=10,
        )
        if rr.status_code == 202:
            replayed += 1
            print(f"Replayed {sid} type={ntype} -> 202")
        else:
            err = rr.json().get("error", {})
            print(f"Skipped {sid} type={ntype} -> {rr.status_code} {err.get('detail', '')[:100]}")

print(f"\nTotal replayed: {replayed}")
