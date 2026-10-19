import requests

SERVICE_KEY = "61ad00ae3a9949ca67de4e881b4077fe5170e96945ec250b9e3482e2e3259a9e"
URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"

params = {
    "serviceKey": SERVICE_KEY,
    "sigunguCd": "11680",
    "bjdongCd": "10100",
    "bun": "0761",
    "ji": "0026",
    "numOfRows": "5",
    "pageNo": "1",
    "_type": "json",  # JSON으로 받으면 다루기 쉬움
}
params = {
    "serviceKey": SERVICE_KEY,
    "sigunguCd": "11680",
    "bjdongCd": "10100",
    "bun": "0761",
    "ji": "0026",
    "numOfRows": "5",
    "pageNo": "1",
    "_type": "json",
}

res = requests.get(URL, params=params, timeout=30)
res.encoding = "utf-8"

print("HTTP:", res.status_code)
print("Content-Type:", res.headers.get("Content-Type"))
print("-" * 50)
print(res.text[:2000])
