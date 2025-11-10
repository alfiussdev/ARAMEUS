"""
Backtest script for Aggressive Compound Bot v1.2
Run strategy backtests on historical data
"""

import argparse
import sys
from pathlib import Path
import json

from bot.config import Config
from bot.modules.data_loader import HistoricalDataLoader
from bot.modules.backtester import Backtester
from bot.modules.performance_metrics import PerformanceMetrics


def main():
    """Main backtest entry point"""

    parser = argparse.ArgumentParser(
        description='Backtest Aggressive Compound Bot v1.2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate sample data and run backtest
  python backtest.py --generate-data --pair HYPE/USDC --days 30

  # Download 30 days from Binance (default, unlimited history)
  python backtest.py --download-data --pair HYPE/USDC --days 30

  # Download from Binance explicitly
  python backtest.py --download-data --source binance --pair HYPE/USDC --days 30

  # Download from Hyperliquid (~3.5 days max for 1m)
  python backtest.py --download-data --source hyperliquid --pair HYPE/USDC --days 30

  # Run backtest on existing CSV data
  python backtest.py --pair HYPE/USDC

  # Run backtest with custom parameters
  python backtest.py --pair HYPE/USDC --equity 50000 --leverage 8

  # Save detailed report
  python backtest.py --pair HYPE/USDC --save-report
        """
    )

    # Data options
    parser.add_argument('--pair', type=str, default='HYPE/USDC',
                       help='Trading pair (default: HYPE/USDC)')
    parser.add_argument('--generate-data', action='store_true',
                       help='Generate synthetic data before backtest')
    parser.add_argument('--download-data', action='store_true',
                       help='Download real data from exchange')
    parser.add_argument('--source', type=str, default='binance', choices=['hyperliquid', 'binance'],
                       help='Data source: binance (default, unlimited history) or hyperliquid (~3.5 days)')
    parser.add_argument('--days', type=int, default=30,
                       help='Days of historical data (default: 30)')

    # Backtest parameters
    parser.add_argument('--equity', type=float, default=10000,
                       help='Initial equity in USDC (default: 10000)')
    parser.add_argument('--leverage', type=int,
                       help='Override default leverage')
    parser.add_argument('--max-equity-per-trade', type=float,
                       help='Override max equity per trade (0-1)')

    # Output options
    parser.add_argument('--save-report', action='store_true',
                       help='Save detailed report to file')
    parser.add_argument('--save-trades', action='store_true',
                       help='Save individual trades to CSV')
    parser.add_argument('--list-data', action='store_true',
                       help='List available historical data files')

    args = parser.parse_args()

    # Print header
    print("\n" + "=" * 70)
    print("  AGGRESSIVE COMPOUND BOT v1.2 - BACKTEST ENGINE")
    print("=" * 70)

    # Initialize data loader
    data_loader = HistoricalDataLoader()

    # List available data
    if args.list_data:
        print("\n📁 Available Historical Data:\n")
        files = data_loader.list_available_data()

        if not files:
            print("  No historical data files found.")
            print("  Run with --generate-data or --download-data to create data.\n")
        else:
            for file in files:
                print(f"  • {file['pair']} ({file['timeframe']})")
                print(f"    Candles: {file['candles']}")
                print(f"    Period: {file['start']} to {file['end']}")
                print(f"    File: {file['filepath']}\n")
        return

    # Generate or download data if requested
    if args.generate_data:
        print(f"\n🔧 Generating synthetic data for {args.pair}...")
        data_1m = data_loader.generate_sample_data(
            pair=args.pair,
            timeframe='1m',
            days=args.days,
            save=True
        )
        # Generate 5m data
        data_5m = data_loader.resample_timeframe(data_1m, '5m')
        pair_clean = args.pair.replace('/', '_')
        data_5m.to_csv(f"data/historical/{pair_clean}_5m.csv", index=False)

    elif args.download_data:
        source_name = args.source.capitalize()
        print(f"\n📥 Downloading data from {source_name} for {args.pair}...")
        try:
            if args.source == 'binance':
                # Download from Binance (unlimited history)
                data_1m = data_loader.download_from_binance(
                    pair=args.pair,
                    timeframe='1m',
                    days_back=args.days,
                    save=True
                )
                # Download 5m data
                data_5m = data_loader.download_from_binance(
                    pair=args.pair,
                    timeframe='5m',
                    days_back=args.days,
                    save=True
                )
            else:  # hyperliquid
                # Download from Hyperliquid (~5000 candles limit)
                data_1m = data_loader.download_historical_data(
                    pair=args.pair,
                    timeframe='1m',
                    days_back=args.days,
                    save=True
                )
                # Download 5m data
                data_5m = data_loader.download_historical_data(
                    pair=args.pair,
                    timeframe='5m',
                    days_back=args.days,
                    save=True
                )
        except Exception as e:
            print(f"\n❌ Error downloading data: {e}")
            print("Try using --generate-data for synthetic data instead.\n")
            sys.exit(1)

    # Load data
    try:
        print(f"\n📊 Loading data for {args.pair}...")
        data_1m = data_loader.load_from_csv(args.pair, '1m')
        print(f"  Loaded {len(data_1m)} candles (1m)")

        try:
            data_5m = data_loader.load_from_csv(args.pair, '5m')
            print(f"  Loaded {len(data_5m)} candles (5m)")
        except FileNotFoundError:
            print("  No 5m data found, will resample from 1m")
            data_5m = data_loader.resample_timeframe(data_1m, '5m')

    except FileNotFoundError:
        print(f"\n❌ No data found for {args.pair}")
        print("Run with --generate-data or --download-data first.\n")
        sys.exit(1)

    # Override config if specified
    if args.leverage:
        Config.DEFAULT_LEVERAGE = args.leverage
        print(f"  Using custom leverage: {args.leverage}x")

    if args.max_equity_per_trade:
        Config.MAX_EQUITY_PER_TRADE = args.max_equity_per_trade
        print(f"  Using custom max equity per trade: {args.max_equity_per_trade * 100}%")

    # Initialize backtester
    print(f"\n🚀 Initializing backtester...")
    backtester = Backtester(Config, initial_equity=args.equity)

    # Run backtest
    results = backtester.run(data_1m, data_5m, pair=args.pair)

    # Calculate and display metrics
    metrics_calc = PerformanceMetrics(results['trades'], args.equity)
    metrics = results['metrics']

    # Print summary
    metrics_calc.print_summary(metrics)

    # Save report if requested
    if args.save_report:
        report_path = Path('reports') / f"backtest_{args.pair.replace('/', '_')}_{int(datetime.now().timestamp())}.json"
        report_path.parent.mkdir(exist_ok=True)

        report = {
            'pair': args.pair,
            'initial_equity': args.equity,
            'final_equity': results['final_equity'],
            'config': {
                'leverage': Config.DEFAULT_LEVERAGE,
                'max_equity_per_trade': Config.MAX_EQUITY_PER_TRADE,
                'risk_reward_ratio': Config.RISK_REWARD_RATIO
            },
            'metrics': metrics,
            'total_trades': len(results['trades'])
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n💾 Report saved to: {report_path}")

    # Save trades if requested
    if args.save_trades:
        import pandas as pd

        trades_path = Path('reports') / f"trades_{args.pair.replace('/', '_')}_{int(datetime.now().timestamp())}.csv"
        trades_df = pd.DataFrame(results['trades'])
        trades_df.to_csv(trades_path, index=False)

        print(f"💾 Trades saved to: {trades_path}")

    # Save equity curve
    equity_df = metrics_calc.get_equity_curve()
    equity_path = Path('reports') / f"equity_curve_{args.pair.replace('/', '_')}_{int(datetime.now().timestamp())}.csv"
    equity_df.to_csv(equity_path, index=False)
    print(f"💾 Equity curve saved to: {equity_path}")

    print("\n" + "=" * 70)
    print("  BACKTEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    from datetime import datetime
    main()
