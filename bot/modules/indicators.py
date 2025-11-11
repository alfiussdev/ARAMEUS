"""
Technical indicators module for the trading bot
Calculates SMA, EMA, RSI, VWAP, ATR, and volume-based indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from collections import deque


class IndicatorEngine:
    """Calculate technical indicators for trading signals"""

    def __init__(self, config):
        """
        Initialize the indicator engine

        Args:
            config: Configuration object with indicator periods
        """
        self.config = config

        # Indicator periods
        self.sma_short_period = config.SMA_SHORT_PERIOD  # 50
        self.sma_long_period = config.SMA_LONG_PERIOD    # 200
        self.ema_fast_period = config.EMA_FAST_PERIOD    # 9
        self.ema_slow_period = config.EMA_SLOW_PERIOD    # 20
        self.rsi_period = config.RSI_PERIOD              # 14
        self.atr_period = config.ATR_PERIOD              # 14
        self.atr_mean_period = config.ATR_MEAN_PERIOD    # 50
        self.vol_mean_20 = config.VOL_MEAN_PERIOD_20     # 20
        self.vol_mean_3 = config.VOL_MEAN_PERIOD_3       # 3

        # Buffers to store historical data (per pair)
        self.candle_buffer: Dict[str, deque] = {}
        self.candle_5m_buffer: Dict[str, deque] = {}

    def update_candles(self, pair: str, candle: Dict[str, Any], timeframe: str = '1m'):
        """
        Update candle buffer for a trading pair

        Args:
            pair: Trading pair symbol
            candle: Candle data dict with keys: timestamp, open, high, low, close, volume
            timeframe: Timeframe ('1m' or '5m')
        """
        if timeframe == '1m':
            if pair not in self.candle_buffer:
                # Need enough history for longest indicator (SMA200)
                self.candle_buffer[pair] = deque(maxlen=self.sma_long_period + 50)
            self.candle_buffer[pair].append(candle)
        elif timeframe == '5m':
            if pair not in self.candle_5m_buffer:
                # Need enough history for EMA20 on 5m
                self.candle_5m_buffer[pair] = deque(maxlen=50)
            self.candle_5m_buffer[pair].append(candle)

    def calculate_sma(self, closes: np.ndarray, period: int) -> float:
        """
        Calculate Simple Moving Average

        Args:
            closes: Array of closing prices
            period: Period for SMA calculation

        Returns:
            float: SMA value
        """
        if len(closes) < period:
            return np.nan
        return np.mean(closes[-period:])

    def calculate_ema(self, closes: np.ndarray, period: int) -> float:
        """
        Calculate Exponential Moving Average

        Args:
            closes: Array of closing prices
            period: Period for EMA calculation

        Returns:
            float: EMA value
        """
        if len(closes) < period:
            return np.nan

        # Use pandas for EMA calculation
        df = pd.DataFrame({'close': closes})
        ema = df['close'].ewm(span=period, adjust=False).mean()
        return ema.iloc[-1]

    def calculate_rsi(self, closes: np.ndarray, period: int) -> float:
        """
        Calculate Relative Strength Index

        Args:
            closes: Array of closing prices
            period: Period for RSI calculation (typically 14)

        Returns:
            float: RSI value (0-100)
        """
        if len(closes) < period + 1:
            return np.nan

        # Calculate price changes
        deltas = np.diff(closes)

        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate average gains and losses
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_vwap(self, candles: List[Dict[str, Any]]) -> float:
        """
        Calculate Volume Weighted Average Price for the current session

        Args:
            candles: List of candle dictionaries

        Returns:
            float: VWAP value
        """
        if not candles:
            return np.nan

        # Calculate typical price for each candle
        total_volume = 0
        total_pv = 0

        for candle in candles:
            typical_price = (candle['high'] + candle['low'] + candle['close']) / 3
            volume = candle['volume']
            total_pv += typical_price * volume
            total_volume += volume

        if total_volume == 0:
            return np.nan

        return total_pv / total_volume

    def calculate_atr(self, candles: List[Dict[str, Any]], period: int) -> float:
        """
        Calculate Average True Range

        Args:
            candles: List of candle dictionaries
            period: Period for ATR calculation (typically 14)

        Returns:
            float: ATR value
        """
        if len(candles) < period + 1:
            return np.nan

        true_ranges = []

        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i - 1]['close']

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        # Return average of last 'period' true ranges
        return np.mean(true_ranges[-period:])

    def calculate_adx(self, candles: List[Dict[str, Any]], period: int = 14) -> float:
        """
        Calculate Average Directional Index (ADX)
        ADX measures trend strength (0-100), regardless of direction
        Values > 25 indicate trending market, < 20 indicate ranging market

        Args:
            candles: List of candle dictionaries
            period: Period for ADX calculation (typically 14)

        Returns:
            float: ADX value (0-100)
        """
        if len(candles) < period * 2:
            return np.nan

        # Calculate +DM and -DM
        plus_dm = []
        minus_dm = []
        true_ranges = []

        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_high = candles[i - 1]['high']
            prev_low = candles[i - 1]['low']
            prev_close = candles[i - 1]['close']

            # Directional movement
            high_diff = high - prev_high
            low_diff = prev_low - low

            # +DM: upward movement
            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
            else:
                plus_dm.append(0)

            # -DM: downward movement
            if low_diff > high_diff and low_diff > 0:
                minus_dm.append(low_diff)
            else:
                minus_dm.append(0)

            # True Range
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        # Convert to numpy arrays
        plus_dm = np.array(plus_dm)
        minus_dm = np.array(minus_dm)
        true_ranges = np.array(true_ranges)

        # Smooth using exponential moving average (Wilder's smoothing)
        # First value is simple average
        plus_di_values = []
        minus_di_values = []

        for i in range(period - 1, len(plus_dm)):
            atr_val = np.mean(true_ranges[i - period + 1:i + 1])
            plus_dm_smooth = np.mean(plus_dm[i - period + 1:i + 1])
            minus_dm_smooth = np.mean(minus_dm[i - period + 1:i + 1])

            if atr_val > 0:
                plus_di = 100 * (plus_dm_smooth / atr_val)
                minus_di = 100 * (minus_dm_smooth / atr_val)
                plus_di_values.append(plus_di)
                minus_di_values.append(minus_di)
            else:
                plus_di_values.append(0)
                minus_di_values.append(0)

        if not plus_di_values:
            return np.nan

        # Calculate DX (Directional Index)
        dx_values = []
        for plus_di, minus_di in zip(plus_di_values, minus_di_values):
            di_sum = plus_di + minus_di
            if di_sum > 0:
                dx = 100 * abs(plus_di - minus_di) / di_sum
                dx_values.append(dx)
            else:
                dx_values.append(0)

        if len(dx_values) < period:
            return np.nan

        # ADX is smoothed average of DX
        adx = np.mean(dx_values[-period:])

        return adx

    def calculate_all_indicators(self, pair: str) -> Optional[Dict[str, Any]]:
        """
        Calculate all indicators for a trading pair

        Args:
            pair: Trading pair symbol

        Returns:
            Dict with all indicator values, or None if not enough data
        """
        if pair not in self.candle_buffer:
            return None

        candles = list(self.candle_buffer[pair])

        # Need at least SMA200 + some buffer
        if len(candles) < self.sma_long_period:
            return None

        # Extract close prices
        closes = np.array([c['close'] for c in candles])

        # Calculate moving averages
        sma50 = self.calculate_sma(closes, self.sma_short_period)
        sma200 = self.calculate_sma(closes, self.sma_long_period)
        ema9 = self.calculate_ema(closes, self.ema_fast_period)
        ema20 = self.calculate_ema(closes, self.ema_slow_period)

        # Calculate RSI
        rsi = self.calculate_rsi(closes, self.rsi_period)

        # Calculate VWAP (using candles from current session)
        vwap = self.calculate_vwap(candles)

        # Calculate ATR
        atr_current = self.calculate_atr(candles, self.atr_period)

        # Calculate ATR mean (average of ATR values over last 50 periods)
        atr_values = []
        for i in range(len(candles) - self.atr_period - self.atr_mean_period, len(candles) - self.atr_period):
            if i > 0:
                atr_val = self.calculate_atr(candles[:i + self.atr_period], self.atr_period)
                if not np.isnan(atr_val):
                    atr_values.append(atr_val)

        atr_mean = np.mean(atr_values) if atr_values else atr_current

        # Calculate volatility ratio
        vol_ratio = atr_current / atr_mean if atr_mean > 0 else 1.0
        vol_ratio = np.clip(vol_ratio, self.config.VOL_RATIO_MIN, self.config.VOL_RATIO_MAX)

        # Market Regime Filter: Calculate ATR for regime detection
        atr_short = np.nan
        atr_long = np.nan
        regime_atr_ratio = np.nan
        adx = np.nan

        if self.config.ENABLE_REGIME_FILTER:
            # Calculate ATR_20 and ATR_100 for regime detection
            atr_short = self.calculate_atr(candles, self.config.ATR_SHORT_PERIOD)
            atr_long = self.calculate_atr(candles, self.config.ATR_LONG_PERIOD)

            # Calculate regime ratio
            if not np.isnan(atr_short) and not np.isnan(atr_long) and atr_long > 0:
                regime_atr_ratio = atr_short / atr_long

        if self.config.ENABLE_ADX_FILTER:
            # Calculate ADX for trend strength
            adx = self.calculate_adx(candles, self.config.ADX_PERIOD)

        # Volume calculations
        volumes = np.array([c['volume'] for c in candles])
        vol_current = volumes[-1]
        vol_mean_20 = np.mean(volumes[-self.vol_mean_20:]) if len(volumes) >= self.vol_mean_20 else vol_current
        vol_mean_3 = np.mean(volumes[-self.vol_mean_3:]) if len(volumes) >= self.vol_mean_3 else vol_current

        # Current price
        current_close = candles[-1]['close']

        # 5-minute candle data (if available)
        candles_5m_data = {}
        if pair in self.candle_5m_buffer and len(self.candle_5m_buffer[pair]) > 0:
            candles_5m = list(self.candle_5m_buffer[pair])
            last_5m_candle = candles_5m[-1]

            candles_5m_data = {
                'open_5m': last_5m_candle['open'],
                'high_5m': last_5m_candle['high'],
                'low_5m': last_5m_candle['low'],
                'close_5m': last_5m_candle['close'],
                'volume_5m': last_5m_candle['volume']
            }

            # Calculate EMA20 on 5m if enough data
            if len(candles_5m) >= 20:
                closes_5m = np.array([c['close'] for c in candles_5m])
                ema20_5m = self.calculate_ema(closes_5m, 20)
                candles_5m_data['ema20_5m'] = ema20_5m

        return {
            # Moving averages
            'sma50': sma50,
            'sma200': sma200,
            'ema9': ema9,
            'ema20': ema20,

            # RSI
            'rsi': rsi,

            # VWAP
            'vwap': vwap,

            # ATR and volatility
            'atr_current': atr_current,
            'atr_mean': atr_mean,
            'volatility_ratio': vol_ratio,

            # Market Regime Filter
            'atr_short': atr_short,
            'atr_long': atr_long,
            'regime_atr_ratio': regime_atr_ratio,
            'adx': adx,

            # Volume
            'volume_current': vol_current,
            'volume_mean_20': vol_mean_20,
            'volume_mean_3': vol_mean_3,

            # Current price
            'current_close': current_close,

            # 5-minute data
            **candles_5m_data
        }

    def has_enough_data(self, pair: str) -> bool:
        """
        Check if we have enough historical data to calculate indicators

        Args:
            pair: Trading pair symbol

        Returns:
            bool: True if enough data is available
        """
        if pair not in self.candle_buffer:
            return False

        return len(self.candle_buffer[pair]) >= self.sma_long_period

    def get_buffer_size(self, pair: str, timeframe: str = '1m') -> int:
        """
        Get the current buffer size for a pair

        Args:
            pair: Trading pair symbol
            timeframe: Timeframe ('1m' or '5m')

        Returns:
            int: Buffer size
        """
        if timeframe == '1m':
            return len(self.candle_buffer.get(pair, []))
        elif timeframe == '5m':
            return len(self.candle_5m_buffer.get(pair, []))
        return 0
