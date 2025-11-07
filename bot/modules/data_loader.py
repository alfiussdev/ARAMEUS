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
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '1h': '60',
            '4h': '240',
            '1d': '1D'
        }

        hl_interval = interval_map.get(timeframe, '1')
        symbol = pair.replace('/', '-').split('-')[0]  # HYPE from HYPE/USDC

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        # Hyperliquid API endpoint
        url = "https://api.hyperliquid.xyz/info"

        all_candles = []
        current_start = start_time

        # Fetch data in chunks (max 5000 candles per request)
        while current_start < end_time:
            payload = {
                'type': 'candleSnapshot',
                'req': {
                    'coin': symbol,
                    'interval': hl_interval,
                    'startTime': int(current_start.timestamp() * 1000),
                    'endTime': int(end_time.timestamp() * 1000)
                }
            }

            try:
                response = requests.post(url, json=payload, timeout=30)
                response.raise_for_status()
                candles = response.json()

                if not candles:
                    break

                all_candles.extend(candles)

                # Move to next chunk
                last_timestamp = candles[-1]['t']
                current_start = datetime.fromtimestamp(last_timestamp / 1000)

                print(f"  Fetched {len(candles)} candles (total: {len(all_candles)})")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"Error fetching data: {e}")
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

        print(f"Downloaded {len(df)} candles from {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Save to CSV
        if save:
            filename = self._get_filename(pair, timeframe)
            filepath = self.data_dir / filename
            df.to_csv(filepath, index=False)
            print(f"Saved to {filepath}")

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
