from portfolio_opt import optimize_portfolio

test_tickers = ["THYAO", "EREGL", "TUPRS", "FROTO"]
# Simulate some fundamentally calculated expected returns (e.g. THYAO very cheap, FROTO expensive)
expected_returns = {
    "THYAO": 0.85,
    "EREGL": 0.35,
    "TUPRS": 0.40,
    "FROTO": -0.10
}

weights, perf, warning = optimize_portfolio(test_tickers, custom_returns_dict=expected_returns)
print("Weights:", weights)
print("Performance:", perf)
print("Warning (if any):", warning)
