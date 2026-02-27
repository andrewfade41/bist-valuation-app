import yfinance as yf
import pandas as pd
from pypfopt import expected_returns, risk_models
from pypfopt.efficient_frontier import EfficientFrontier
import datetime

def optimize_portfolio(tickers, custom_returns_dict=None):
    """
    Given a list of BIST tickers (e.g. ['THYAO', 'TUPRS']) and an optional dictionary of their expected 
    future returns (e.g. {'THYAO': 0.45, 'TUPRS': 0.15}), fetches last 2 years of daily data for risk calculation,
    and returns the optimal Sharpe ratio portfolio weights and its expected performance.
    """
    if not tickers:
        return None, "Portföyde hisse bulunamadı.", None
        
    # Format tickers for yfinance (BIST stocks usually have .IS suffix)
    yf_tickers = []
    for t in tickers:
        t = t.strip().upper()
        if not t.endswith('.IS'):
            yf_tickers.append(f"{t}.IS")
        else:
            yf_tickers.append(t)
            
    # Calculate date range (last 2 years)
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365 * 2)
    
    try:
        # Fetch historical data
        df = yf.download(yf_tickers, start=start_date, end=end_date)['Close']
        if df.empty:
            return None, "Veri indirilemedi.", None
            
        # If downloaded exactly one ticker, yfinance returns a Series instead of DataFrame columns
        if len(yf_tickers) == 1:
            return None, "Optimizasyon için en az 2 hisse senedi gereklidir.", None
            
        # Drop rows with all NaNs
        df = df.dropna(how='all')
        
        # Calculate sample covariance matrix (Risk stays based on past 2 years of daily data)
        S = risk_models.sample_cov(df)
        
        # Calculate expected returns
        if custom_returns_dict and isinstance(custom_returns_dict, dict):
            # Use user-provided fundamental analysis expectations instead of past price movements
            # Warning: PyPortfolioOpt expects a pd.Series indexed by the exact ticker names in df.columns (e.g., 'THYAO.IS')
            mu_dict = {}
            for t_raw, expected_return in custom_returns_dict.items():
                t_formatted = f"{t_raw.strip().upper()}.IS" if not t_raw.endswith('.IS') else t_raw.strip().upper()
                mu_dict[t_formatted] = expected_return
            
            # Create a Series matching the downloaded data's columns. Fallback to 0 if a ticker is missing in dict
            mu = pd.Series([mu_dict.get(col, 0.0) for col in df.columns], index=df.columns)
        else:
            # Fallback to standard historical data performance if no custom dictionary is provided
            mu = expected_returns.mean_historical_return(df)
            
        # Optimize for maximal Sharpe ratio
        ef = EfficientFrontier(mu, S)
        
        # Determine the maximum expected return amongst the assets
        max_mu = mu.max()
        
        # PyPortfolioOpt default risk_free_rate is 0.02. 
        # If all assets perform worse than the risk free rate, it will throw an error.
        # We adjust the risk free rate to be slightly lower than the max return, or 0.0 if returns are negative.
        adjusted_risk_free = 0.02
        warning_msg = None
        
        if max_mu <= 0.02:
            adjusted_risk_free = max_mu - 0.01 if max_mu > 0 else 0.0
            
        try:
            # Try to get the optimal Sharpe portfolio
            raw_weights = ef.max_sharpe(risk_free_rate=adjusted_risk_free)
        except Exception as sharpe_err:
            # If it still fails (usually due to highly volatile negative returns), fallback to Min Volatility
            ef = EfficientFrontier(mu, S) # Re-init to reset constraints
            raw_weights = ef.min_volatility()
            warning_msg = "⚠️ Filtrelenen hisseler içerisinde Markowitz'in getiri/risk beklentisine (Sharpe) uygun pozitif/güçlü trende sahip hisse bulunamadı. Bu nedenle getiri yerine en risksiz (Minimum Volatilite) dağılım hesaplandı."
            
        cleaned_weights = ef.clean_weights()
        
        # Calculate expected performance
        # returns: expected annual return, std: annual volatility, sharpe: Sharpe ratio
        expected_annual_return, annual_volatility, sharpe_ratio = ef.portfolio_performance(risk_free_rate=adjusted_risk_free)
        
        # Format weights for output, remove .IS suffix for display
        weights_dict = {k.replace('.IS', ''): v for k, v in cleaned_weights.items() if v > 0.001}
        
        performance = {
            'expected_return': expected_annual_return,
            'volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio
        }
        
        return weights_dict, performance, warning_msg
        
    except Exception as e:
        return None, f"Optimizasyon sırasında hata oluştu: {str(e)}", None
