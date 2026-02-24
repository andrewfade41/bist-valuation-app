import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys

# Add parent dir to path to import from bist_valuation_app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bist_valuation_app.data_fetcher import fetch_bist_fundamentals

def get_sector(ticker):
    try:
        t = yf.Ticker(ticker + ".IS")
        sector = t.info.get("sector", "Unknown")
        return ticker, sector
    except Exception as e:
        return ticker, "Unknown"

def main():
    df = fetch_bist_fundamentals()
    if df is None:
        print("Failed to fetch fundamentals.")
        return
        
    tickers = df['Kod'].tolist()
    print(f"Fetching sectors for {len(tickers)} tickers via yfinance...")
    
    sector_map = {}
    # Use ThreadPoolExecutor to speed up fetching
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(get_sector, tickers)
        for ticker, sector in results:
            sector_map[ticker] = sector
            print(f"{ticker}: {sector}")
            
    # Save to a JSON file in the bist_valuation_app directory
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sectors.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(sector_map, f, indent=4, ensure_ascii=False)
    print(f"Done. Saved sectors to {out_path}.")

if __name__ == '__main__':
    main()
