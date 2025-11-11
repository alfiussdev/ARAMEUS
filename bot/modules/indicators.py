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

    # ========================================================================
    # VRR-SPECIFIC INDICATORS
    # ========================================================================

    def calculate_wick_ratio(self, candle: Dict[str, Any], direction: str = 'auto') -> Dict[str, float]:
        """
        Calculate wick ratios for a candle (VRR indicator)

        Args:
            candle: Candle dictionary with open, high, low, close
            direction: 'bullish', 'bearish', or 'auto'

        Returns:
            dict: {
                'upper_wick_ratio': Upper wick / Total range,
                'lower_wick_ratio': Lower wick / Total range,
                'body_ratio': Body / Total range,
                'total_range': High - Low,
                'is_reversal': bool (strong wick >= 40%)
            }
        """
        high = candle['high']
        low = candle['low']
        open_price = candle['open']
        close_price = candle['close']

        total_range = high - low
        if total_range == 0:
            return {
                'upper_wick_ratio': 0,
                'lower_wick_ratio': 0,
                'body_ratio': 0,
                'total_range': 0,
                'is_reversal': False
            }

        # Calculate body
        body_top = max(open_price, close_price)
        body_bottom = min(open_price, close_price)
        body_size = abs(close_price - open_price)

        # Calculate wicks
        upper_wick = high - body_top
        lower_wick = body_bottom - low

        # Ratios
        upper_wick_ratio = upper_wick / total_range
        lower_wick_ratio = lower_wick / total_range
        body_ratio = body_size / total_range

        # Determine if it's a reversal candle
        is_bullish_reversal = lower_wick_ratio >= self.config.VRR_MIN_WICK_RATIO and close_price > open_price
        is_bearish_reversal = upper_wick_ratio >= self.config.VRR_MIN_WICK_RATIO and close_price < open_price

        if direction == 'auto':
            is_reversal = is_bullish_reversal or is_bearish_reversal
        elif direction == 'bullish':
            is_reversal = is_bullish_reversal
        else:  # bearish
            is_reversal = is_bearish_reversal

        return {
            'upper_wick_ratio': upper_wick_ratio,
            'lower_wick_ratio': lower_wick_ratio,
            'body_ratio': body_ratio,
            'total_range': total_range,
            'is_reversal': is_reversal,
            'is_strong_reversal': max(upper_wick_ratio, lower_wick_ratio) >= self.config.VRR_STRONG_WICK_RATIO
        }

    def calculate_directional_movement(self, candles: List[Dict[str, Any]],
                                      period: int, atr_multiplier: float) -> Dict[str, Any]:
        """
        Calculate directional movement over last N candles (VRR indicator)

        Args:
            candles: List of candle dictionaries
            period: Number of candles to check
            atr_multiplier: Minimum ATR multiplier required

        Returns:
            dict: {
                'direction': 'up', 'down', or 'none',
                'movement_size': Absolute price movement,
                'atr_multiple': Movement / ATR,
                'passes_filter': bool
            }
        """
        if len(candles) < period + 14:  # Need ATR period as well
            return {
                'direction': 'none',
                'movement_size': 0,
                'atr_multiple': 0,
                'passes_filter': False
            }

        # Get price movement over last N candles
        start_close = candles[-period - 1]['close']
        end_close = candles[-1]['close']
        movement = end_close - start_close
        movement_size = abs(movement)

        # Calculate ATR for reference
        atr = self.calculate_atr(candles, 14)
        if np.isnan(atr) or atr == 0:
            return {
                'direction': 'none',
                'movement_size': movement_size,
                'atr_multiple': 0,
                'passes_filter': False
            }

        atr_multiple = movement_size / atr

        # Determine direction
        if movement > 0:
            direction = 'up'
        elif movement < 0:
            direction = 'down'
        else:
            direction = 'none'

        passes_filter = atr_multiple >= atr_multiplier

        return {
            'direction': direction,
            'movement_size': movement_size,
            'atr_multiple': atr_multiple,
            'passes_filter': passes_filter
        }

    def calculate_volume_divergence(self, candles: List[Dict[str, Any]],
                                   lookback: int = 3) -> Dict[str, Any]:
        """
        Detect volume divergence (declining volume on directional move)

        Args:
            candles: List of candle dictionaries
            lookback: Number of candles to analyze

        Returns:
            dict: {
                'has_divergence': bool,
                'volume_trend': 'declining', 'rising', or 'flat',
                'price_trend': 'up', 'down', or 'flat',
                'divergence_strength': 0-1 score
            }
        """
        if len(candles) < lookback:
            return {
                'has_divergence': False,
                'volume_trend': 'flat',
                'price_trend': 'flat',
                'divergence_strength': 0
            }

        # Get last N candles
        recent_candles = candles[-lookback:]

        # Analyze volume trend
        volumes = [c['volume'] for c in recent_candles]
        volume_increasing = all(volumes[i] <= volumes[i+1] for i in range(len(volumes)-1))
        volume_decreasing = all(volumes[i] >= volumes[i+1] for i in range(len(volumes)-1))

        if volume_decreasing:
            volume_trend = 'declining'
        elif volume_increasing:
            volume_trend = 'rising'
        else:
            volume_trend = 'flat'

        # Analyze price trend
        closes = [c['close'] for c in recent_candles]
        price_increasing = all(closes[i] <= closes[i+1] for i in range(len(closes)-1))
        price_decreasing = all(closes[i] >= closes[i+1] for i in range(len(closes)-1))

        if price_increasing:
            price_trend = 'up'
        elif price_decreasing:
            price_trend = 'down'
        else:
            price_trend = 'flat'

        # Divergence exists when price trending but volume declining
        has_divergence = (price_trend in ['up', 'down']) and (volume_trend == 'declining')

        # Calculate divergence strength (0-1)
        if has_divergence:
            # Measure how much volume declined relative to first candle
            volume_ratio = volumes[-1] / volumes[0] if volumes[0] > 0 else 1.0
            divergence_strength = max(0, min(1, 1 - volume_ratio))
        else:
            divergence_strength = 0

        return {
            'has_divergence': has_divergence,
            'volume_trend': volume_trend,
            'price_trend': price_trend,
            'divergence_strength': divergence_strength
        }

    def find_swing_points(self, candles: List[Dict[str, Any]],
                         lookback: int = 20) -> Dict[str, Any]:
        """
        Find recent swing highs and lows (liquidity zones)

        Args:
            candles: List of candle dictionaries
            lookback: Number of candles to search

        Returns:
            dict: {
                'swing_high': Price level,
                'swing_low': Price level,
                'distance_to_high': % distance,
                'distance_to_low': % distance,
                'near_liquidity_zone': bool (within 1% of swing point)
            }
        """
        if len(candles) < lookback:
            return {
                'swing_high': np.nan,
                'swing_low': np.nan,
                'distance_to_high': np.nan,
                'distance_to_low': np.nan,
                'near_liquidity_zone': False
            }

        # Get recent candles
        recent_candles = candles[-lookback:]
        current_price = candles[-1]['close']

        # Find swing high (highest high)
        swing_high = max(c['high'] for c in recent_candles)

        # Find swing low (lowest low)
        swing_low = min(c['low'] for c in recent_candles)

        # Calculate distances
        if current_price > 0:
            distance_to_high = ((swing_high - current_price) / current_price) * 100
            distance_to_low = ((current_price - swing_low) / current_price) * 100
        else:
            distance_to_high = np.nan
            distance_to_low = np.nan

        # Check if near liquidity zone (within 1%)
        near_high = abs(distance_to_high) <= 1.0 if not np.isnan(distance_to_high) else False
        near_low = abs(distance_to_low) <= 1.0 if not np.isnan(distance_to_low) else False
        near_liquidity_zone = near_high or near_low

        return {
            'swing_high': swing_high,
            'swing_low': swing_low,
            'distance_to_high': distance_to_high,
            'distance_to_low': distance_to_low,
            'near_liquidity_zone': near_liquidity_zone
        }

    def detect_swing_levels_with_touches(self, candles: List[Dict[str, Any]],
                                         min_touches: int = 3,
                                         touch_tolerance: float = 0.008) -> Dict[str, Any]:
        """
        Detect swing high/low levels with multiple touches (support/resistance).
        Used for LSR strategy to find liquidity zones.

        Args:
            candles: List of candle dictionaries
            min_touches: Minimum number of touches to consider a valid level
            touch_tolerance: % tolerance for considering a price "touching" a level (0.8%)

        Returns:
            dict: {
                'resistance_level': float or None,
                'support_level': float or None,
                'resistance_touches': int,
                'support_touches': int,
                'has_valid_structure': bool
            }
        """
        if len(candles) < 20:
            return {
                'resistance_level': None,
                'support_level': None,
                'resistance_touches': 0,
                'support_touches': 0,
                'has_valid_structure': False
            }

        # Use last 60 candles for structure detection (1 hour on 1m)
        lookback = min(60, len(candles))
        recent_candles = candles[-lookback:]

        # Find local highs and lows
        highs = [c['high'] for c in recent_candles]
        lows = [c['low'] for c in recent_candles]

        # Find most prominent high and low (simple approach: highest/lowest in range)
        resistance_candidate = max(highs)
        support_candidate = min(lows)

        # Count touches within tolerance
        resistance_touches = 0
        support_touches = 0

        for candle in recent_candles:
            # Check if high touched resistance
            if abs(candle['high'] - resistance_candidate) / resistance_candidate <= touch_tolerance:
                resistance_touches += 1

            # Check if low touched support
            if abs(candle['low'] - support_candidate) / support_candidate <= touch_tolerance:
                support_touches += 1

        # Validate structure
        has_valid_resistance = resistance_touches >= min_touches
        has_valid_support = support_touches >= min_touches
        has_valid_structure = has_valid_resistance or has_valid_support

        return {
            'resistance_level': resistance_candidate if has_valid_resistance else None,
            'support_level': support_candidate if has_valid_support else None,
            'resistance_touches': resistance_touches,
            'support_touches': support_touches,
            'has_valid_structure': has_valid_structure
        }

    def detect_liquidity_sweep(self, candles: List[Dict[str, Any]],
                               swing_level: float,
                               direction: str,
                               min_volume_mult: float = 2.5,
                               min_wick_ratio: float = 0.50) -> Dict[str, Any]:
        """
        Detect if the current candle performed a liquidity sweep (fakeout).

        A sweep occurs when:
        1. Price breaks a key level (swing high/low)
        2. Volume is elevated (≥2.5× avg)
        3. Candle has large wick (≥50%)
        4. Price closes back inside the range (rejection)

        Args:
            candles: List of candle dictionaries
            swing_level: The swing high or low being tested
            direction: 'bullish_sweep' (tests support) or 'bearish_sweep' (tests resistance)
            min_volume_mult: Minimum volume multiplier vs average
            min_wick_ratio: Minimum wick ratio (0.50 = 50%)

        Returns:
            dict: {
                'is_sweep': bool,
                'sweep_distance': float (% beyond level),
                'wick_ratio': float,
                'volume_ratio': float,
                'closed_inside': bool
            }
        """
        if len(candles) < 20:
            return {
                'is_sweep': False,
                'sweep_distance': 0.0,
                'wick_ratio': 0.0,
                'volume_ratio': 0.0,
                'closed_inside': False
            }

        current_candle = candles[-1]
        prev_candles = candles[-21:-1]  # 20 candles for volume average

        # Calculate volume ratio
        avg_volume = np.mean([c['volume'] for c in prev_candles])
        volume_ratio = current_candle['volume'] / avg_volume if avg_volume > 0 else 0

        # Calculate wick ratios
        wick_data = self.calculate_wick_ratio(current_candle, direction='auto')

        # Check sweep conditions based on direction
        if direction == 'bullish_sweep':
            # Testing support from below (bearish candle sweeps support, then closes inside)
            swept_below = current_candle['low'] < swing_level
            closed_above = current_candle['close'] > swing_level
            relevant_wick_ratio = wick_data['lower_wick_ratio']
            sweep_distance = ((swing_level - current_candle['low']) / swing_level) * 100 if swept_below else 0.0

        elif direction == 'bearish_sweep':
            # Testing resistance from above (bullish candle sweeps resistance, then closes inside)
            swept_above = current_candle['high'] > swing_level
            closed_below = current_candle['close'] < swing_level
            relevant_wick_ratio = wick_data['upper_wick_ratio']
            sweep_distance = ((current_candle['high'] - swing_level) / swing_level) * 100 if swept_above else 0.0

        else:
            return {
                'is_sweep': False,
                'sweep_distance': 0.0,
                'wick_ratio': 0.0,
                'volume_ratio': volume_ratio,
                'closed_inside': False
            }

        # Validate all conditions
        volume_ok = volume_ratio >= min_volume_mult
        wick_ok = relevant_wick_ratio >= min_wick_ratio

        if direction == 'bullish_sweep':
            closed_inside = swept_below and closed_above
        else:
            closed_inside = swept_above and closed_below

        is_sweep = volume_ok and wick_ok and closed_inside

        return {
            'is_sweep': is_sweep,
            'sweep_distance': sweep_distance,
            'wick_ratio': relevant_wick_ratio,
            'volume_ratio': volume_ratio,
            'closed_inside': closed_inside
        }

    def detect_rsi_divergence(self, candles: List[Dict[str, Any]],
                             rsi_values: List[float],
                             direction: str,
                             lookback: int = 10) -> Dict[str, Any]:
        """
        Detect RSI divergence (price makes new high/low but RSI doesn't).

        Bullish divergence: Price makes lower low, RSI makes higher low
        Bearish divergence: Price makes higher high, RSI makes lower high

        Args:
            candles: List of candle dictionaries
            rsi_values: List of RSI values (same length as candles)
            direction: 'bullish' or 'bearish'
            lookback: Number of candles to look back for swing comparison

        Returns:
            dict: {
                'has_divergence': bool,
                'divergence_strength': float (0-1),
                'price_extreme': float,
                'rsi_extreme': float
            }
        """
        if len(candles) < lookback or len(rsi_values) < lookback:
            return {
                'has_divergence': False,
                'divergence_strength': 0.0,
                'price_extreme': 0.0,
                'rsi_extreme': 0.0
            }

        recent_candles = candles[-lookback:]
        recent_rsi = rsi_values[-lookback:]

        current_candle = candles[-1]
        current_rsi = rsi_values[-1]

        if direction == 'bullish':
            # Look for lower low in price, higher low in RSI
            price_lows = [c['low'] for c in recent_candles]
            prev_low_price = min(price_lows[:-1]) if len(price_lows) > 1 else price_lows[0]
            current_low_price = current_candle['low']

            prev_low_rsi_idx = price_lows.index(prev_low_price)
            prev_low_rsi = recent_rsi[prev_low_rsi_idx]

            # Bullish divergence: price lower, RSI higher
            price_makes_lower_low = current_low_price < prev_low_price
            rsi_makes_higher_low = current_rsi > prev_low_rsi

            has_divergence = price_makes_lower_low and rsi_makes_higher_low

            # Strength: how much RSI recovered vs price decline
            if has_divergence:
                price_decline_pct = ((prev_low_price - current_low_price) / prev_low_price) * 100
                rsi_recovery = current_rsi - prev_low_rsi
                divergence_strength = min(1.0, rsi_recovery / 20.0)  # Normalize to 0-1
            else:
                divergence_strength = 0.0

            return {
                'has_divergence': has_divergence,
                'divergence_strength': divergence_strength,
                'price_extreme': current_low_price,
                'rsi_extreme': current_rsi
            }

        elif direction == 'bearish':
            # Look for higher high in price, lower high in RSI
            price_highs = [c['high'] for c in recent_candles]
            prev_high_price = max(price_highs[:-1]) if len(price_highs) > 1 else price_highs[0]
            current_high_price = current_candle['high']

            prev_high_rsi_idx = price_highs.index(prev_high_price)
            prev_high_rsi = recent_rsi[prev_high_rsi_idx]

            # Bearish divergence: price higher, RSI lower
            price_makes_higher_high = current_high_price > prev_high_price
            rsi_makes_lower_high = current_rsi < prev_high_rsi

            has_divergence = price_makes_higher_high and rsi_makes_lower_high

            # Strength: how much RSI weakened vs price advance
            if has_divergence:
                price_advance_pct = ((current_high_price - prev_high_price) / prev_high_price) * 100
                rsi_decline = prev_high_rsi - current_rsi
                divergence_strength = min(1.0, rsi_decline / 20.0)  # Normalize to 0-1
            else:
                divergence_strength = 0.0

            return {
                'has_divergence': has_divergence,
                'divergence_strength': divergence_strength,
                'price_extreme': current_high_price,
                'rsi_extreme': current_rsi
            }

        else:
            return {
                'has_divergence': False,
                'divergence_strength': 0.0,
                'price_extreme': 0.0,
                'rsi_extreme': 0.0
            }
