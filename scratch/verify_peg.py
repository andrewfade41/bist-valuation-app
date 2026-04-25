import pandas as pd
import numpy as np
from calculator import calculate_fair_values

def test_peg_calculation():
    # Mock data
    data = {
        'Kod': ['TEST1', 'TEST2', 'TEST3'],
        'Kapanış (TL)': [100, 200, 300],
        'F/K': [10.0, 20.0, 5.0],
        'PD/DD': [1.5, 2.0, 1.0],
        'Net Kar Yıllık Büyüme (%)': [20.0, -10.0, 0.0], # Positive, Negative, Zero
        'Son Dönem': ['12/2025', '12/2025', '12/2025'],
        'Sektör': ['Tech', 'Finance', 'Energy']
    }
    df = pd.DataFrame(data)
    
    # Calculate
    df_calc, _ = calculate_fair_values(df)
    
    print("Calculated PEG values:")
    for i, row in df_calc.iterrows():
        print(f"Ticker: {row['Kod']}, Growth: {row['Net Kar Yıllık Büyüme (%)']}, FK: {row['F/K']}, PEG: {row['PEG']}")
        
    # Assertions
    # TEST1: 10 / 20 = 0.5
    assert df_calc.loc[df_calc['Kod']=='TEST1', 'PEG'].iloc[0] == 0.5
    # TEST2: Negative growth -> NaN
    assert np.isnan(df_calc.loc[df_calc['Kod']=='TEST2', 'PEG'].iloc[0])
    # TEST3: Zero growth -> NaN
    assert np.isnan(df_calc.loc[df_calc['Kod']=='TEST3', 'PEG'].iloc[0])
    
    print("\nTests passed!")

if __name__ == "__main__":
    test_peg_calculation()
