import sys
import os
sys.path.append("/Users/andrew/Desktop/migration_hp/PYTHON CODES/borsa adil değer/bist_valuation_app")
from data_fetcher import fetch_bist_fundamentals
import pandas as pd

def verify():
    print("Fetching data with advanced Takas...")
    df = fetch_bist_fundamentals()
    
    if df is None:
        print("FAILED: DataFrame is None")
        return
        
    print(f"Success: Fetched {len(df)} stocks.")
    
    takas_cols = ['Yabancı Payı (%)', 'Takas (7G Değişim %)', 'Takas (30G Değişim %)', 'Takas (90G Değişim %)']
    present_cols = [col for col in takas_cols if col in df.columns]
    
    print(f"Takas columns found: {present_cols}")
    
    if len(present_cols) < 4:
        print(f"FAILED: Some Takas columns are missing. Found: {present_cols}")
        return
        
    # Check a few samples
    samples = df[['Kod', 'Yabancı Payı (%)', 'Takas (7G Değişim %)', 'Takas (30G Değişim %)', 'Takas (90G Değişim %)']].dropna().head(10)
    print("\nSample Data (Advanced Takas):")
    print(samples)
    
    if len(samples) == 0:
        print("WARNING: No stocks have complete Takas data.")
    else:
        print("\nVerification Successful: Multi-date Takas data is being fetched and merged.")

if __name__ == "__main__":
    verify()
