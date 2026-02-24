import urllib.request
import json
import os
import ssl
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context

def fetch_earnings_dates():
    print("Fetching earnings release dates from TradingView...")
    url = "https://scanner.tradingview.com/turkey/scan"
    
    # Query all BIST stocks
    data = {
        "filter": [{"left": "name", "operation": "nempty"}],
        "options": {"lang": "tr"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
        "columns": ["name", "earnings_release_date"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 1000] # fetch up to 1000 stocks
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    earnings_map = {}
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            for row in result.get('data', []):
                ticker = row['d'][0]
                timestamp = row['d'][1]
                if timestamp is not None:
                    # Convert TV UTC timestamp to formatted date string
                    formatted_date = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y')
                    earnings_map[ticker] = formatted_date
                else:
                    earnings_map[ticker] = "Belirsiz"
                    
        # Save to a JSON file in the bist_valuation_app directory
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'earnings_dates.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(earnings_map, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully saved {len(earnings_map)} earnings dates to {out_path}.")
        return earnings_map

    except Exception as e:
        print("Error fetching TV dates:", e)
        return None

if __name__ == "__main__":
    fetch_earnings_dates()
