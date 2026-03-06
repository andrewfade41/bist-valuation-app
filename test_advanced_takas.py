import requests
import json
from datetime import datetime, timedelta

def test_ajax():
    url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/GetYabanciOranlarXHR"
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Use EXACT payload from user's curl
    payload = {
        "baslangicTarih": "11-02-2026", # Example from user
        "bitisTarihi": "05-03-2026",    # Example from user
        "sektor": None,
        "endeks": "09",
        "hisse": None
    }
    
    print(f"Requesting data with payload: {payload}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Response text: {response.text}")
            return

        result = response.json()
        data = result.get('d', [])
        print(f"Successfully fetched {len(data)} items.")
        
        if data:
            print("\nSample item:")
            print(json.dumps(data[0], indent=2))
        else:
            print("No data returned. Trying with endeks=None...")
            payload["endeks"] = None
            response = requests.post(url, headers=headers, json=payload)
            result = response.json()
            data = result.get('d', [])
            print(f"Fetched with endeks=None: {len(data)} items.")
            if data:
                print("\nSample item (endeks=None):")
                print(json.dumps(data[0], indent=2))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ajax()
