# 📊 Backtesting Guide - Aggressive Compound Bot v1.2

Complete guide for backtesting trading strategies without risking real capital.

---

## 🎯 What is Backtesting?

Backtesting allows you to test the trading strategy on historical data to:
- ✅ Evaluate strategy performance before going live
- ✅ Calculate potential returns and risks
- ✅ Optimize parameters (leverage, stop loss, etc.)
- ✅ Identify weaknesses in the strategy
- ✅ Build confidence in the system

**No wallet or API keys required!**

---

## 🚀 Quick Start

### 1. Generate Sample Data and Run Backtest

```bash
# Generate 30 days of synthetic data and run backtest
python backtest.py --generate-data --pair HYPE/USDC --days 30
```

This will:
1. Create synthetic market data (random walk with trends)
2. Save it to `data/historical/`
3. Run a complete backtest
4. Display performance metrics

### 2. Download Real Data (Optional)

```bash
# Download real data from Hyperliquid
python backtest.py --download-data --pair HYPE/USDC --days 30
```

### 3. Run Backtest on Existing Data

```bash
# Use previously downloaded/generated data
python backtest.py --pair HYPE/USDC
```

---

## 📥 Data Management

### Download Data for Multiple Pairs

```bash
# Download data for both HYPE and ZEC
python download_data.py --pairs "HYPE/USDC,ZEC/USDC" --days 60
```

### Generate Synthetic Data

```bash
# Generate synthetic data (useful for testing)
python download_data.py --pairs "HYPE/USDC,ZEC/USDC" --days 90 --synthetic
```

### List Available Data

```bash
# See what data you have
python download_data.py --list
```

Output example:
```
📁 Available Historical Data:

  • HYPE/USDC (1m)
    Candles: 43200
    Period: 2024-12-07 to 2025-01-06
    File: data/historical/HYPE_USDC_1m.csv

  • HYPE/USDC (5m)
    Candles: 8640
    Period: 2024-12-07 to 2025-01-06
    File: data/historical/HYPE_USDC_5m.csv
```

---

## 🎛️ Backtest Parameters

### Basic Parameters

```bash
# Custom initial equity
python backtest.py --pair HYPE/USDC --equity 50000

# Different time period
python backtest.py --pair HYPE/USDC --days 60

# Save detailed report
python backtest.py --pair HYPE/USDC --save-report --save-trades
```

### Strategy Parameters

```bash
# Test with different leverage
python backtest.py --pair HYPE/USDC --leverage 8

# Test with different risk per trade
python backtest.py --pair HYPE/USDC --max-equity-per-trade 0.10

# Combine parameters
python backtest.py --pair HYPE/USDC --equity 100000 --leverage 12 --max-equity-per-trade 0.15
```

---

## 📈 Understanding Results

### Console Output

After running a backtest, you'll see:

```
======================================================================
  BACKTEST PERFORMANCE SUMMARY
======================================================================

📊 OVERVIEW
  Initial Equity:    $10,000.00
  Final Equity:      $12,450.00
  Total P&L:         $2,450.00
  Total Return:      24.50%
  Total Trades:      45
  Total Fees:        $125.50

📈 RETURNS
  Sharpe Ratio:      1.85
  Sortino Ratio:     2.31
  Calmar Ratio:      3.42
  Annualized Return: 312.50%

⚠️  RISK METRICS
  Max Drawdown:      -8.50%
  Max DD Duration:   3 days
  VaR (95%):         $-45.00

🎯 TRADE ANALYSIS
  Win Rate:          62.22%
  Winning Trades:    28
  Losing Trades:     17
  Profit Factor:     2.15
  Avg Win:           $120.50
  Avg Loss:          $65.30
  Avg R-Multiple:    1.85R
  Expectancy:        $54.44
  Best Trade:        $385.00
  Worst Trade:       $-125.00

⏱️  TIME ANALYSIS
  Avg Trade Duration: 2.5 hours
  Total Trading Days: 30
  Trades per Day:     1.50

🔥 STREAKS
  Max Win Streak:    7
  Max Loss Streak:   4

======================================================================
```

### Key Metrics Explained

| Metric | What It Means | Good Value |
|--------|---------------|------------|
| **Total Return** | Overall profit/loss | Positive |
| **Sharpe Ratio** | Risk-adjusted returns | > 1.5 |
| **Sortino Ratio** | Downside risk-adjusted returns | > 2.0 |
| **Max Drawdown** | Largest peak-to-trough decline | < 20% |
| **Win Rate** | % of profitable trades | > 50% |
| **Profit Factor** | Gross profit / Gross loss | > 1.5 |
| **Avg R-Multiple** | Average risk/reward achieved | > 1.0 |
| **Expectancy** | Average $ per trade | Positive |

---

## 📁 Generated Files

Backtests generate several files in the `reports/` directory:

### 1. Backtest Report (JSON)
```bash
reports/backtest_HYPE_USDC_1704585600.json
```

Contains:
- Complete metrics
- Configuration used
- Summary statistics

### 2. Individual Trades (CSV)
```bash
reports/trades_HYPE_USDC_1704585600.csv
```

Columns:
- `pair`, `side`, `entry_price`, `exit_price`
- `entry_time`, `exit_time`, `duration_minutes`
- `pnl_net`, `pnl_pct`, `r_multiple`
- `exit_reason`, `tp1_hit`

### 3. Equity Curve (CSV)
```bash
reports/equity_curve_HYPE_USDC_1704585600.csv
```

Track your balance over time:
- `timestamp`, `equity`

---

## 🔬 Strategy Optimization

### Testing Different Parameters

Create a script to test multiple configurations:

```python
# optimize.py
from bot.config import Config
from bot.modules.data_loader import HistoricalDataLoader
from bot.modules.backtester import Backtester

# Load data once
data_loader = HistoricalDataLoader()
data_1m = data_loader.load_from_csv('HYPE/USDC', '1m')
data_5m = data_loader.load_from_csv('HYPE/USDC', '5m')

# Test different leverage values
results = []

for leverage in [8, 10, 12]:
    Config.DEFAULT_LEVERAGE = leverage

    backtester = Backtester(Config, initial_equity=10000)
    result = backtester.run(data_1m, data_5m, pair='HYPE/USDC')

    results.append({
        'leverage': leverage,
        'final_equity': result['final_equity'],
        'sharpe': result['metrics']['returns']['sharpe_ratio'],
        'max_dd': result['metrics']['risk']['max_drawdown_pct']
    })

# Find best configuration
best = max(results, key=lambda x: x['sharpe'])
print(f"Best leverage: {best['leverage']}x")
print(f"Sharpe Ratio: {best['sharpe']:.2f}")
```

### Parameter Grid Search

```python
# Test combinations
configs = [
    {'leverage': 8, 'max_equity': 0.10},
    {'leverage': 10, 'max_equity': 0.15},
    {'leverage': 12, 'max_equity': 0.20},
]

for config in configs:
    # Run backtest with each config
    # Compare results
```

---

## 📊 Analyzing Results

### Import Data into Spreadsheet

```bash
# Save trades to CSV
python backtest.py --pair HYPE/USDC --save-trades
```

Open in Excel/Google Sheets to:
- Create pivot tables
- Generate charts
- Filter by exit reason
- Analyze time of day patterns

### Python Analysis

```python
import pandas as pd

# Load trades
df = pd.read_csv('reports/trades_HYPE_USDC_xxx.csv')

# Analyze by exit reason
exit_reasons = df.groupby('exit_reason').agg({
    'pnl_net': ['sum', 'mean', 'count']
})
print(exit_reasons)

# Winners vs Losers
winners = df[df['pnl_net'] > 0]
losers = df[df['pnl_net'] <= 0]

print(f"Avg winner: ${winners['pnl_net'].mean():.2f}")
print(f"Avg loser: ${losers['pnl_net'].mean():.2f}")

# Plot equity curve
equity = pd.read_csv('reports/equity_curve_HYPE_USDC_xxx.csv')
equity.plot(x='timestamp', y='equity')
```

---

## 🎨 Visualization

### Create Equity Curve Chart

```python
import matplotlib.pyplot as plt
import pandas as pd

# Load equity curve
df = pd.read_csv('reports/equity_curve_HYPE_USDC_xxx.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Plot
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp'], df['equity'], linewidth=2)
plt.title('Equity Curve - HYPE/USDC Backtest')
plt.xlabel('Date')
plt.ylabel('Equity (USDC)')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('equity_curve.png')
plt.show()
```

### Drawdown Chart

```python
# Calculate drawdowns
df['peak'] = df['equity'].cummax()
df['drawdown'] = (df['equity'] - df['peak']) / df['peak'] * 100

plt.figure(figsize=(12, 6))
plt.fill_between(df['timestamp'], df['drawdown'], 0, alpha=0.3, color='red')
plt.plot(df['timestamp'], df['drawdown'], color='red', linewidth=1)
plt.title('Drawdown % - HYPE/USDC Backtest')
plt.xlabel('Date')
plt.ylabel('Drawdown %')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('drawdown.png')
plt.show()
```

---

## ⚠️ Important Considerations

### Backtesting Limitations

1. **No Slippage (minimal)**: Real execution may differ
2. **Perfect Data**: Assumes clean, accurate historical data
3. **No Black Swans**: Can't predict unprecedented events
4. **Look-Ahead Bias**: Be careful not to use future information
5. **Overfitting**: Don't optimize too much for historical data

### Best Practices

✅ **DO**:
- Test on out-of-sample data
- Use realistic parameters
- Account for fees and slippage
- Test different market conditions
- Validate assumptions

❌ **DON'T**:
- Over-optimize for past data
- Ignore risk metrics (focus only on returns)
- Assume backtest results guarantee future performance
- Skip testing edge cases
- Use unrealistic leverage or position sizes

---

## 🔧 Advanced Usage

### Custom Data Sources

```python
# Use your own CSV files
import pandas as pd

# Load custom data
df = pd.read_csv('my_custom_data.csv')

# Ensure required columns
required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
assert all(col in df.columns for col in required)

# Save in correct format
df.to_csv('data/historical/CUSTOM_PAIR_1m.csv', index=False)

# Run backtest
python backtest.py --pair CUSTOM/PAIR
```

### Walk-Forward Analysis

Test on different time periods:

```bash
# Month 1
python backtest.py --pair HYPE/USDC --days 30

# Month 2
python backtest.py --pair HYPE/USDC --days 60

# Month 3
python backtest.py --pair HYPE/USDC --days 90
```

Compare consistency across periods.

---

## 📚 Examples

### Example 1: Conservative Strategy

```bash
python backtest.py \
  --pair HYPE/USDC \
  --equity 10000 \
  --leverage 8 \
  --max-equity-per-trade 0.10 \
  --save-report
```

### Example 2: Aggressive Strategy

```bash
python backtest.py \
  --pair HYPE/USDC \
  --equity 50000 \
  --leverage 12 \
  --max-equity-per-trade 0.20 \
  --save-report
```

### Example 3: Multiple Pairs Comparison

```bash
# Test HYPE
python backtest.py --pair HYPE/USDC --save-report

# Test ZEC
python backtest.py --pair ZEC/USDC --save-report

# Compare reports
```

---

## 🆘 Troubleshooting

### "No data found"
```bash
# Generate data first
python download_data.py --pairs "HYPE/USDC" --days 30 --synthetic
```

### "Not enough data"
```bash
# Need at least 200 candles for SMA200
python download_data.py --pairs "HYPE/USDC" --days 7 --synthetic  # Minimum
```

### "Error downloading data"
```bash
# Use synthetic data instead
python backtest.py --generate-data --pair HYPE/USDC --days 30
```

---

## 📖 Next Steps

After backtesting:

1. ✅ **Analyze results** - Review metrics and trades
2. ✅ **Optimize parameters** - Test different configurations
3. ✅ **Validate robustness** - Test on different periods
4. ✅ **Calculate risk** - Understand maximum drawdown
5. ✅ **Compare alternatives** - Test variations of the strategy
6. ✅ **Document findings** - Keep notes on what works
7. ✅ **Paper trade** - Test in dry run mode (see main README)
8. ✅ **Start small** - Begin with minimal capital if going live

---

**Remember**: Past performance does not guarantee future results. Backtesting is a tool for analysis, not a crystal ball. Always test thoroughly and start with capital you can afford to lose.

---

*For live trading setup, see the main [README.md](README.md)*
