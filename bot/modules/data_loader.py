"""
Historical data loader for backtesting
Supports loading from CSV files or fetching from Hyperliquid API
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import requests
import time
import ccxt


class HistoricalDataLoader:
    """Load and manage historical market data for backtesting"""

    def __init__(self, data_dir: str = "data/historical"):
        """
        Initialize data loader

        Args:
            data_dir: Directory to store/load historical data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._spot_cache = {}  # Cache for spot pair indices

    def _get_spot_index(self, token: str) -> Optional[str]:
        """
        Get the spot pair index for a token from Hyperliquid spotMeta

        Args:
            token: Token symbol (e.g., 'ZEC', 'HYPE')

        Returns:
            Spot pair index (e.g., '@107') or None if not found
        """
        # Check cache first
        if token in self._spot_cache:
            return self._spot_cache[token]

        try:
            url = "https://api.hyperliquid.xyz/info"
            payload = {'type': 'spotMeta'}
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            meta = response.json()

            # Find token in universe
            tokens = meta.get('tokens', [])
            universe = meta.get('universe', [])

            # Find token index
            token_index = None
            for idx, t in enumerate(tokens):
                if t.get('name', '').upper() == token.upper():
                    token_index = t.get('index')
                    break

            if token_index is None:
                return None

            # Find spot pair index that has this token paired with USDC (index 0)
            for spot_idx, pair in enumerate(universe):
                if pair.get('tokens') == [token_index, 0]:
                    spot_format = f"@{spot_idx}"
                    self._spot_cache[token] = spot_format
                    print(f"  Found {token} spot index: {spot_format}")
                    return spot_format

            return None

        except Exception as e:
            print(f"  Warning: Could not fetch spot metadata: {e}")
            return None

    def load_from_csv(self, pair: str, timeframe: str = '1m') -> pd.DataFrame:
        """
        Load historical data from CSV file

        Args:
            pair: Trading pair (e.g., 'HYPE/USDC')
            timeframe: Timeframe ('1m', '5m', etc.)

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        filename = self._get_filename(pair, timeframe)
        filepath = self.data_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(
                f"Historical data file not found: {filepath}\n"
                f"Please download data first using download_historical_data()"
            )

        df = pd.read_csv(filepath)

        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        return df

    def download_historical_data(self, pair: str, timeframe: str = '1m',
                                 days_back: int = 30, save: bool = True) -> pd.DataFrame:
        """
        Download historical data from Hyperliquid API

        Args:
            pair: Trading pair (e.g., 'HYPE/USDC')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            days_back: Number of days of historical data to fetch
            save: Whether to save to CSV

        Returns:
            DataFrame with historical data
        """
        print(f"Downloading {days_back} days of {timeframe} data for {pair}...")

        # Convert timeframe to Hyperliquid format
        interval_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }

        hl_interval = interval_map.get(timeframe, '1m')

        # Map trading pairs to Hyperliquid coin format
        # For spot pairs, Hyperliquid uses @{index} format
        # For perpetuals, use coin name directly (e.g., "BTC", "ETH")
        spot_pair_map = {
            'HYPE/USDC': '@107',   # HYPE spot pair index on Hyperliquid mainnet
            'PURR/USDC': 'PURR',   # PURR uses special format
        }

        # Perpetuals (use coin name directly)
        perp_pairs = {
            'BTC/USDC': 'BTC',
            'ETH/USDC': 'ETH',
            'SOL/USDC': 'SOL',
            'AVAX/USDC': 'AVAX',
        }

        # Try spot first, then perp, then query API for spot index
        if pair in spot_pair_map:
            symbol = spot_pair_map[pair]
            print(f"  Using spot pair format: {symbol}")
        elif pair in perp_pairs:
            symbol = perp_pairs[pair]
            print(f"  Using perpetual format: {symbol}")
        else:
            # Try to get spot index from API
            base_token = pair.replace('/', '-').split('-')[0]
            spot_index = self._get_spot_index(base_token)

            if spot_index:
                symbol = spot_index
                print(f"  Using spot pair format: {symbol}")
            else:
                # Final fallback: try base currency name (for perpetuals)
                symbol = base_token
                print(f"  Using fallback format: {symbol} (might be perpetual or fail)")

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        # Calculate how many candles we need
        interval_minutes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        minutes = interval_minutes.get(timeframe, 1)
        target_candles = int((days_back * 24 * 60) / minutes)

        print(f"  Target: {target_candles} candles for {days_back} days")

        # Hyperliquid API endpoint
        url = "https://api.hyperliquid.xyz/info"

        all_candles = []
        current_end_time = end_time
        max_requests = 20  # Safety limit to prevent infinite loops

        print(f"  Fetching data backwards from {end_time.strftime('%Y-%m-%d %H:%M')}")

        # Fetch data in chunks, working backwards from present
        # Strategy: Request with endTime = current point, startTime = far back
        # API returns the LAST 5000 candles in that range
        # Then use oldest candle from response as new endTime
        for request_num in range(max_requests):
            # For the request, use a very early startTime (far in the past)
            # This ensures we get the maximum 5000 candles ending at current_end_time
            far_back_time = current_end_time - timedelta(days=365)  # 1 year back

            # But don't go earlier than what user requested
            request_start = max(far_back_time, start_time)

            payload = {
                'type': 'candleSnapshot',
                'req': {
                    'coin': symbol,
                    'interval': hl_interval,
                    'startTime': int(request_start.timestamp() * 1000),
                    'endTime': int(current_end_time.timestamp() * 1000)
                }
            }

            try:
                response = requests.post(url, json=payload, timeout=30)
                response.raise_for_status()
                candles = response.json()

                if not candles or len(candles) == 0:
                    print(f"  No more data available before {current_end_time.strftime('%Y-%m-%d %H:%M')}")
                    break

                # The API returns candles in chronological order
                # We want to prepend older candles to our collection
                # So add them to the beginning
                all_candles = candles + all_candles

                oldest_candle_time = datetime.fromtimestamp(candles[0]['t'] / 1000)
                newest_candle_time = datetime.fromtimestamp(candles[-1]['t'] / 1000)

                print(f"  [{request_num + 1}] Fetched {len(candles)} candles: {oldest_candle_time.strftime('%Y-%m-%d %H:%M')} to {newest_candle_time.strftime('%Y-%m-%d %H:%M')} (total: {len(all_candles)})")

                # Check if we have enough data
                if len(all_candles) >= target_candles:
                    print(f"  ✓ Reached target of {target_candles} candles")
                    break

                # Check if the oldest candle is before our target start time
                if oldest_candle_time <= start_time:
                    print(f"  ✓ Reached requested start time")
                    break

                # If we got fewer than 4000 candles, we might be hitting the limit
                # (5000 is max, so getting significantly less suggests no more data)
                if len(candles) < 4000:
                    print(f"  ⚠️  Only got {len(candles)} candles - might be at Hyperliquid's data limit")
                    if len(candles) < 100:
                        print(f"  Stopping: too few candles to continue")
                        break

                # Move the window backwards for next request
                # New endTime = oldest candle timestamp minus 1ms to avoid overlap
                oldest_timestamp_ms = candles[0]['t']
                current_end_time = datetime.fromtimestamp((oldest_timestamp_ms - 1) / 1000)

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"  Error fetching data: {e}")
                break

        if not all_candles:
            raise ValueError(f"No data fetched for {pair}")

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'timestamp': pd.to_datetime(c['t'], unit='ms'),
                'open': float(c['o']),
                'high': float(c['h']),
                'low': float(c['l']),
                'close': float(c['c']),
                'volume': float(c['v'])
            }
            for c in all_candles
        ])

        df = df.sort_values('timestamp').reset_index(drop=True)
        df = df.drop_duplicates(subset='timestamp', keep='last')

        print(f"📦 Downloaded {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Check if we have existing historical data to merge with
        if save:
            filename = self._get_filename(pair, timeframe)
            filepath = self.data_dir / filename

            if filepath.exists():
                print(f"📂 Found existing data file, merging with new data...")
                try:
                    old_df = pd.read_csv(filepath)
                    old_df['timestamp'] = pd.to_datetime(old_df['timestamp'])

                    old_count = len(old_df)
                    old_min = old_df['timestamp'].min()
                    old_max = old_df['timestamp'].max()

                    print(f"   Old data: {old_count} candles from {old_min} to {old_max}")

                    # Combine old and new data
                    combined_df = pd.concat([old_df, df], ignore_index=True)

                    # Remove duplicates (keep the newer data)
                    combined_df = combined_df.sort_values('timestamp')
                    combined_df = combined_df.drop_duplicates(subset='timestamp', keep='last')
                    combined_df = combined_df.reset_index(drop=True)

                    # Detect gaps (missing data periods)
                    if len(combined_df) > 1:
                        # Calculate expected time between candles
                        interval_map = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
                        expected_minutes = interval_map.get(timeframe, 1)
                        expected_delta = timedelta(minutes=expected_minutes)

                        # Check for gaps larger than 2x expected interval
                        time_diffs = combined_df['timestamp'].diff()
                        large_gaps = time_diffs[time_diffs > expected_delta * 2]

                        if len(large_gaps) > 0:
                            print(f"   ⚠️  Found {len(large_gaps)} data gaps:")
                            for idx in large_gaps.head(3).index:
                                gap_start = combined_df.loc[idx-1, 'timestamp']
                                gap_end = combined_df.loc[idx, 'timestamp']
                                gap_duration = gap_end - gap_start
                                print(f"      Gap: {gap_start} to {gap_end} ({gap_duration})")
                            if len(large_gaps) > 3:
                                print(f"      ... and {len(large_gaps) - 3} more gaps")

                    # Calculate total coverage
                    total_duration = combined_df['timestamp'].max() - combined_df['timestamp'].min()
                    days_coverage = total_duration.total_seconds() / (24 * 3600)

                    df = combined_df
                    print(f"   ✅ Merged data: {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")
                    print(f"   📊 Total coverage: {days_coverage:.1f} days")

                except Exception as e:
                    print(f"   ⚠️  Error merging old data: {e}")
                    print(f"   Using only new data")

            # Save the final dataset
            df.to_csv(filepath, index=False)
            print(f"💾 Saved to {filepath}")

        return df

    def download_from_binance(self, pair: str, timeframe: str = '1m',
                              days_back: int = 30, save: bool = True) -> pd.DataFrame:
        """
        Download historical data from Binance (using CCXT)
        Binance has much longer history available (years of data)

        Args:
            pair: Trading pair (e.g., 'HYPE/USDC', 'BTC/USDC')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            days_back: Number of days of historical data to fetch
            save: Whether to save to CSV and merge with existing data

        Returns:
            DataFrame with historical data
        """
        print(f"📥 Downloading from Binance: {days_back} days of {timeframe} data for {pair}...")

        # Map pair format (HYPE/USDC → HYPE/USDT for Binance)
        binance_pair = pair.replace('USDC', 'USDT')

        # Determine if we need futures or spot market
        # HYPE is only on Binance Futures, not spot
        use_futures = 'HYPE' in pair.upper()
        market_type = 'future' if use_futures else 'spot'

        print(f"   Using Binance {market_type.upper()}: {binance_pair}")

        # Initialize Binance exchange
        exchange = ccxt.binance({
            'enableRateLimit': True,  # Respect rate limits
            'options': {
                'defaultType': market_type,  # 'spot' or 'future'
            }
        })

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        since = int(start_time.timestamp() * 1000)  # CCXT uses milliseconds

        # Calculate how many candles we need
        interval_minutes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440}
        minutes = interval_minutes.get(timeframe, 1)
        target_candles = int((days_back * 24 * 60) / minutes)

        print(f"   Target: {target_candles} candles from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")

        all_candles = []
        current_since = since
        max_requests = 50  # Safety limit

        try:
            for request_num in range(max_requests):
                # Fetch up to 1000 candles per request (Binance limit)
                ohlcv = exchange.fetch_ohlcv(
                    binance_pair,
                    timeframe=timeframe,
                    since=current_since,
                    limit=1000
                )

                if not ohlcv or len(ohlcv) == 0:
                    print(f"   No more data available")
                    break

                all_candles.extend(ohlcv)

                oldest_time = datetime.fromtimestamp(ohlcv[0][0] / 1000)
                newest_time = datetime.fromtimestamp(ohlcv[-1][0] / 1000)

                print(f"   [{request_num + 1}] Fetched {len(ohlcv)} candles: {oldest_time.strftime('%Y-%m-%d %H:%M')} to {newest_time.strftime('%Y-%m-%d %H:%M')} (total: {len(all_candles)})")

                # Check if we have enough data
                if len(all_candles) >= target_candles:
                    print(f"   ✓ Reached target of {target_candles} candles")
                    break

                # Check if we've reached the present
                if newest_time >= end_time:
                    print(f"   ✓ Reached present time")
                    break

                # Move to next chunk (add 1ms to avoid duplicate)
                current_since = ohlcv[-1][0] + 1

                time.sleep(exchange.rateLimit / 1000)  # Respect rate limit

        except ccxt.NetworkError as e:
            print(f"   ⚠️  Network error: {e}")
            if len(all_candles) == 0:
                raise ValueError(f"Could not fetch data from Binance: {e}")
        except ccxt.ExchangeError as e:
            print(f"   ⚠️  Exchange error: {e}")
            if len(all_candles) == 0:
                raise ValueError(f"Binance error: {e}")
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
            if len(all_candles) == 0:
                raise ValueError(f"Failed to fetch from Binance: {e}")

        if not all_candles:
            raise ValueError(f"No data fetched for {pair} from Binance")

        # Convert to DataFrame
        # CCXT format: [timestamp, open, high, low, close, volume]
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Remove duplicates
        df = df.sort_values('timestamp')
        df = df.drop_duplicates(subset='timestamp', keep='last')
        df = df.reset_index(drop=True)

        print(f"📦 Downloaded {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Merge with existing data if requested
        if save:
            filename = self._get_filename(pair, timeframe)
            filepath = self.data_dir / filename

            if filepath.exists():
                print(f"📂 Found existing data file, merging with new data...")
                try:
                    old_df = pd.read_csv(filepath)
                    old_df['timestamp'] = pd.to_datetime(old_df['timestamp'])

                    old_count = len(old_df)
                    old_min = old_df['timestamp'].min()
                    old_max = old_df['timestamp'].max()

                    print(f"   Old data: {old_count} candles from {old_min} to {old_max}")

                    # Combine old and new data
                    combined_df = pd.concat([old_df, df], ignore_index=True)

                    # Remove duplicates (keep the newer data)
                    combined_df = combined_df.sort_values('timestamp')
                    combined_df = combined_df.drop_duplicates(subset='timestamp', keep='last')
                    combined_df = combined_df.reset_index(drop=True)

                    # Calculate total coverage
                    total_duration = combined_df['timestamp'].max() - combined_df['timestamp'].min()
                    days_coverage = total_duration.total_seconds() / (24 * 3600)

                    df = combined_df
                    print(f"   ✅ Merged data: {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")
                    print(f"   📊 Total coverage: {days_coverage:.1f} days")

                except Exception as e:
                    print(f"   ⚠️  Error merging old data: {e}")
                    print(f"   Using only new data")

            # Save the final dataset
            df.to_csv(filepath, index=False)
            print(f"💾 Saved to {filepath}")

        return df

    def generate_sample_data(self, pair: str, timeframe: str = '1m',
                            days: int = 30, save: bool = True) -> pd.DataFrame:
        """
        Generate synthetic market data for testing (random walk with trends)

        Args:
            pair: Trading pair
            timeframe: Timeframe
            days: Number of days to generate
            save: Whether to save to CSV

        Returns:
            DataFrame with synthetic data
        """
        print(f"Generating {days} days of synthetic {timeframe} data for {pair}...")

        # Calculate number of candles
        interval_minutes = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '1h': 60,
            '4h': 240,
            '1d': 1440
        }

        minutes = interval_minutes.get(timeframe, 1)
        num_candles = int((days * 24 * 60) / minutes)

        # Starting price
        base_price = 25.0 if 'HYPE' in pair else 45.0

        timestamps = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        current_time = datetime.now() - timedelta(days=days)
        current_price = base_price

        for i in range(num_candles):
            # Random walk with slight trend
            trend = np.sin(i / 100) * 0.002  # Cyclical trend
            change = np.random.normal(trend, 0.01)  # Random change ±1%

            open_price = current_price
            close_price = current_price * (1 + change)

            # High and low
            high_price = max(open_price, close_price) * np.random.uniform(1.0, 1.015)
            low_price = min(open_price, close_price) * np.random.uniform(0.985, 1.0)

            # Volume
            volume = np.random.uniform(100000, 500000)

            timestamps.append(current_time)
            opens.append(open_price)
            highs.append(high_price)
            lows.append(low_price)
            closes.append(close_price)
            volumes.append(volume)

            current_price = close_price
            current_time += timedelta(minutes=minutes)

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })

        print(f"Generated {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Save to CSV
        if save:
            filename = self._get_filename(pair, timeframe)
            filepath = self.data_dir / filename
            df.to_csv(filepath, index=False)
            print(f"Saved to {filepath}")

        return df

    def resample_timeframe(self, df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """
        Resample data to a different timeframe

        Args:
            df: DataFrame with 1m data
            target_timeframe: Target timeframe ('5m', '15m', '1h', etc.)

        Returns:
            Resampled DataFrame
        """
        df = df.copy()
        df = df.set_index('timestamp')

        # Resample rules (using 'min' instead of deprecated 'T')
        resample_map = {
            '5m': '5min',
            '15m': '15min',
            '1h': '1H',
            '4h': '4H',
            '1d': '1D'
        }

        rule = resample_map.get(target_timeframe, '5min')

        resampled = df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        resampled = resampled.reset_index()

        return resampled

    def _get_filename(self, pair: str, timeframe: str) -> str:
        """Generate filename for pair and timeframe"""
        pair_clean = pair.replace('/', '_')
        return f"{pair_clean}_{timeframe}.csv"

    def list_available_data(self) -> List[Dict[str, str]]:
        """
        List all available historical data files

        Returns:
            List of dicts with pair, timeframe, filepath info
        """
        files = []
        for filepath in self.data_dir.glob("*.csv"):
            # Parse filename: HYPE_USDC_1m.csv
            parts = filepath.stem.split('_')
            if len(parts) >= 3:
                pair = f"{parts[0]}/{parts[1]}"
                timeframe = parts[2]

                # Get file info
                df = pd.read_csv(filepath)

                files.append({
                    'pair': pair,
                    'timeframe': timeframe,
                    'filepath': str(filepath),
                    'candles': len(df),
                    'start': df['timestamp'].min(),
                    'end': df['timestamp'].max()
                })

        return files
