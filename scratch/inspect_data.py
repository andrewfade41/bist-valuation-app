import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_fetcher import fetch_bist_fundamentals

def inspect():
    df = fetch_bist_fundamentals()
    if df is None:
        print("FAIL to fetch")
        return
        
    print(f"Total stocks fetched: {len(df)}")
    
    # 1. Stocks with RSI < 30
    oversold = df[df['RSI (14)'] < 30]
    print(f"\nOversold stocks (RSI < 30) count: {len(oversold)}")
    if not oversold.empty:
        for idx, row in oversold.head(10).iterrows():
            ratio = row['volume'] / row['average_volume_60d_calc'] if row['average_volume_60d_calc'] else 0
            print(f"Ticker: {row['Kod']:8s} | RSI: {row['RSI (14)']:5.2f} | Volume Ratio: {ratio:5.2f}")
            
    # 2. Stocks with volume ratio > 3.0
    high_vol = df[df['volume'] > df['average_volume_60d_calc'] * 3.0]
    print(f"\nHigh volume stocks (ratio > 3.0) count: {len(high_vol)}")
    if not high_vol.empty:
        for idx, row in high_vol.iterrows():
            print(f"Ticker: {row['Kod']:8s} | RSI: {row['RSI (14)']} | Volume: {row['volume']} | Avg: {row['average_volume_60d_calc']}")

if __name__ == "__main__":
    inspect()
