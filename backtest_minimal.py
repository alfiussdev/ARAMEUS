"""
Minimal strategy backtest for structural testing
Tests only basic trend and volume filters to identify if issue is structural
"""

import argparse
import pandas as pd
from datetime import datetime, timedelta

from bot.config import Config
from bot.modules.data_loader import DataLoader
from bot.modules.indicators import IndicatorEngine
from bot.modules.mock_logger import MockLogger


def run_minimal_backtest(pair: str, days: int = 30):
    """
    Run minimal strategy test with only:
    - Trend filter (SMA50 > SMA200)
    - Basic volume filter (volume > average)

    This helps identify if 0 trades is due to filters or structural issues.
    """
    print(f"\n{'='*70}")
    print(f"  MINIMAL STRATEGY TEST - {pair}")
    print(f"  Testing only: trend filter + volume filter")
    print(f"{'='*70}\n")

    # Load configuration
    config = Config()

    # Load data
    print(f"Loading {days} days of data for {pair}...")
    data_loader = DataLoader()

    # Calculate start date
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Load 1-minute data
    data_1m = data_loader.load_hyperliquid_data(
        pair=pair,
        start_date=start_date,
        end_date=end_date,
        timeframe='1m'
    )

    if data_1m.empty:
        print(f"ERROR: No data loaded for {pair}")
        return

    print(f"Loaded {len(data_1m)} candles from {data_1m['timestamp'].min()} to {data_1m['timestamp'].max()}\n")

    # Initialize indicator engine
    indicator_engine = IndicatorEngine(config)

    # Warm up period
    warmup_candles = 200
    print(f"Warming up indicators ({warmup_candles} candles)...")

    for i in range(warmup_candles):
        candle = {
            'timestamp': data_1m.iloc[i]['timestamp'],
            'open': float(data_1m.iloc[i]['open']),
            'high': float(data_1m.iloc[i]['high']),
            'low': float(data_1m.iloc[i]['low']),
            'close': float(data_1m.iloc[i]['close']),
            'volume': float(data_1m.iloc[i]['volume'])
        }
        indicator_engine.update_candles(pair, candle, '1m')

    print(f"Starting minimal strategy test...\n")

    # Track signals
    long_signals = 0
    short_signals = 0
    total_candles = 0

    # Process candles
    for i in range(warmup_candles, min(warmup_candles + 5000, len(data_1m))):
        candle = {
            'timestamp': data_1m.iloc[i]['timestamp'],
            'open': float(data_1m.iloc[i]['open']),
            'high': float(data_1m.iloc[i]['high']),
            'low': float(data_1m.iloc[i]['low']),
            'close': float(data_1m.iloc[i]['close']),
            'volume': float(data_1m.iloc[i]['volume'])
        }
        indicator_engine.update_candles(pair, candle, '1m')

        # Calculate indicators
        indicators = indicator_engine.calculate_all_indicators(pair)
        if not indicators:
            continue

        total_candles += 1

        # MINIMAL FILTERS ONLY
        # 1. Trend filter: SMA50 vs SMA200
        trend_bullish = indicators['sma50'] > indicators['sma200']
        trend_bearish = indicators['sma50'] < indicators['sma200']

        # 2. Basic volume filter
        volume_ok = indicators['volume_current'] > indicators['volume_mean_20']

        # Log every 100th candle
        if total_candles % 100 == 0:
            print(f"[{total_candles}] {candle['timestamp']} | "
                  f"SMA50={indicators['sma50']:.2f} | SMA200={indicators['sma200']:.2f} | "
                  f"trend_bullish={trend_bullish} | trend_bearish={trend_bearish} | "
                  f"volume_ok={volume_ok} (vol={indicators['volume_current']:.0f}, avg={indicators['volume_mean_20']:.0f})")

        # Check for minimal signals
        if trend_bullish and volume_ok:
            long_signals += 1
            print(f"✓ [{total_candles}] {candle['timestamp']} | MINIMAL LONG SIGNAL | "
                  f"SMA50={indicators['sma50']:.2f} > SMA200={indicators['sma200']:.2f} | "
                  f"volume={indicators['volume_current']:.0f} > avg={indicators['volume_mean_20']:.0f}")

        if trend_bearish and volume_ok:
            short_signals += 1
            print(f"✓ [{total_candles}] {candle['timestamp']} | MINIMAL SHORT SIGNAL | "
                  f"SMA50={indicators['sma50']:.2f} < SMA200={indicators['sma200']:.2f} | "
                  f"volume={indicators['volume_current']:.0f} > avg={indicators['volume_mean_20']:.0f}")

    # Summary
    print(f"\n{'='*70}")
    print(f"  MINIMAL STRATEGY TEST RESULTS")
    print(f"  Candles processed: {total_candles}")
    print(f"  Long signals (trend + volume): {long_signals}")
    print(f"  Short signals (trend + volume): {short_signals}")
    print(f"  Total signals: {long_signals + short_signals}")
    print(f"{'='*70}\n")

    if long_signals == 0 and short_signals == 0:
        print("⚠️  WARNING: Even minimal strategy produced 0 signals!")
        print("   This suggests a STRUCTURAL issue:")
        print("   - Data feed may be missing or corrupted")
        print("   - Indicators may not be calculating correctly")
        print("   - Time window may be too restrictive")
        print("   - Pair configuration may be incorrect\n")
    else:
        print("✓ Minimal strategy CAN generate signals.")
        print("  The issue is likely with the additional filters in the full strategy.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run minimal strategy backtest for debugging')
    parser.add_argument('--pair', type=str, default='HYPE/USDC',
                       help='Trading pair (default: HYPE/USDC)')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days to backtest (default: 30)')

    args = parser.parse_args()

    run_minimal_backtest(args.pair, args.days)
