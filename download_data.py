"""
Data download utility for backtesting
Downloads historical data from Hyperliquid or generates synthetic data
"""

import argparse
from bot.modules.data_loader import HistoricalDataLoader


def main():
    parser = argparse.ArgumentParser(description='Download historical data for backtesting')

    parser.add_argument('--pairs', type=str, default='HYPE/USDC,ZEC/USDC',
                       help='Comma-separated list of pairs (default: HYPE/USDC,ZEC/USDC)')
    parser.add_argument('--days', type=int, default=30,
                       help='Days of historical data (default: 30)')
    parser.add_argument('--synthetic', action='store_true',
                       help='Generate synthetic data instead of downloading')
    parser.add_argument('--list', action='store_true',
                       help='List available data files')

    args = parser.parse_args()

    data_loader = HistoricalDataLoader()

    # List existing data
    if args.list:
        print("\n📁 Available Historical Data:\n")
        files = data_loader.list_available_data()

        if not files:
            print("  No data files found.\n")
        else:
            for file in files:
                print(f"  • {file['pair']} ({file['timeframe']})")
                print(f"    Candles: {file['candles']}")
                print(f"    Period: {file['start']} to {file['end']}")
                print(f"    File: {file['filepath']}\n")
        return

    # Parse pairs
    pairs = [p.strip() for p in args.pairs.split(',')]

    print(f"\n{'='*70}")
    print(f"  DATA DOWNLOAD UTILITY")
    print(f"{'='*70}\n")

    for pair in pairs:
        print(f"Processing {pair}...")

        if args.synthetic:
            # Generate synthetic data
            print(f"  Generating synthetic data ({args.days} days)...")
            data_1m = data_loader.generate_sample_data(
                pair=pair,
                timeframe='1m',
                days=args.days,
                save=True
            )

            # Resample to 5m
            data_5m = data_loader.resample_timeframe(data_1m, '5m')
            pair_clean = pair.replace('/', '_')
            data_5m.to_csv(f"data/historical/{pair_clean}_5m.csv", index=False)
            print(f"  ✓ Generated {len(data_1m)} candles (1m)")
            print(f"  ✓ Generated {len(data_5m)} candles (5m)")

        else:
            # Download from Hyperliquid
            try:
                print(f"  Downloading from Hyperliquid ({args.days} days)...")

                # Download 1m data
                data_1m = data_loader.download_historical_data(
                    pair=pair,
                    timeframe='1m',
                    days_back=args.days,
                    save=True
                )

                # Download 5m data
                data_5m = data_loader.download_historical_data(
                    pair=pair,
                    timeframe='5m',
                    days_back=args.days,
                    save=True
                )

                print(f"  ✓ Downloaded {len(data_1m)} candles (1m)")
                print(f"  ✓ Downloaded {len(data_5m)} candles (5m)")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                print(f"  Try using --synthetic flag for synthetic data")

        print()

    print(f"{'='*70}")
    print(f"  Download complete!")
    print(f"  Run 'python download_data.py --list' to see available data")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
