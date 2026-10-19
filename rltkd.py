import requests, pandas as pd, time

SERVICE_KEY = "61ad00ae3a9949ca67de4e881b4077fe5170e96945ec250b9e3482e2e3259a9e"
URL = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"

# 반기 단위로 쪼개기 (한 번에 366일 요청하면 자주 끊김)
periods = []
for y in range(2020, 2026):
    periods += [(f"{y}0101", f"{y}0630"), (f"{y}0701", f"{y}1231")]
periods += [("20260101", "20260630")]

frames = []
for start, end in periods:
    for attempt in range(4):
        try:
            p = {
                "serviceKey": SERVICE_KEY,
                "dataType": "JSON",
                "dataCd": "ASOS",
                "dateCd": "DAY",
                "startDt": start,
                "endDt": end,
                "stnIds": "108",
                "numOfRows": "200",
                "pageNo": "1",
            }
            items = requests.get(URL, params=p, timeout=90).json()["response"]["body"][
                "items"
            ]["item"]
            frames.append(pd.DataFrame(items))
            print(f"{start}~{end}  {len(items)}일")
            break
        except Exception as e:
            if attempt == 3:
                print(f"{start}~{end}  실패 ({type(e).__name__})")
            time.sleep(3)
    time.sleep(1)

df = pd.concat(frames).drop_duplicates("tm")
df["tm"] = pd.to_datetime(df["tm"])
df["avgTa"] = pd.to_numeric(df["avgTa"], errors="coerce")
df["HDD"] = (18.0 - df["avgTa"]).clip(lower=0)
df["CDD"] = (df["avgTa"] - 18.0).clip(lower=0)

g = df.set_index("tm")[["HDD", "CDD"]].resample("ME")
monthly = g.sum().round(1)
monthly["days"] = g.size()  # 그 달에 실제로 받은 일수

# 일수가 25일 미만인 달은 불완전 → 제거
bad = monthly[monthly["days"] < 25]
if len(bad):
    print("\n[제외된 불완전 월]")
    print(bad)
monthly = monthly[monthly["days"] >= 25].drop(columns="days")

monthly.index = monthly.index.strftime("%Y%m")
monthly.index.name = "ym"
monthly.to_csv("weather.csv", encoding="utf-8-sig")

print(f"\n총 {len(monthly)}개월 저장")
print(monthly.head(14))
