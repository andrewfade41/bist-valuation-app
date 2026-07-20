import json
import urllib.request

def test_volume():
    url = "https://scanner.tradingview.com/turkey/scan"
    data = {
        "filter": [
            {"left": "name", "operation": "nempty"},
            {"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 3]}
        ],
        "options": {"lang": "tr"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
        "columns": [
            "name",
            "volume",
            "average_volume_60d_calc"
        ],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, 20]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Total count returned by query: {result.get('totalCount')}")
            for row in result.get('data', [])[:10]:
                print(f"Ticker: {row['d'][0]}, Vol: {row['d'][1]}, AvgVol60d: {row['d'][2]}")
    except Exception as e:
        print("Error fetching TV data:", e)

if __name__ == "__main__":
    test_volume()
