import json
import urllib.request
import pandas as pd

def test_tv_peg():
    url = "https://scanner.tradingview.com/turkey/scan"
    data = {
        "filter": [{"left": "name", "operation": "nempty"}],
        "options": {"lang": "tr"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
        "columns": [
            "name", 
            "peg_ratio",
            "net_income_yoy_growth_ttm",
            "price_earnings_ttm"
        ],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 10]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            for row in result.get('data', []):
                print(f"Ticker: {row['d'][0]}, PEG: {row['d'][1]}, Growth: {row['d'][2]}, PE: {row['d'][3]}")
    except Exception as e:
        print("Error fetching TV data:", e)

if __name__ == "__main__":
    test_tv_peg()
