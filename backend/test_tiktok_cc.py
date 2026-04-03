import requests

url = "https://ads.tiktok.com/creative_radar_api/v1/top_ads/v2/list"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "anonymous-user-id": "0000000000000000000",
}
params = {
    "page": 1,
    "limit": 20,
    "period": 30,
    "industry": "",
    "objective": "",
    "region": "US",
    "language": "",
    "sort_by": "like",
}

try:
    response = requests.get(url, headers=headers, params=params)
    print(response.status_code)
    print(response.text[:500])
except Exception as e:
    print(e)
