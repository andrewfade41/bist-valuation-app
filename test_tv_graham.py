import urllib.request
import json
import pandas as pd

url = "https://scanner.tradingview.com/turkey/scan"

def test_col(col):
    data = {"filter": [{"left": "name", "operation": "nempty"}], "options": {"lang": "tr"}, "markets": ["turkey"], "symbols": {"query": {"types": ["stock"]}}, "columns": ["name", col], "range": [0, 1]}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            print("OK:", col, res['data'][0]['d'][1] if res['data'] else "none")
    except Exception as e:
        print("FAIL:", col, e)

for c in ["current_ratio", "return_on_equity", "debt_to_equity", "price_earnings_ttm", "price_book_ratio", "dividend_yield_recent", "dividend_yield_current", "price_earnings_ratio"]:
    test_col(c)

