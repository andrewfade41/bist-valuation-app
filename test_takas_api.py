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
    
    # Try different combinations
    print(f"Current Time: {datetime.now()}")
    for i in range(1, 10):
        bitis_dt = datetime.now() - timedelta(days=i)
        bitis = bitis_dt.strftime("%d-%m-%Y")
        
        for days in [1, 7, 30, 90]:
            baslangic_dt = bitis_dt - timedelta(days=days)
            baslangic = baslangic_dt.strftime("%d-%m-%Y")
            
            payload = {
                "baslangicTarih": baslangic,
                "bitisTarihi": bitis,
                "sektor": None,
                "endeks": None,
                "hisse": None
            }
            
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                if response.status_code == 200:
                    data = response.json().get('d', [])
                    if data:
                        print(f"SUCCESS: Bitis: {bitis} ({bitis_dt.strftime('%A')}), Baslangic: {baslangic} ({baslangic_dt.strftime('%A')}), Days: {days} -> Data: {len(data)}")
                    else:
                        print(f"EMPTY: Bitis: {bitis} ({bitis_dt.strftime('%A')}), Baslangic: {baslangic} ({baslangic_dt.strftime('%A')}), Days: {days}")
                else:
                    print(f"FAILED: Bitis: {bitis}, Status: {response.status_code}")
            except Exception as e:
                print(f"Exception for {bitis}: {e}")

if __name__ == "__main__":
    test_takas()
