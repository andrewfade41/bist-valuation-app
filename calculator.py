import pandas as pd
import numpy as np
import json
import os
from constants import (
    FK_VALID_MIN, FK_VALID_MAX, PDDD_VALID_MIN, PDDD_VALID_MAX,
    GRAHAM_MARKET_CAP_THRESHOLD, GRAHAM_CURRENT_RATIO_MIN,
    GRAHAM_DEBT_TO_EQUITY_MAX, GRAHAM_FK_MAX, GRAHAM_PDDD_MAX,
    GRAHAM_MULTIPLIER_MAX, GRAHAM_ROE_MIN, GRAHAM_RSI_MAX,
    GRAHAM_NUMBER_CONSTANT, GROWTH_STRONG_THRESHOLD,
    NET_DEBT_CASH_RICH_BONUS, MINERVINI_52W_LOW_MULTIPLIER,
    MINERVINI_52W_HIGH_MULTIPLIER, ANNUALIZATION_MULTIPLIERS,
    SEASONAL_SECTORS, SECTORS_FILENAME,
)

def _parse_period_month(period_str):
    """
    'Son Dönem' değerinden ay bilgisini çıkarır.
    Örn: '3/2026' -> 3, '12/2025' -> 12, 'Belirsiz' -> None
    """
    if pd.isna(period_str) or str(period_str).strip().lower() in ('belirsiz', 'nan', ''):
        return None
    try:
        month = int(str(period_str).split('/')[0])
        return month if month in ANNUALIZATION_MULTIPLIERS else None
    except (ValueError, IndexError):
        return None


def _get_current_expected_quarter():
    """
    Bugünün tarihine göre en güncel beklenen bilanço çeyreğini döndürür.
    Nisan 2026 → Q1 2026 (3/2026) bilançolarının açıklanması bekleniyor.
    """
    from datetime import datetime
    now = datetime.now()
    year = now.year
    month = now.month
    # Bilanço açıklanma takvimine göre:
    # Ocak-Mart  → 12/(yıl-1) yıl sonu bilançosu güncel
    # Nisan-Haziran → 3/yıl (Q1) bilançosu bekleniyor/açıklanıyor
    # Temmuz-Eylül → 6/yıl (Q2) bilançosu bekleniyor/açıklanıyor  
    # Ekim-Aralık → 9/yıl (Q3) bilançosu bekleniyor/açıklanıyor
    if month <= 3:
        return 12, year - 1
    elif month <= 6:
        return 3, year
    elif month <= 9:
        return 6, year
    else:
        return 9, year


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
    
    # ---------- TTM EPS Normalizasyonu ----------
    # Q1/Q2/Q3 bilançolarında EPS sadece kümülatif kâra dayanır.
    # Yıllıklaştırma yaparak F/K bazlı hedef fiyatların karşılaştırılabilir olmasını sağlıyoruz.
    if 'Son Dönem' in df.columns:
        df['_period_month'] = df['Son Dönem'].apply(_parse_period_month)
        df['_annualization_factor'] = df['_period_month'].map(ANNUALIZATION_MULTIPLIERS).fillna(1)
        df['EPS_TTM'] = df['EPS_Derived'] * df['_annualization_factor']
    else:
        df['EPS_TTM'] = df['EPS_Derived']
        df['_annualization_factor'] = 1
    
    # ROE (Özsermaye Karlılığı) = EPS / BVPS = PD/DD / F/K
    df['ROE_Derived'] = df['PD/DD'] / df['F/K']
    
    # Method 1: F/K Bazlı Hedef Fiyat = EPS_TTM * Hedef F/K
    # TTM normalizasyonlu EPS kullanılıyor
    df['Hedef Fiyat (F/K)'] = df['EPS_TTM'] * target_fk
    
    # Method 2: PD/DD Bazlı Hedef Fiyat = BVPS * Hedef PD/DD
    df['Hedef Fiyat (PD/DD)'] = df['BVPS_Derived'] * target_pddd
    
    # Method 3: ROE Bazlı Hedef Fiyat = BVPS * (ROE / Beklenen Getiri)
    df['Hedef Fiyat (ROE)'] = df['BVPS_Derived'] * (df['ROE_Derived'] / expected_return)
    
    # Replace inf with NaN to avoid calculation errors
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # Load Sectors
    sectors_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SECTORS_FILENAME)
    if os.path.exists(sectors_path):
        with open(sectors_path, 'r', encoding='utf-8') as f:
            sector_map = json.load(f)
        df['Sektör'] = df['Kod'].map(sector_map).fillna('Unknown')
    else:
        df['Sektör'] = 'Unknown'
    
    # ---------- Bilanço Güncellik Göstergesi ----------
    expected_quarter, expected_year = _get_current_expected_quarter()
    expected_period = f"{expected_quarter}/{expected_year}"
    
    def _classify_freshness(period_str):
        """Bilanço döneminin güncelliğini sınıflandırır."""
        if pd.isna(period_str) or str(period_str).strip().lower() in ('belirsiz', 'nan', ''):
            return 'Belirsiz'
        try:
            parts = str(period_str).split('/')
            p_month = int(parts[0])
            p_year = int(parts[1])
            e_month = expected_quarter
            e_year = expected_year
            # Çeyrek farkını hesapla
            quarter_map = {3: 1, 6: 2, 9: 3, 12: 4}
            p_q = quarter_map.get(p_month, 0)
            e_q = quarter_map.get(e_month, 0)
            diff = (e_year * 4 + e_q) - (p_year * 4 + p_q)
            if diff <= 0:
                return 'Güncel'     # Beklenen çeyrek veya daha yeni
            elif diff == 1:
                return 'Önceki'     # Bir önceki çeyrek
            else:
                return 'Eski'       # 2+ çeyrek eski
        except (ValueError, IndexError):
            return 'Belirsiz'
    
    if 'Son Dönem' in df.columns:
        df['Bilanço Güncelliği'] = df['Son Dönem'].apply(_classify_freshness)
        
        # Mevsimsel sektör uyarısı — yıllıklaştırmanın güvenilir olmayabileceği hisseler
        is_seasonal = df['Sektör'].isin(SEASONAL_SECTORS)
        is_interim = df['_annualization_factor'] > 1
        df['Mevsimsel Uyarı'] = is_seasonal & is_interim
        
    # Calculate BIST Averages (excluding inf, nan and extremely high outliers)
    # We clip or filter outliers to get a realistic BIST average
    valid_fk = df['F/K'].replace([np.inf, -np.inf], np.nan)
    valid_fk = valid_fk[(valid_fk > FK_VALID_MIN) & (valid_fk < FK_VALID_MAX)]
    bist_avg_fk = valid_fk.mean() if not valid_fk.empty else DEFAULT_TARGET_FK

    valid_pddd = df['PD/DD'].replace([np.inf, -np.inf], np.nan)
    valid_pddd = valid_pddd[(valid_pddd > PDDD_VALID_MIN) & (valid_pddd < PDDD_VALID_MAX)]
    bist_avg_pddd = valid_pddd.mean() if not valid_pddd.empty else DEFAULT_TARGET_PDDD
    
    # Calculate Sector Averages
    sector_avg_pddd = df.groupby('Sektör')['PD/DD'].transform(
        lambda x: x.replace([np.inf, -np.inf], np.nan)[(x > PDDD_VALID_MIN) & (x < PDDD_VALID_MAX)].mean()
    )
    # Fill NaN sector averages with BIST average if sector is too small 
    sector_avg_pddd = sector_avg_pddd.fillna(bist_avg_pddd)

    # ------------------ NEW USER REQUESTED COLUMNS ------------------
    # BİST Ortalaması Bazlı Hedef Fiyat:
    # Ortalaması ( EPS_TTM * BIST_Avg_FK  ve  BVPS * BIST_Avg_PDDD )
    df['Hedef Fiyat (BIST Ort.)'] = ((df['EPS_TTM'] * bist_avg_fk) + (df['BVPS_Derived'] * bist_avg_pddd)) / 2
    
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

    # ------------------ PEG RATIO CALCULATION ------------------
    # PEG = (F/K) / (Net Kar Yıllık Büyüme)
    # Growth is provided in percentage (e.g., 50 for 50%).
    # If growth <= 0, PEG is not meaningful for traditional valuation.
    if 'Net Kar Yıllık Büyüme (%)' in df.columns:
        df['PEG'] = np.where(
            (df['Net Kar Yıllık Büyüme (%)'] > 0) & (df['F/K'] > 0),
            df['F/K'] / df['Net Kar Yıllık Büyüme (%)'],
            np.nan
        )
    else:
        df['PEG'] = np.nan

    # Average Target Price (Eksik verileri yok sayarak hesaplar) - using original 3 formulas
    hesaplanan_kolonlar = ['Hedef Fiyat (F/K)', 'Hedef Fiyat (PD/DD)', 'Hedef Fiyat (ROE)']
    df['Nihai Hedef Fiyat'] = df[hesaplanan_kolonlar].mean(axis=1)
    
    # Potential Profit/Loss Percentage
    df['Potansiyel Getiri (%)'] = ((df['Nihai Hedef Fiyat'] - df['Kapanış (TL)']) / df['Kapanış (TL)']) * 100
    
    # ------------------ MINERVINI SCREENER ------------------
    # 1. Current Price > SMA 150 > SMA 200
    # 2. Current Price > SMA 50
    # 3. Current Price >= 1.3 * 52 Week Low
    # 4. Current Price >= 0.75 * 52 Week High
    
    # Ensure numerical types
    for col in ['MA50', 'MA150', 'MA200', '52 Haftalık Zirve', '52 Haftalık Dip', 'Kapanış (TL)']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if all(c in df.columns for c in ['MA50', 'MA150', 'MA200', '52 Haftalık Zirve', '52 Haftalık Dip', 'Kapanış (TL)']):
        c1 = (df['Kapanış (TL)'] > df['MA150']) & (df['MA150'] > df['MA200'])
        c2 = (df['Kapanış (TL)'] > df['MA50'])
        c3 = (df['Kapanış (TL)'] >= MINERVINI_52W_LOW_MULTIPLIER * df['52 Haftalık Dip'])
        c4 = (df['Kapanış (TL)'] >= MINERVINI_52W_HIGH_MULTIPLIER * df['52 Haftalık Zirve'])
        df['Minervini_Uyumlu'] = c1 & c2 & c3 & c4
    else:
        df['Minervini_Uyumlu'] = False

    # ------------------ GRAHAM RATING (0-10) ------------------
    # Initialize Graham Score
    df['Graham Skoru'] = 0

    # 1. Büyüklük (Size): Piyasa Değeri > 5.000.000.000
    if 'Piyasa Değeri' in df.columns:
        df['Piyasa Değeri'] = pd.to_numeric(df['Piyasa Değeri'], errors='coerce')
        df['Graham Skoru'] += (df['Piyasa Değeri'] > GRAHAM_MARKET_CAP_THRESHOLD).astype(int)

    # 2. Likidite: Cari Oran > 1.5
    if 'Cari Oran' in df.columns:
        df['Cari Oran'] = pd.to_numeric(df['Cari Oran'], errors='coerce')
        df['Graham Skoru'] += (df['Cari Oran'] > GRAHAM_CURRENT_RATIO_MIN).astype(int)

    # 3. Düşük Borçluluk: Borç/Özkaynak < 0.5
    if 'Borç/Özkaynak' in df.columns:
        df['Borç/Özkaynak'] = pd.to_numeric(df['Borç/Özkaynak'], errors='coerce')
        df['Graham Skoru'] += ((df['Borç/Özkaynak'] < GRAHAM_DEBT_TO_EQUITY_MAX) & (df['Borç/Özkaynak'] >= 0)).astype(int)

    # 4. Kârlılık İstikrarı: F/K > 0
    df['Graham Skoru'] += (df['F/K'] > 0).astype(int)

    # 5. Yüksek Kârlılık: ROE > %20
    df['Graham Skoru'] += (df['ROE_Derived'] > GRAHAM_ROE_MIN).astype(int)

    # 6. Ucuz Fiyatlama: F/K < 15
    df['Graham Skoru'] += ((df['F/K'] > 0) & (df['F/K'] < GRAHAM_FK_MAX)).astype(int)

    # 7. Makul Defter Değeri: PD/DD < 1.5
    df['Graham Skoru'] += ((df['PD/DD'] > 0) & (df['PD/DD'] < GRAHAM_PDDD_MAX)).astype(int)

    # 8. Graham Çarpan Şartı: (F/K * PD/DD) < 22.5
    df['Graham Skoru'] += (((df['F/K'] > 0) & (df['PD/DD'] > 0)) & ((df['F/K'] * df['PD/DD']) < GRAHAM_MULTIPLIER_MAX)).astype(int)

    # 9. Temettü Verimi: > 0
    if 'Temettü Verimi' in df.columns:
        df['Temettü Verimi'] = pd.to_numeric(df['Temettü Verimi'], errors='coerce')
        df['Graham Skoru'] += (df['Temettü Verimi'] > 0).astype(int)
        # TradingView decimal formatından yüzdeye çevir (0.05 → 5.0%)
        df['Temettü Verimi (%)'] = (df['Temettü Verimi'] * 100).round(2)

    # 10. Aşırı Fiyatlanmamış: RSI(14) < 60
    if 'RSI (14)' in df.columns:
        df['RSI (14)'] = pd.to_numeric(df['RSI (14)'], errors='coerce')
        df['Graham Skoru'] += ((df['RSI (14)'] > 0) & (df['RSI (14)'] < GRAHAM_RSI_MAX)).astype(int)

    # ------------------ OPERATIONAL HEALTH SCORE (0-10) ------------------
    df['Operasyonel Skor'] = 0
    
    # 1. Growth (FAVÖK & Net Kar)
    if 'FAVÖK Yıllık Büyüme (%)' in df.columns:
        df['FAVÖK Yıllık Büyüme (%)'] = pd.to_numeric(df['FAVÖK Yıllık Büyüme (%)'], errors='coerce')
        df['Operasyonel Skor'] += (df['FAVÖK Yıllık Büyüme (%)'] > 0).astype(int)
        df['Operasyonel Skor'] += (df['FAVÖK Yıllık Büyüme (%)'] > GROWTH_STRONG_THRESHOLD).astype(int)
        
    if 'Net Kar Yıllık Büyüme (%)' in df.columns:
        df['Net Kar Yıllık Büyüme (%)'] = pd.to_numeric(df['Net Kar Yıllık Büyüme (%)'], errors='coerce')
        df['Operasyonel Skor'] += (df['Net Kar Yıllık Büyüme (%)'] > 0).astype(int)
        df['Operasyonel Skor'] += (df['Net Kar Yıllık Büyüme (%)'] > GROWTH_STRONG_THRESHOLD).astype(int)
        
    # 2. Margins
    if 'Brüt Marj (%)' in df.columns:
        df['Brüt Marj (%)'] = pd.to_numeric(df['Brüt Marj (%)'], errors='coerce')
        df['Operasyonel Skor'] += (df['Brüt Marj (%)'] > 0).astype(int)
        
    if 'FAVÖK Marjı (%)' in df.columns:
        df['FAVÖK Marjı (%)'] = pd.to_numeric(df['FAVÖK Marjı (%)'], errors='coerce')
        df['Operasyonel Skor'] += (df['FAVÖK Marjı (%)'] > 0).astype(int)
        
    if 'Net Kar Marjı (%)' in df.columns:
        df['Net Kar Marjı (%)'] = pd.to_numeric(df['Net Kar Marjı (%)'], errors='coerce')
        df['Operasyonel Skor'] += (df['Net Kar Marjı (%)'] > 0).astype(int)
        
    # 3. Solvency (Net Debt & Liquidity)
    if 'Net Borç' in df.columns:
        df['Net Borç'] = pd.to_numeric(df['Net Borç'], errors='coerce')
        df['Operasyonel Skor'] += (df['Net Borç'] < 0).astype(int) * NET_DEBT_CASH_RICH_BONUS  # Cash Rich is a strong sign
        
    if 'Cari Oran' in df.columns:
        df['Operasyonel Skor'] += (df['Cari Oran'] > GRAHAM_CURRENT_RATIO_MIN).astype(int)

    # Calculate Graham Number (Graham Sayısı)
    # Graham Sayısı — TTM normalizasyonlu EPS kullanılıyor
    graham_conditions = (df['EPS_TTM'] > 0) & (df['BVPS_Derived'] > 0)
    df['Graham Sayısı'] = np.where(graham_conditions, np.sqrt(GRAHAM_NUMBER_CONSTANT * df['EPS_TTM'] * df['BVPS_Derived']), np.nan)

    # Sort by Potential Return (Büyükten Küçüğe), keeping NaNs at the end
    df = df.sort_values(by='Potansiyel Getiri (%)', ascending=False, na_position='last')
    
    # Clean up column formatting for presentation
    cols_to_round = ['Hedef Fiyat (F/K)', 'Hedef Fiyat (PD/DD)', 'Hedef Fiyat (ROE)', 
                     'Hedef Fiyat (BIST Ort.)', 'Hedef Fiyat (Sektör PD/DD)', 
                     'Nihai Hedef Fiyat', 'Potansiyel Getiri (%)', 'ROE_Derived',
                     'MA200 Uzaklık (%)', 'RSI (14)', 'Graham Sayısı',
                     'Brüt Marj (%)', 'FAVÖK Marjı (%)', 'Net Kar Marjı (%)',
                     'FAVÖK Yıllık Büyüme (%)', 'Net Kar Yıllık Büyüme (%)', 'Halka Açıklık (%)',
                     'PEG']
    for col in cols_to_round:
        # We need to fillna with None or np.nan before formatting, but actually round handles NaNs gracefully
        if col in df.columns:
            df[col] = df[col].astype(float).round(2)
        
    # Prepare summary statistics to return
    # Calculate Sector F/K Averages for display purposes (even though not used in method 2 due to potential unreliability)
    sector_avg_summary = df.groupby('Sektör').agg(
        Sektör_FK_Ortalama=('F/K', lambda x: x.replace([np.inf, -np.inf], np.nan)[(x > FK_VALID_MIN) & (x < FK_VALID_MAX)].mean()),
        Sektör_PDDD_Ortalama=('PD/DD', lambda x: x.replace([np.inf, -np.inf], np.nan)[(x > PDDD_VALID_MIN) & (x < PDDD_VALID_MAX)].mean()),
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
