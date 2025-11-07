# Aggressive Compound Bot v1.2 - ARCANUM

**Advanced algorithmic trading bot for Hyperliquid perpetual contracts**

Trading HYPE/USDC and ZEC/USDC with momentum-based strategies, multi-timeframe analysis, and sophisticated risk management.

---

## 🎯 Overview

The Aggressive Compound Bot (ARCANUM) is a systematic trading bot designed to capitalize on strong directional movements in cryptocurrency derivatives markets. It combines multiple technical indicators, multi-timeframe analysis, and adaptive risk management to identify high-probability trading opportunities while strictly controlling downside risk.

### Key Features

- ✅ **Multi-filter entry system**: 7+ simultaneous conditions for trade entry
- ✅ **Adaptive position sizing**: Based on ATR volatility ratio
- ✅ **Dynamic stop loss and take profit**: Calculated from current market volatility
- ✅ **Partial profit taking**: TP1 at 50% + trailing stop for remainder
- ✅ **Signal invalidation**: Early exit when conditions reverse
- ✅ **Global risk controls**: Loss streak cooldown, daily/global drawdown limits
- ✅ **Comprehensive logging**: Structured JSON logs for all trades and decisions
- ✅ **Dry run mode**: Test strategies without risking capital

---

## 📊 Trading Strategy

### Timeframes
- **Primary**: 1-minute candles for entry/exit signals
- **Confirmation**: 5-minute candles for structural context

### Indicators Used

| Indicator | Period | Purpose |
|-----------|--------|---------|
| SMA50 | 50 | Macro trend identification |
| SMA200 | 200 | Long-term trend filter |
| EMA9 | 9 | Fast momentum |
| EMA20 | 20 | Slow momentum |
| RSI | 14 | Directional momentum strength |
| VWAP | Session | Institutional bias |
| ATR | 14 | Volatility measurement |
| Volume | 20, 3 | Participation validation |

### Entry Conditions

#### LONG Entry
All conditions must be satisfied:
1. **Trend**: SMA50 > SMA200
2. **Momentum**: EMA9 > EMA20
3. **Institutional bias**: Price > VWAP
4. **RSI**: > 55 (healthy bullish momentum)
5. **Volume**: Current > 1.8× 20-period avg AND > 1.2× 3-period avg
6. **5m structure**: Close_5m > Open_5m (bullish 5m candle)
7. **Spread**: ≤ 0.15% (sufficient liquidity)

#### SHORT Entry
All conditions must be satisfied:
1. **Trend**: SMA50 < SMA200
2. **Momentum**: EMA9 < EMA20
3. **Institutional bias**: Price < VWAP
4. **RSI**: < 45 (healthy bearish momentum)
5. **Volume**: Current > 1.8× 20-period avg AND > 1.2× 3-period avg
6. **5m structure**: Close_5m < Open_5m (bearish 5m candle)
7. **Spread**: ≤ 0.15% (sufficient liquidity)

### Position Management

#### Entry
- **Leverage**: 8x-12x (adaptive based on volatility)
- **Margin per trade**: 10-20% of equity (adaptive)
- **Stop loss**: 0.5% × volatility_ratio (max 5% of margin)
- **Position size**: **Inversely proportional to volatility_ratio** (keeps dollar risk constant)
- **Take profit**: 2.2× stop loss distance (R:R = 2.2:1)

**Key Principle**: When volatility increases, the bot uses **wider stops + smaller positions** to maintain constant dollar risk:
- High volatility (ratio > 1.5): Wider stops (e.g., 0.75%) + Smaller position (÷ 1.5)
- Normal volatility (ratio ~1.0): Normal stops (0.5%) + Normal position
- Low volatility (ratio < 0.9): Tighter stops (e.g., 0.45%) + Larger position (÷ 0.9)

#### Exit Management
1. **TP1 (50% close)**: When price reaches TP1
   - Close 50% of position
   - Move stop loss to breakeven
   - Activate trailing stop for remainder

2. **Trailing Stop**: After TP1
   - Distance = ATR × volatility_ratio
   - Tracks highest/lowest price reached

3. **Stop Loss**: Fixed at entry
   - Before TP1: Original stop loss
   - After TP1: Breakeven

4. **Invalidation**: Early exit if:
   - LONG: EMA9 ≤ EMA20 OR Price < VWAP OR RSI < 50
   - SHORT: EMA9 ≥ EMA20 OR Price > VWAP OR RSI > 50

### Risk Management

#### Per-Trade Risk
- Max margin per trade: 20% of equity
- Max loss per trade: 5% of margin (~1% of equity)
- **Constant dollar risk**: Position size scales inversely with volatility
  - Formula: `position_size = (margin × leverage) / volatility_ratio / entry_price`
  - This ensures: `risk_in_dollars = position_size × stop_distance` stays constant

#### Global Risk Controls
1. **Loss Streak Cooldown**
   - After 3 consecutive losses
   - No new trades for 12 hours
   - Existing positions managed normally

2. **Daily Drawdown Limit**
   - -15% from day start equity
   - No new trades until next day
   - Existing positions managed normally

3. **Global Drawdown Limit**
   - -25% from all-time peak equity
   - **BOT SHUTDOWN** (manual restart required)
   - This is a circuit breaker for catastrophic scenarios

---

## 🏗️ Architecture

```
ARAMEUS/
├── bot/
│   ├── __init__.py
│   ├── config.py                    # Configuration management
│   └── modules/
│       ├── __init__.py
│       ├── logger.py                # Structured logging
│       ├── data_feed.py             # Hyperliquid API integration
│       ├── indicators.py            # Technical indicators
│       ├── signal_engine.py         # Entry signal logic
│       ├── risk_manager.py          # Position sizing & risk calc
│       ├── execution_engine.py      # Order execution
│       ├── position_manager.py      # TP/SL/trailing management
│       └── risk_controls.py         # Global risk limits
├── logs/                            # Trading logs
├── data/                            # Persistent state
├── main.py                          # Main bot entry point
├── requirements.txt
├── .env.example
└── README.md
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `config.py` | Load and validate configuration from environment |
| `logger.py` | Structured JSON logging for trades and system events |
| `data_feed.py` | Fetch market data, orderbook, account state from Hyperliquid |
| `indicators.py` | Calculate all technical indicators (SMA, EMA, RSI, VWAP, ATR) |
| `signal_engine.py` | Evaluate entry signals and invalidation conditions |
| `risk_manager.py` | Calculate position size, SL, TP, P&L, trade quality |
| `execution_engine.py` | Place and manage orders (market, stop, limit) |
| `position_manager.py` | Monitor positions, handle TP1, trailing stops |
| `risk_controls.py` | Enforce global risk limits (streaks, drawdowns) |

---

## 🚀 Installation

### Prerequisites
- Python 3.9+
- Hyperliquid account (testnet or mainnet)
- API credentials

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd ARAMEUS
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

### Environment Configuration

Edit `.env` with your settings:

```env
# API Credentials (required for live trading)
HYPERLIQUID_API_KEY=your_api_key
HYPERLIQUID_SECRET_KEY=your_secret_key
HYPERLIQUID_WALLET_ADDRESS=your_wallet_address

# Mode
DRY_RUN=true          # Set to false for live trading
TESTNET=false         # Set to true for testnet

# Trading pairs
TRADING_PAIRS=HYPE/USDC,ZEC/USDC

# Risk parameters (adjust carefully)
DEFAULT_LEVERAGE=10
MAX_EQUITY_PER_TRADE=0.20
LOSS_STREAK_LIMIT=3
DAILY_DRAWDOWN_LIMIT=0.15
GLOBAL_DRAWDOWN_LIMIT=0.25
```

---

## 📊 Backtesting (Test Without Risk!)

Before risking real capital, **backtest your strategy** on historical data:

```bash
# Generate sample data and run backtest
python backtest.py --generate-data --pair HYPE/USDC --days 30
```

This will:
- Generate 30 days of market data
- Run the complete trading strategy
- Show detailed performance metrics
- **No wallet or API keys required!**

### Quick Backtest Commands

```bash
# Download real data from Hyperliquid
python backtest.py --download-data --pair HYPE/USDC --days 60

# Run backtest with custom parameters
python backtest.py --pair HYPE/USDC --equity 50000 --leverage 8

# Save detailed report
python backtest.py --pair HYPE/USDC --save-report --save-trades

# List available data
python download_data.py --list
```

### What You'll See

```
📊 OVERVIEW
  Initial Equity:    $10,000.00
  Final Equity:      $12,450.00
  Total Return:      24.50%
  Total Trades:      45

📈 RETURNS
  Sharpe Ratio:      1.85
  Sortino Ratio:     2.31
  Max Drawdown:      -8.50%

🎯 TRADE ANALYSIS
  Win Rate:          62.22%
  Profit Factor:     2.15
  Avg R-Multiple:    1.85R
```

**📖 For complete backtesting guide, see [BACKTESTING.md](BACKTESTING.md)**

---

## 💻 Usage

### Dry Run Mode (Recommended for testing)

```bash
python main.py
```

This mode uses simulated data and does not place real orders. Perfect for:
- Testing the bot logic
- Validating configuration
- Understanding the strategy

### Live Trading

**⚠️ WARNING: Live trading involves real capital at risk**

1. Ensure you understand the strategy completely
2. Test thoroughly in dry run mode
3. Start with small position sizes
4. Set `.env`:
```env
DRY_RUN=false
```

4. Run:
```bash
python main.py
```

### Monitoring

The bot logs extensively to:
- **Console**: Real-time system events
- **`logs/bot_YYYYMMDD.log`**: All system events
- **`logs/trades_YYYYMMDD.log`**: Trade entries/exits with full details
- **`logs/daily_summaries.log`**: Daily performance summaries

### Stopping the Bot

Use `Ctrl+C` for graceful shutdown. The bot will:
- Stop looking for new entries
- Log final statistics
- Save state (positions remain open unless manually closed)

---

## 📈 Performance Tracking

### Real-time Metrics

The bot tracks:
- Equity (current and peak)
- Open positions with unrealized P&L
- Daily P&L and drawdown
- Global drawdown from peak
- Loss streak counter
- Win rate and profit factor

### Log Analysis

All trades are logged with:
- Entry/exit timestamps and prices
- Position size, margin, leverage
- All indicator values at entry
- Which filters passed/failed
- Exit reason (TP1, TRAILING, STOP_LOSS, INVALIDATION)
- P&L (gross, net, fees)
- R-multiple achieved
- Trade quality assessment

Use these logs to:
- Analyze strategy performance
- Identify optimal parameters
- Detect issues or edge cases
- Generate performance reports

---

## ⚙️ Configuration Reference

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DEFAULT_LEVERAGE` | 10 | Base leverage multiplier |
| `MAX_EQUITY_PER_TRADE` | 0.20 | Max 20% of equity as margin per trade |
| `BASE_SL_PCT` | 0.005 | Base stop loss 0.5% (adjusted by ATR) |
| `RISK_REWARD_RATIO` | 2.2 | TP/SL ratio |
| `LOSS_STREAK_LIMIT` | 3 | Consecutive losses before cooldown |
| `COOLDOWN_HOURS` | 12 | Hours to wait after loss streak |
| `DAILY_DRAWDOWN_LIMIT` | 0.15 | 15% daily loss limit |
| `GLOBAL_DRAWDOWN_LIMIT` | 0.25 | 25% global loss limit (shutdown) |
| `RSI_LONG_THRESHOLD` | 55 | Minimum RSI for long entry |
| `RSI_SHORT_THRESHOLD` | 45 | Maximum RSI for short entry |
| `VOL_MULTIPLIER_20` | 1.8 | Volume vs 20-period average |
| `VOL_MULTIPLIER_3` | 1.2 | Volume vs 3-period average |
| `MAX_SPREAD` | 0.0015 | Maximum spread 0.15% |

### Volatility Adaptation

The bot adjusts position size and leverage based on `volatility_ratio = ATR_current / ATR_mean`:

| Volatility Ratio | Margin Used | Leverage |
|------------------|-------------|----------|
| < 0.9 (Low) | 10% | 12x |
| 0.9 - 1.5 (Normal) | 20% | 10x |
| > 1.5 (High) | 15% | 8x |

---

## 🔒 Security

### API Keys
- Never commit `.env` to version control
- Use read-only API keys when possible
- Rotate keys regularly
- Use IP whitelisting if available

### Risk Limits
- Always run in dry run mode first
- Start with conservative position sizes
- Monitor the bot actively, especially initially
- Set up alerts for equity drawdowns

---

## 🐛 Troubleshooting

### "Failed to connect to Hyperliquid API"
- Check your internet connection
- Verify API credentials in `.env`
- Check if Hyperliquid API is operational
- Try testnet mode first

### "Configuration error"
- Ensure all required fields in `.env` are set
- Check that numeric values are valid
- Verify leverage settings (MIN ≤ DEFAULT ≤ MAX)

### "Not enough data for indicators"
- Bot needs 200+ candles for SMA200
- Wait a few minutes for data collection
- Check logs for progress updates

### Bot not entering trades
- Check risk controls status in logs
- Verify you're not in cooldown period
- Check if daily/global drawdown limits reached
- Review signal logs to see which filters are failing

---

## 📝 Development

### Adding New Pairs

Edit `.env`:
```env
TRADING_PAIRS=HYPE/USDC,ZEC/USDC,BTC/USDC
```

### Customizing Strategy

Key files to modify:
- **Entry logic**: `bot/modules/signal_engine.py`
- **Position sizing**: `bot/modules/risk_manager.py`
- **Exit logic**: `bot/modules/position_manager.py`
- **Risk limits**: `bot/modules/risk_controls.py`

### Testing

```bash
# Run with verbose logging
LOG_LEVEL=DEBUG python main.py

# Simulate specific market conditions
# Modify SimulatedDataFeed in data_feed.py
```

---

## ⚠️ Disclaimer

**This bot is provided for educational and research purposes only.**

- Trading cryptocurrencies and derivatives involves substantial risk of loss
- Past performance does not guarantee future results
- The bot may have bugs or behave unexpectedly
- You are solely responsible for your trading decisions
- Use at your own risk
- The authors assume no liability for any losses incurred

**Always:**
- Understand the code before running it
- Test thoroughly in dry run mode
- Start with small position sizes
- Never risk more than you can afford to lose
- Monitor the bot actively

---

## 📄 License

[Specify your license here]

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

---

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing documentation
- Review logs for error details

---

## 🎯 Roadmap

Potential future enhancements:
- [ ] WebSocket streaming for real-time data
- [ ] Multi-exchange support
- [ ] Web dashboard for monitoring
- [ ] Advanced order types (iceberg, TWAP)
- [ ] Machine learning signal optimization
- [ ] Backtesting framework
- [ ] Portfolio-level risk management
- [ ] Telegram/Discord notifications

---

**Built with ❤️ for algorithmic trading**

*Version 1.2.0 - Last updated: 2025-01-06*
