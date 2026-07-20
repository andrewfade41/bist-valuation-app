import json
import urllib.request

def run_query(filter_config):
    url = "https://scanner.tradingview.com/turkey/scan"
    data = {
        "filter": [
            {"left": "name", "operation": "nempty"},
            filter_config
        ],
        "options": {"lang": "tr"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
        "columns": ["name", "volume", "average_volume_60d_calc"],
        "range": [0, 10]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('totalCount'), [row['d'][0] for row in result.get('data', [])]
    except Exception as e:
        return f"Error: {e}", []

if __name__ == "__main__":
    # Test: above% with 0.03 (which corresponds to 3%)
    c, stocks = run_query({"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 0.03]})
    print(f"Test (above% with 0.03): Total Count = {c}, Stocks (first 10) = {stocks}")
    
    # Test: above% with 0.5 (50% above average)
    c5, stocks5 = run_query({"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 0.5]})
    print(f"Test (above% with 0.5): Total Count = {c5}, Stocks (first 10) = {stocks5}")
