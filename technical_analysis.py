import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import logging

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    
    # Wilder's Smoothing using Exponential Moving Average
    # alpha = 1 / period -> com = period - 1
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def find_pivots(series, order=5):
    """
    Finds local peaks and troughs in a series.
    order: number of points on each side to use for comparison.
    """
    peaks = argrelextrema(series.values, np.greater_equal, order=order)[0]
    troughs = argrelextrema(series.values, np.less_equal, order=order)[0]
    return list(peaks), list(troughs)

def detect_bullish_divergence(df, order=5):
    """
    Detects Regular Bullish Divergence:
    - Price: Lower Low
    - RSI: Higher Low
    """
    if len(df) < 30:
        return None
    
    # Create a copy to avoid modification issues
    df = df.copy()
    
    # Flatten multi-index columns if they exist
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # Calculate RSI if not present
    if 'RSI' not in df.columns:
        close_data = df['Close']
        df['RSI'] = calculate_rsi(close_data)
        
    df = df.dropna(subset=['RSI'])
    # Reset index to use integer locations for pivot logic
    df_idx = df.reset_index()
    
    # Ensure we use the correct column names
    low_data = df_idx['Low']
    rsi_data = df_idx['RSI']
    
    # Find troughs in Price (Low) and RSI
    _, price_troughs = find_pivots(low_data, order=order)
    _, rsi_troughs = find_pivots(rsi_data, order=order)
    
    if len(price_troughs) < 2 or len(rsi_troughs) < 2:
        return None
        
    # Check most recent trough
    recent_trough_idx = price_troughs[-1]
    
    # Signal should be fresh (close to the end of data)
    if (len(df_idx) - 1 - recent_trough_idx) > order + 2:
        return None
        
    prev_trough_idx = price_troughs[-2]
    
    current_price_low = low_data.iloc[recent_trough_idx]
    prev_price_low = low_data.iloc[prev_trough_idx]
    
    # Condition 1: Lower Low in Price
    if current_price_low < prev_price_low:
        # Find corresponding RSI troughs (indices might slightly differ)
        # We look for RSI troughs near the Price troughs
        curr_rsi_trough_idx = min(rsi_troughs, key=lambda x: abs(x - recent_trough_idx))
        prev_rsi_trough_idx = min(rsi_troughs, key=lambda x: abs(x - prev_trough_idx))
        
        # Ensure they are reasonably aligned (within 3 bars)
        if abs(curr_rsi_trough_idx - recent_trough_idx) <= 3 and abs(prev_rsi_trough_idx - prev_trough_idx) <= 3:
            current_rsi = rsi_data.iloc[curr_rsi_trough_idx]
            prev_rsi = rsi_data.iloc[prev_rsi_trough_idx]
            
            # Condition 2: Higher Low in RSI
            if current_rsi > prev_rsi:
                # Optional: At least one point was in oversold territory or close to it
                if prev_rsi < 35 or current_rsi < 35:
                    return {
                        'type': 'Pozitif Uyumsuzluk',
                        'current_price': float(current_price_low),
                        'prev_price': float(prev_price_low),
                        'current_rsi': float(current_rsi),
                        'prev_rsi': float(prev_rsi),
                        'date': df_idx.loc[recent_trough_idx, 'Date'].strftime('%d.%m.%Y') if 'Date' in df_idx.columns else ''
                    }
    return None
