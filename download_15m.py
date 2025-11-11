"""
Quick script to download 15m timeframe data from Binance
"""
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time

def download_15m(pair: str = 'SOL/USDC', days: int = 60):
    """Download 15m candles from Binance"""

    print(f"\n📥 Downloading {pair} 15m data from Binance...")
    print(f"Period: {days} days")

    # Initialize Binance
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })

    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    # Convert to milliseconds
    since = int(start_time.timestamp() * 1000)

    # Fetch candles
    all_candles = []
    print(f"Fetching candles from {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}...")

    while True:
        try:
            candles = exchange.fetch_ohlcv(pair, '15m', since=since, limit=1000)

            if not candles:
                break

            all_candles.extend(candles)

            # Update since to last candle timestamp
            since = candles[-1][0] + 1

            # Check if we've reached the end
            if candles[-1][0] >= int(end_time.timestamp() * 1000):
                break

            print(f"  Downloaded {len(all_candles)} candles...", end='\r')
            time.sleep(0.5)  # Rate limit

        except Exception as e:
            print(f"\n❌ Error: {e}")
            break

    if not all_candles:
        print("\n❌ No data downloaded")
        return

    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Save to CSV
    pair_clean = pair.replace('/', '_')
    filename = f"data/historical/{pair_clean}_15m.csv"
    df.to_csv(filename, index=False)

    print(f"\n✅ Downloaded {len(df)} candles")
    print(f"💾 Saved to: {filename}")
    print(f"Period: {df['timestamp'].min()} to {df['timestamp'].max()}")

if __name__ == '__main__':
    download_15m('SOL/USDC', 60)
