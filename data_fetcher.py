import pandas as pd
import ssl
import json
import urllib.request
from datetime import datetime, timedelta

def fetch_bist_fundamentals():
    # Bypass SSL verification if needed for MacOS python environments
    ssl._create_default_https_context = ssl._create_unverified_context
    
    url = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx"
    
    print("Fetching fundamental data from İş Yatırım...")
    try:
        # decimal comes as ',' and thousands as '.' in Turkish localized websites
        dfs = pd.read_html(url, decimal=',', thousands='.')
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

    # We need the table containing F/K, PD/DD, and Son Dönem. (Table 6)
    # And Table 2 for Halka Açıklık Oranı (%)
    target_df = None
    halka_aciklik_df = None
    
    for df in dfs:
        if set(['Kod', 'F/K', 'PD/DD', 'Son Dönem']).issubset(df.columns):
            target_df = df
        if 'Halka Açıklık Oranı (%)' in df.columns and 'Kod' in df.columns:
            halka_aciklik_df = df[['Kod', 'Halka Açıklık Oranı (%)']].copy()
            
    if target_df is None:
        print("Could not find the target table on the page.")
        return None

    # Clean the data
    # Convert 'A/D' (Anlamlı Değil/Not meaningful) to NaN
    target_df = target_df.replace('A/D', pd.NA)
    
    # Convert numeric columns to float
    numeric_cols = ['Kapanış (TL)', 'F/K', 'PD/DD']
    for col in numeric_cols:
        target_df[col] = pd.to_numeric(target_df[col], errors='coerce')
        
    # Merge Halka Açıklık from Table 2
    if halka_aciklik_df is not None:
        halka_aciklik_df['Halka Açıklık Oranı (%)'] = pd.to_numeric(halka_aciklik_df['Halka Açıklık Oranı (%)'], errors='coerce')
        target_df = target_df.merge(halka_aciklik_df, on='Kod', how='left')
        # Rename for consistency with app.py if needed, app.py uses 'Halka Açıklık (%)'
        target_df = target_df.rename(columns={'Halka Açıklık Oranı (%)': 'Halka Açıklık (%)'})

    # Sadece kapanış fiyatı olmayan hisseleri çıkart (işlem görmeyen/tahtası kapalı)
    target_df = target_df.dropna(subset=['Kapanış (TL)'])
    target_df['Kod'] = target_df['Kod'].str.strip()
    target_df = target_df.drop_duplicates(subset=['Kod'])
    
    # Merge Advanced Takas Data (7, 30, 90 Days)
    print("Fetching advanced Takas data (7, 30, 90 days)...")
    try:
        # Find the latest available date for Takas data (check last 5 days)
        latest_takas_df = pd.DataFrame()
        latest_date_str = ""
        
        for i in range(1, 6):
            check_date = (datetime.now() - timedelta(days=i))
            df_check = fetch_takas_data(days_back=1, bitis_date=check_date)
            if not df_check.empty:
                latest_takas_df = df_check
                latest_date_str = check_date.strftime("%d-%m-%Y")
                print(f"Using latest Takas date: {latest_date_str}")
                break
        
        if not latest_takas_df.empty:
            # Current Takas & 7 Days Change
            # We already have the 'latest' data, but we need the change from 7 days before THAT date
            bitis_dt = datetime.strptime(latest_date_str, "%d-%m-%Y")
            
            df_7g = fetch_takas_data(days_back=7, bitis_date=bitis_dt)
            if not df_7g.empty:
                df_7g = df_7g.drop_duplicates(subset=['Kod'])
                df_7g = df_7g.rename(columns={'YAB_ORAN_END': 'Yabancı Payı (%)', 'DEGISIM': 'Takas (7G Değişim %)'})
                target_df = target_df.merge(df_7g[['Kod', 'Yabancı Payı (%)', 'Takas (7G Değişim %)']], on='Kod', how='left')
            
            # 30 Days Change
            df_30g = fetch_takas_data(days_back=30, bitis_date=bitis_dt)
            if not df_30g.empty:
                df_30g = df_30g.drop_duplicates(subset=['Kod'])
                df_30g = df_30g.rename(columns={'DEGISIM': 'Takas (30G Değişim %)'})
                target_df = target_df.merge(df_30g[['Kod', 'Takas (30G Değişim %)']], on='Kod', how='left')
                
            # 90 Days Change
            df_90g = fetch_takas_data(days_back=90, bitis_date=bitis_dt)
            if not df_90g.empty:
                df_90g = df_90g.drop_duplicates(subset=['Kod'])
                df_90g = df_90g.rename(columns={'DEGISIM': 'Takas (90G Değişim %)'})
                target_df = target_df.merge(df_90g[['Kod', 'Takas (90G Değişim %)']], on='Kod', how='left')
                
    except Exception as e:
        print(f"Error merging advanced Takas data: {e}")

    # Merge TV Data
    print("Fetching live technical data from TradingView...")
    tv_df = fetch_tv_data()
    if not tv_df.empty:
        target_df = target_df.merge(tv_df, on='Kod', how='left')
        target_df['Bilanço Açıklanma Tarihi'] = target_df['Bilanço Açıklanma Tarihi'].fillna('Belirsiz')
    
    return target_df

def fetch_takas_data(days_back=7, bitis_date=None):
    import requests
    
    url = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/GetYabanciOranlarXHR"
    
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if bitis_date is None:
        bitis_dt = datetime.now() - timedelta(days=1)
    else:
        bitis_dt = bitis_date
        
    bitis = bitis_dt.strftime("%d-%m-%Y")
    baslangic = (bitis_dt - timedelta(days=days_back)).strftime("%d-%m-%Y")
    
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
                df = pd.DataFrame(data)
                df = df.rename(columns={'HISSE_KODU': 'Kod'})
                df['Kod'] = df['Kod'].str.strip()
                return df[['Kod', 'YAB_ORAN_END', 'DEGISIM']]
    except Exception as e:
        print(f"Error fetching Takas ({days_back} days) for {bitis}: {e}")
    
    return pd.DataFrame()

def fetch_tv_data():
    url = "https://scanner.tradingview.com/turkey/scan"
    data = {
        "filter": [{"left": "name", "operation": "nempty"}],
        "options": {"lang": "tr"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
        "columns": ["name", "earnings_release_date", "RSI", "SMA50", "SMA150", "SMA200", "price_52_week_high", "price_52_week_low", "current_ratio", "debt_to_equity", "dividend_yield_recent", "market_cap_basic", "return_on_equity"],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 1000]
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    records = []
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            for row in result.get('data', []):
                ticker = row['d'][0]
                timestamp = row['d'][1]
                rsi = row['d'][2]
                sma50 = row['d'][3]
                sma150 = row['d'][4]
                sma200 = row['d'][5]
                high_52w = row['d'][6]
                low_52w = row['d'][7]
                current_ratio = row['d'][8]
                debt_to_equity = row['d'][9]
                dividend_yield = row['d'][10]
                market_cap = row['d'][11]
                roe = row['d'][12]
                
                if pd.notnull(timestamp):
                    formatted_date = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y')
                else:
                    formatted_date = 'Belirsiz'
                    
                records.append({
                    'Kod': ticker,
                    'Bilanço Açıklanma Tarihi': formatted_date,
                    'RSI (14)': rsi,
                    'MA50': sma50,
                    'MA150': sma150,
                    'MA200': sma200,
                    '52 Haftalık Zirve': high_52w,
                    '52 Haftalık Dip': low_52w,
                    'Cari Oran': current_ratio,
                    'Borç/Özkaynak': debt_to_equity,
                    'Temettü Verimi': dividend_yield,
                    'Piyasa Değeri': market_cap,
                    'TV_ROE': roe
                })
    except Exception as e:
        print("Error fetching TV data:", e)
        
    return pd.DataFrame(records)

if __name__ == "__main__":
    df = fetch_bist_fundamentals()
    if df is not None:
        print(df.head())
        print(f"Total valid stocks fetched: {len(df)}")
