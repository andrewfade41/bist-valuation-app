import pandas as pd
import numpy as np
import json
import os

def calculate_fair_values(df, target_fk=10.0, target_pddd=1.5, expected_return=0.5):
    """
    Calculates fair values based on F/K, PD/DD, and ROE.
    
    Parameters:
    - target_fk: Beklenen/Sektör F/K çarpanı
    - target_pddd: Beklenen/Sektör PD/DD çarpanı
    - expected_return: Risksiz getiri / Beklenen minimum getiri oranı (ör. %50 -> 0.5)
    """
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    # Deriving metrics
    # EPS (Hisse Başına Kar) = Fiyat / F/K
    df['EPS_Derived'] = df['Kapanış (TL)'] / df['F/K']
    
    # BVPS (Hisse Başına Defter Değeri) = Fiyat / PD/DD
    df['BVPS_Derived'] = df['Kapanış (TL)'] / df['PD/DD']
    
    # ROE (Özsermaye Karlılığı) = EPS / BVPS = PD/DD / F/K
    df['ROE_Derived'] = df['PD/DD'] / df['F/K']
    
    # Method 1: F/K Bazlı Hedef Fiyat = EPS * Hedef F/K
    df['Hedef Fiyat (F/K)'] = df['EPS_Derived'] * target_fk
    
    # Method 2: PD/DD Bazlı Hedef Fiyat = BVPS * Hedef PD/DD
    df['Hedef Fiyat (PD/DD)'] = df['BVPS_Derived'] * target_pddd
    
    # Method 3: ROE Bazlı Hedef Fiyat = BVPS * (ROE / Beklenen Getiri)
    df['Hedef Fiyat (ROE)'] = df['BVPS_Derived'] * (df['ROE_Derived'] / expected_return)
    
    # Replace inf with NaN to avoid calculation errors
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # Load Sectors
    sectors_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sectors.json')
    if os.path.exists(sectors_path):
        with open(sectors_path, 'r', encoding='utf-8') as f:
            sector_map = json.load(f)
        df['Sektör'] = df['Kod'].map(sector_map).fillna('Unknown')
    else:
        df['Sektör'] = 'Unknown'
        
    # Calculate BIST Averages (excluding inf, nan and extremely high outliers > 500)
    # We clip or filter outliers to get a realistic BIST average
    valid_fk = df['F/K'].replace([np.inf, -np.inf], np.nan)
    valid_fk = valid_fk[(valid_fk > 0) & (valid_fk < 150)]
    bist_avg_fk = valid_fk.mean() if not valid_fk.empty else 10.0

    valid_pddd = df['PD/DD'].replace([np.inf, -np.inf], np.nan)
    valid_pddd = valid_pddd[(valid_pddd > 0) & (valid_pddd < 50)]
    bist_avg_pddd = valid_pddd.mean() if not valid_pddd.empty else 1.5
    
    # Calculate Sector Averages
    sector_avg_pddd = df.groupby('Sektör')['PD/DD'].transform(
        lambda x: x.replace([np.inf, -np.inf], np.nan)[(x > 0) & (x < 50)].mean()
    )
    # Fill NaN sector averages with BIST average if sector is too small 
    sector_avg_pddd = sector_avg_pddd.fillna(bist_avg_pddd)

    # ------------------ NEW USER REQUESTED COLUMNS ------------------
    # BİST Ortalaması Bazlı Hedef Fiyat:
    # Ortalaması ( EPS * BIST_Avg_FK  ve  BVPS * BIST_Avg_PDDD )
    df['Hedef Fiyat (BIST Ort.)'] = ((df['EPS_Derived'] * bist_avg_fk) + (df['BVPS_Derived'] * bist_avg_pddd)) / 2
    
    # Sektör PD/DD Ortalaması Bazlı Hedef Fiyat:
    df['Hedef Fiyat (Sektör PD/DD)'] = df['BVPS_Derived'] * sector_avg_pddd
    
    # MA200 Uzaklık (%) calculation
    # If MA200 is available, calculate percentage distance. Use coerce for safety.
    if 'MA200' in df.columns:
        df['MA200'] = pd.to_numeric(df['MA200'], errors='coerce')
        df['MA200 Uzaklık (%)'] = ((df['Kapanış (TL)'] - df['MA200']) / df['MA200']) * 100
    else:
        df['MA200 Uzaklık (%)'] = np.nan
        df['RSI (14)'] = np.nan

    # Average Target Price (Eksik verileri yok sayarak hesaplar) - using original 3 formulas
    hesaplanan_kolonlar = ['Hedef Fiyat (F/K)', 'Hedef Fiyat (PD/DD)', 'Hedef Fiyat (ROE)']
    df['Nihai Hedef Fiyat'] = df[hesaplanan_kolonlar].mean(axis=1)
    
    # Potential Profit/Loss Percentage
    df['Potansiyel Getiri (%)'] = ((df['Nihai Hedef Fiyat'] - df['Kapanış (TL)']) / df['Kapanış (TL)']) * 100
    
    # Sort by Potential Return (Büyükten Küçüğe), keeping NaNs at the end
    df = df.sort_values(by='Potansiyel Getiri (%)', ascending=False, na_position='last')
    
    # Clean up column formatting for presentation
    cols_to_round = ['Hedef Fiyat (F/K)', 'Hedef Fiyat (PD/DD)', 'Hedef Fiyat (ROE)', 
                     'Hedef Fiyat (BIST Ort.)', 'Hedef Fiyat (Sektör PD/DD)', 
                     'Nihai Hedef Fiyat', 'Potansiyel Getiri (%)', 'ROE_Derived',
                     'MA200 Uzaklık (%)', 'RSI (14)']
    for col in cols_to_round:
        # We need to fillna with None or np.nan before formatting, but actually round handles NaNs gracefully
        if col in df.columns:
            df[col] = df[col].astype(float).round(2)
        
    # Prepare summary statistics to return
    # Calculate Sector F/K Averages for display purposes (even though not used in method 2 due to potential unreliability)
    sector_avg_summary = df.groupby('Sektör').agg(
        Sektör_FK_Ortalama=('F/K', lambda x: x.replace([np.inf, -np.inf], np.nan)[(x > 0) & (x < 150)].mean()),
        Sektör_PDDD_Ortalama=('PD/DD', lambda x: x.replace([np.inf, -np.inf], np.nan)[(x > 0) & (x < 50)].mean()),
        Hisse_Sayısı=('Kod', 'count')
    ).reset_index()
    
    summary_stats = {
        'bist_avg_fk': round(bist_avg_fk, 2),
        'bist_avg_pddd': round(bist_avg_pddd, 2),
        'sector_avg_df': sector_avg_summary
    }
        
    return df, summary_stats

if __name__ == "__main__":
    from data_fetcher import fetch_bist_fundamentals
    df_raw = fetch_bist_fundamentals()
    if df_raw is not None:
        df_calc, stats = calculate_fair_values(df_raw)
        print("BIST Averages:", stats)
        print("Top 5 Stocks by Potential Return:")
        print(df_calc[['Kod', 'Sektör', 'Kapanış (TL)', 'Nihai Hedef Fiyat', 'Hedef Fiyat (BIST Ort.)', 'Hedef Fiyat (Sektör PD/DD)']].head())
