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
    # Test 1: above% with 3
    c1, stocks1 = run_query({"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 3]})
    print(f"Test 1 (above% with 3): Total Count = {c1}, Stocks = {stocks1}")
    
    # Test 2: above% with 300
    c2, stocks2 = run_query({"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 300]})
    print(f"Test 2 (above% with 300): Total Count = {c2}, Stocks = {stocks2}")
    
    # Test 3: above% with 0
    c3, stocks3 = run_query({"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 0]})
    print(f"Test 3 (above% with 0): Total Count = {c3}, Stocks = {stocks3}")
    
    # Test 4: above% with 30 (30%)
    c4, stocks4 = run_query({"left": "volume", "operation": "above%", "right": ["average_volume_60d_calc", 30]})
    print(f"Test 4 (above% with 30): Total Count = {c4}, Stocks = {stocks4}")
