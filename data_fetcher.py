import pandas as pd
import ssl
import json
import urllib.request
from datetime import datetime

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

    # We need the table containing F/K, PD/DD, and Son Dönem. (Table 6 in our test)
    # Let's search for the dataframe that has 'F/K' and 'PD/DD' and 'Son Dönem'
    target_df = None
    for df in dfs:
        if set(['Kod', 'F/K', 'PD/DD', 'Son Dönem']).issubset(df.columns):
            target_df = df
            break
            
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
        
    # Sadece kapanış fiyatı olmayan hisseleri çıkart (işlem görmeyen/tahtası kapalı)
    # F/K veya PD/DD'si NaN olanları da hesaplamaya dahil etmeye çalışacağız
    target_df = target_df.dropna(subset=['Kapanış (TL)'])
    
    # Merge TV Data
    print("Fetching live technical data from TradingView...")
    tv_df = fetch_tv_data()
    if not tv_df.empty:
        target_df = target_df.merge(tv_df, on='Kod', how='left')
        target_df['Bilanço Açıklanma Tarihi'] = target_df['Bilanço Açıklanma Tarihi'].fillna('Belirsiz')
    
    return target_df

def fetch_tv_data():
    url = "https://scanner.tradingview.com/turkey/scan"
    data = {
        "filter": [{"left": "name", "operation": "nempty"}],
        "options": {"lang": "tr"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
        "columns": ["name", "earnings_release_date", "RSI", "SMA50", "SMA150", "SMA200", "price_52_week_high", "price_52_week_low", "current_ratio", "debt_to_equity", "dividend_yield_recent", "market_cap_basic", "return_on_equity", "float_shares_outstanding", "total_shares_outstanding"],
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
                float_shares = row['d'][13]
                total_shares = row['d'][14]
                
                # Calculate Free Float Ratio
                halka_aciklik = None
                if float_shares and total_shares and total_shares > 0:
                    halka_aciklik = (float_shares / total_shares) * 100
                
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
                    'TV_ROE': roe,
                    'Halka Açıklık (%)': halka_aciklik
                })
    except Exception as e:
        print("Error fetching TV data:", e)
        
    return pd.DataFrame(records)

if __name__ == "__main__":
    df = fetch_bist_fundamentals()
    if df is not None:
        print(df.head())
        print(f"Total valid stocks fetched: {len(df)}")
