from portfolio_opt import optimize_portfolio

tickers = ["THYAO", "EREGL", "SISE", "TUPRS"]
weights, perf = optimize_portfolio(tickers)

print("Weights:")
print(weights)
print("Performance:")
print(perf)
