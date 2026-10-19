import requests
import time
import pandas as pd

SERVICE_KEY = "61ad00ae3a9949ca67de4e881b4077fe5170e96945ec250b9e3482e2e3259a9e"
URL = "http://apis.data.go.kr/1613000/BldEngyHubService/getBeGasUsgInfo"

base = {
    "serviceKey": SERVICE_KEY,
    "sigunguCd": "11680",
    "bjdongCd": "10100",
    "bun": "0761",
    "ji": "0026",
    "numOfRows": "10",
    "pageNo": "1",
    "_type": "json",
}

rows = []
for y in range(2020, 2027):
    for m in range(1, 13):
        ym = f"{y}{m:02d}"
        for attempt in range(3):
            try:
                r = requests.get(URL, params=dict(base, useYm=ym), timeout=60)
                d = r.json()
                if "response" in d:
                    items = d["response"]["body"]["items"]
                    if items:
                        q = items["item"][0]["useQty"]
                        rows.append({"ym": ym, "gas": q})
                        print(ym, q)
                break
            except Exception:
                time.sleep(2)
        time.sleep(0.3)

pd.DataFrame(rows).to_csv("gas.csv", index=False, encoding="utf-8-sig")
print(f"\n총 {len(rows)}개월 → gas.csv")
