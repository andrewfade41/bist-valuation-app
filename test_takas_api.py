import requests
import json
from datetime import datetime, timedelta
import pandas as pd

def test_takas(days_back=7):
    url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/GetYabanciOranlarXHR"
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Try different dates
    for i in range(1, 6):
        bitis_dt = datetime.now() - timedelta(days=i)
        bitis = bitis_dt.strftime("%d-%m-%Y")
        baslangic = (bitis_dt - timedelta(days=days_back)).strftime("%d-%m-%Y")
        
        payload = {
            "baslangicTarih": baslangic,
            "bitisTarihi": bitis,
            "sektor": None,
            "endeks": None,
            "hisse": None
        }
        
        print(f"Testing with Bitis: {bitis}, Baslangic: {baslangic}")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json().get('d', [])
                print(f"Length of data: {len(data)}")
                if data:
                    print(f"First record: {data[0]}")
                    break
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    test_takas()
