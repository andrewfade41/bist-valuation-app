import json
import urllib.request

def test_volume_stats():
    url = "https://scanner.tradingview.com/turkey/scan"
    data = {
        "filter": [
            {"left": "name", "operation": "nempty"}
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
        "range": [0, 100]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Total count: {result.get('totalCount')}")
            for row in result.get('data', [])[:20]:
                name = row['d'][0]
                vol = row['d'][1]
                avg = row['d'][2]
                ratio = (vol / avg) if avg and avg > 0 else 0
                print(f"Ticker: {name:8s} | Vol: {vol:12d} | AvgVol60d: {avg:12.1f} | Ratio: {ratio:5.2f}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_volume_stats()
