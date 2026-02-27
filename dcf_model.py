import yfinance as yf
import pandas as pd

def calculate_dcf(ticker: str, growth_rate_1_5: float, growth_rate_6_10: float, discount_rate: float, perpetual_growth_rate: float = 0.02):
    """
    Calculates the Intrinsic Value of a stock using the Discounted Cash Flow (DCF) model.
    Fetch financial data using yfinance.
    
    Args:
        ticker (str): The stock ticker symbol (e.g., 'THYAO'). '.IS' will be added automatically if missing.
        growth_rate_1_5 (float): Expected annual growth rate for years 1-5 (e.g., 0.15 for 15%).
        growth_rate_6_10 (float): Expected annual growth rate for years 6-10 (e.g., 0.10 for 10%).
        discount_rate (float): The discount rate or WACC (e.g., 0.25 for 25%).
        perpetual_growth_rate (float): Terminal growth rate after 10 years (e.g., 0.02 for 2%).
        
    Returns:
        tuple: (intrinsic_value_per_share, current_price, details_dict, error_msg)
    """
    try:
        # Format for BIST stocks
        t_clean = ticker.strip().upper()
        t_yf = f"{t_clean}.IS" if not t_clean.endswith('.IS') else t_clean
        
        info = yf.Ticker(t_yf).info
        
        # Required DCF Inputs
        fcf = info.get('freeCashflow')
        total_debt = info.get('totalDebt', 0)
        total_cash = info.get('totalCash', 0)
        shares_out = info.get('sharesOutstanding')
        current_price = info.get('currentPrice')
        
        if fcf is None or shares_out is None or current_price is None:
            return None, None, None, f"{t_clean} için gerekli bilanço verileri yfinance üzerinden eksik geldi (Eksik FCF veya Hisse Adedi)."
            
        if fcf <= 0:
             return None, current_price, None, f"{t_clean} şirketinin güncel Serbest Nakit Akımı ({fcf:,.0f} ₺) negatiftir. DCF modeli kurulamıyor."
            
        # Project Phase 1: Years 1-5
        projected_fcf = []
        current_fcf = fcf
        
        for year in range(1, 6):
            current_fcf *= (1 + growth_rate_1_5)
            projected_fcf.append(current_fcf)
            
        # Project Phase 2: Years 6-10
        for year in range(6, 11):
            current_fcf *= (1 + growth_rate_6_10)
            projected_fcf.append(current_fcf)
            
        # Discount the projected cash flows
        pv_fcf = []
        for i, cf in enumerate(projected_fcf):
            year = i + 1
            pv = cf / ((1 + discount_rate) ** year)
            pv_fcf.append(pv)
            
        sum_pv_fcf = sum(pv_fcf)
        
        # Calculate Terminal Value (Gordon Growth Model)
        terminal_value = (projected_fcf[-1] * (1 + perpetual_growth_rate)) / (discount_rate - perpetual_growth_rate)
        pv_terminal_value = terminal_value / ((1 + discount_rate) ** 10)
        
        # Calculate Enterprise Value
        enterprise_value = sum_pv_fcf + pv_terminal_value
        
        # Calculate Equity Value (Enterprise Value + Cash - Debt)
        equity_value = enterprise_value + total_cash - total_debt
        
        # Calculate Intrinsic Value per Share
        intrinsic_value = equity_value / shares_out
        
        details = {
            'Güncel Serbest Nakit Akımı (FCF)': fcf,
            'Nakitler': total_cash,
            'Borçlar': total_debt,
            'Sermaye Senedi / Ödenmiş': shares_out,
            'İşletme Değeri (PV FCF + TV)': enterprise_value,
            'Sermaye Değeri (Equity)': equity_value
        }
        
        return intrinsic_value, current_price, details, None
        
    except Exception as e:
        return None, None, None, f"DCF hesaplanırken hata oluştu: {str(e)}"
