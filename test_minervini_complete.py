from data_fetcher import fetch_bist_fundamentals
from calculator import calculate_fair_values

df_raw = fetch_bist_fundamentals()
if df_raw is not None:
    df_calc, stats = calculate_fair_values(df_raw)
    minervini_stocks = df_calc[df_calc['Minervini_Uyumlu'] == True]
    print(f"Total stocks: {len(df_calc)}")
    print(f"Minervini compliant stocks: {len(minervini_stocks)}")
    if len(minervini_stocks) > 0:
        print(minervini_stocks[['Kod', 'Kapanış (TL)', 'MA50', 'MA150', 'MA200', '52 Haftalık Zirve', '52 Haftalık Dip']].head())
