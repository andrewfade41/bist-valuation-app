import urllib.request
import json
import pandas as pd

url = "https://scanner.tradingview.com/turkey/scan"
data = {
    "filter": [{"left": "name", "operation": "equal", "right": "THYAO"}],
    "options": {"lang": "tr"},
    "markets": ["turkey"],
    "symbols": {"query": {"types": ["stock"]}},
    "columns": ["name", "close", "SMA50", "SMA150", "SMA200", "price_52_week_high", "price_52_week_low"],
    "sort": {"sortBy": "name", "sortOrder": "asc"},
    "range": [0, 10]
}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(json.dumps(result, indent=2))
except Exception as e:
    print("Error:", e)
