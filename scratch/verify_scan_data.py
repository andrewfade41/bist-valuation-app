import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_fetcher import fetch_bist_fundamentals
from constants import VOLUME_FILTER_MULTIPLIER

def test_fetch_and_filter():
    print("Testing data fetching...")
    df = fetch_bist_fundamentals()
    if df is None or df.empty:
        print("FAIL: DataFrame is empty or None")
        return
        
    print("\nDataFrame columns:")
    print(df.columns.tolist())
    
    # Check if volume columns exist
    if 'volume' not in df.columns or 'average_volume_60d_calc' not in df.columns:
        print("FAIL: 'volume' or 'average_volume_60d_calc' not found in columns")
        return
        
    print(f"\nTotal rows fetched: {len(df)}")
    
    # Check data types and print first few rows
    tv_data = df[['Kod', 'volume', 'average_volume_60d_calc']].dropna()
    print(f"Rows with valid TradingView volume data: {len(tv_data)}")
    
    # Filter
    filtered_df = tv_data[tv_data['volume'] > tv_data['average_volume_60d_calc'] * VOLUME_FILTER_MULTIPLIER]
    print(f"Rows matching volume filter (volume > average * {VOLUME_FILTER_MULTIPLIER}): {len(filtered_df)}")
    
    if len(filtered_df) > 0:
        print("\nFirst 5 matched stocks:")
        for idx, row in filtered_df.head(5).iterrows():
            ratio = row['volume'] / row['average_volume_60d_calc']
            print(f"Ticker: {row['Kod']:8s} | Volume: {row['volume']:12.1f} | Avg 60d: {row['average_volume_60d_calc']:12.1f} | Ratio: {ratio:5.2f}")
        print("\nSUCCESS: Volume filter test completed successfully!")
    else:
        print("\nWARNING: No stocks matched the volume filter. This is possible if the market is closed or volume is low today.")

if __name__ == "__main__":
    test_fetch_and_filter()
