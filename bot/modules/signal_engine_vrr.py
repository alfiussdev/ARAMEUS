"""
Signal engine module for VRR (Volatility Rejection Reversal) strategy
Implements mean reversion entries on volatility spikes with exhaustion signals
"""

from typing import Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
import numpy as np


class SignalType(Enum):
    """Signal types"""
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class VRRSignalEngine:
    """Generate VRR trading signals based on volatility exhaustion and reversal patterns"""

    def __init__(self, config, logger, indicators_engine):
        """
        Initialize VRR signal engine

        Args:
            config: Configuration object
            logger: Logger instance
            indicators_engine: IndicatorEngine instance for VRR-specific calculations
        """
        self.config = config
        self.logger = logger
        self.indicators = indicators_engine

    def evaluate_signal(self, pair: str, indicators: Dict[str, Any],
                       orderbook: Dict[str, Any], candles: list,
                       enable_debug: bool = False,
                       candle_num: int = 0, timestamp=None) -> Tuple[SignalType, float, Dict[str, bool]]:
        """
        Evaluate VRR trading signal based on volatility exhaustion

        Args:
            pair: Trading pair
            indicators: Dictionary of indicator values
            orderbook: Orderbook data with spread information
            candles: List of recent candles for VRR analysis
            enable_debug: Enable detailed debug logging
            candle_num: Candle number for debug logging
            timestamp: Timestamp for debug logging

        Returns:
            Tuple of (signal_type, confidence, filters_passed)
        """
        # Check minimum required indicators
        required_indicators = ['rsi', 'vwap', 'atr_current', 'volume_current', 'volume_mean_20', 'current_close']

        for indicator in required_indicators:
            if indicator not in indicators:
                self.logger.log_system_event(
                    f"Missing indicator {indicator} for VRR strategy on {pair}",
                    pair=pair,
                    available_indicators=list(indicators.keys())
                )
                return SignalType.NO_TRADE, 0.0, {}

        # Check market regime filters first (fast reject)
        if not self._check_market_regime(indicators, candles, timestamp):
            return SignalType.NO_TRADE, 0.0, {'regime_ok': False}

        # Evaluate LONG conditions (buy after bearish exhaustion)
        long_signal, long_confidence, long_filters = self._evaluate_long_signal(
            indicators, orderbook, candles, enable_debug, candle_num, timestamp
        )

        # Evaluate SHORT conditions (sell after bullish exhaustion)
        short_signal, short_confidence, short_filters = self._evaluate_short_signal(
            indicators, orderbook, candles, enable_debug, candle_num, timestamp
        )

        # Determine final signal
        if long_signal and not short_signal:
            signal = SignalType.LONG
            confidence = long_confidence
            filters = long_filters
        elif short_signal and not long_signal:
            signal = SignalType.SHORT
            confidence = short_confidence
            filters = short_filters
        else:
            signal = SignalType.NO_TRADE
            confidence = 0.0
            filters = {}

        # Log signal evaluation
        if self.logger:
            self.logger.log_signal(
                pair=pair,
                signal=signal.value,
                confidence=confidence,
                indicators=indicators,
                filters_passed=filters
            )

        return signal, confidence, filters

    def _check_market_regime(self, indicators: Dict[str, Any],
                            candles: list, timestamp) -> bool:
        """
        Check if market regime is suitable for VRR trading

        Returns:
            bool: True if regime is suitable
        """
        # 1. Volatility Filter: ATR_current > 1.2× ATR_baseline
        if self.config.VRR_ENABLE_VOL_FILTER:
            atr_current = indicators.get('atr_current')
            atr_mean = indicators.get('atr_mean')

            if atr_current and atr_mean and atr_mean > 0:
                atr_ratio = atr_current / atr_mean
                if atr_ratio < self.config.VRR_ATR_MIN_RATIO:
                    return False  # Too low volatility
            else:
                return False  # Can't calculate ratio

        # 2. Trend/Range Filter: EMAs must be separated (not ranging)
        if self.config.VRR_ENABLE_TREND_FILTER:
            ema_fast = indicators.get('ema9')
            ema_slow = indicators.get('ema20')
            current_close = indicators.get('current_close')

            if ema_fast and ema_slow and current_close and current_close > 0:
                ema_separation = abs(ema_fast - ema_slow) / current_close
                if ema_separation < self.config.VRR_MIN_EMA_SEPARATION:
                    return False  # Market too flat/ranging

        # 3. Time Filter: Only trade during high-volume hours
        if self.config.VRR_ENABLE_TIME_FILTER and timestamp:
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    dt = datetime.now()
            else:
                dt = timestamp if isinstance(timestamp, datetime) else datetime.now()

            hour_utc = dt.hour
            if hour_utc < self.config.VRR_START_HOUR or hour_utc >= self.config.VRR_END_HOUR:
                return False  # Outside trading hours

        return True

    def _evaluate_long_signal(self, indicators: Dict[str, Any],
                              orderbook: Dict[str, Any], candles: list,
                              enable_debug: bool = False,
                              candle_num: int = 0, timestamp=None) -> Tuple[bool, float, Dict[str, bool]]:
        """
        Evaluate LONG signal (buy after bearish exhaustion / oversold reversal)

        Returns:
            Tuple of (signal_valid, confidence, filters_passed)
        """
        filters = {}

        # Get current candle for structure analysis
        current_candle = candles[-1]
        prev_candle = candles[-2] if len(candles) >= 2 else current_candle

        # 1. Directional Movement: Recent strong bearish move (≥ 1.8× ATR in 5 candles)
        dir_movement = self.indicators.calculate_directional_movement(
            candles,
            self.config.VRR_DIRECTION_PERIOD,
            self.config.VRR_DIRECTION_ATR_MULT
        )
        filters['directional_move_ok'] = (dir_movement['direction'] == 'down' and
                                         dir_movement['passes_filter'])

        # 2. RSI Exhaustion: RSI < 26 (oversold)
        rsi = indicators['rsi']
        filters['rsi_exhaustion_ok'] = rsi < self.config.RSI_LONG_THRESHOLD

        # 3. Volume Spike: Current volume > 4× average
        vol_current = indicators['volume_current']
        vol_mean = indicators['volume_mean_20']
        vol_ratio = vol_current / vol_mean if vol_mean > 0 else 0
        filters['volume_spike_ok'] = vol_ratio >= self.config.VRR_VOL_SPIKE_MULT

        # 4. Reversal Candle Structure: Bullish candle with strong lower wick
        wick_data = self.indicators.calculate_wick_ratio(current_candle, direction='bullish')
        filters['reversal_structure_ok'] = wick_data['is_reversal']

        # 5. Volume Divergence: Declining volume on the bearish push
        if self.config.VRR_ENABLE_VOL_DIVERGENCE:
            vol_div = self.indicators.calculate_volume_divergence(
                candles,
                self.config.VRR_DIVERGENCE_LOOKBACK
            )
            filters['volume_divergence_ok'] = vol_div['has_divergence']
        else:
            filters['volume_divergence_ok'] = True  # Skip if disabled

        # 6. Multi-Timeframe Confirmation
        if self.config.VRR_ENABLE_MTF:
            rsi_5m = indicators.get('rsi_5m', 50)
            filters['mtf_confirmation_ok'] = rsi_5m < self.config.VRR_MTF_RSI_LONG
        else:
            filters['mtf_confirmation_ok'] = True  # Skip if disabled

        # 7. Structural Validation
        if self.config.VRR_ENABLE_STRUCTURE_CHECK:
            structure_ok = True

            # Must close within previous candle range
            if self.config.VRR_MUST_CLOSE_IN_PREV_RANGE:
                close_in_range = (current_candle['close'] >= prev_candle['low'] and
                                current_candle['close'] <= prev_candle['high'])
                structure_ok = structure_ok and close_in_range

            # Near liquidity zone (swing low)
            if self.config.VRR_CHECK_LIQUIDITY_ZONE:
                swing_points = self.indicators.find_swing_points(
                    candles,
                    self.config.VRR_LIQUIDITY_LOOKBACK
                )
                structure_ok = structure_ok and swing_points['near_liquidity_zone']

            filters['structure_ok'] = structure_ok
        else:
            filters['structure_ok'] = True

        # 8. Spread filter
        filters['spread_ok'] = orderbook['spread'] <= self.config.MAX_SPREAD

        # Calculate confidence
        filters_passed = sum(filters.values())
        total_filters = len(filters)
        confidence = filters_passed / total_filters

        # Signal is valid only if ALL filters pass
        signal_valid = all(filters.values())

        # Debug logging
        if enable_debug:
            decision = "VRR_LONG_ENTRY" if signal_valid else "no_trade"
            print(f"[VRR][{candle_num}] {timestamp} | {decision} | "
                  f"direction_ok={filters['directional_move_ok']} (ATR_mult={dir_movement['atr_multiple']:.2f}) | "
                  f"rsi_ok={filters['rsi_exhaustion_ok']} (RSI={rsi:.1f}) | "
                  f"vol_spike_ok={filters['volume_spike_ok']} (ratio={vol_ratio:.2f}) | "
                  f"reversal_ok={filters['reversal_structure_ok']} (wick={wick_data['lower_wick_ratio']:.2f}) | "
                  f"vol_div_ok={filters['volume_divergence_ok']} | "
                  f"mtf_ok={filters['mtf_confirmation_ok']} | "
                  f"structure_ok={filters['structure_ok']} | "
                  f"spread_ok={filters['spread_ok']}")

        return signal_valid, confidence, filters

    def _evaluate_short_signal(self, indicators: Dict[str, Any],
                               orderbook: Dict[str, Any], candles: list,
                               enable_debug: bool = False,
                               candle_num: int = 0, timestamp=None) -> Tuple[bool, float, Dict[str, bool]]:
        """
        Evaluate SHORT signal (sell after bullish exhaustion / overbought reversal)

        Returns:
            Tuple of (signal_valid, confidence, filters_passed)
        """
        filters = {}

        # Get current candle for structure analysis
        current_candle = candles[-1]
        prev_candle = candles[-2] if len(candles) >= 2 else current_candle

        # 1. Directional Movement: Recent strong bullish move (≥ 1.8× ATR in 5 candles)
        dir_movement = self.indicators.calculate_directional_movement(
            candles,
            self.config.VRR_DIRECTION_PERIOD,
            self.config.VRR_DIRECTION_ATR_MULT
        )
        filters['directional_move_ok'] = (dir_movement['direction'] == 'up' and
                                         dir_movement['passes_filter'])

        # 2. RSI Exhaustion: RSI > 74 (overbought)
        rsi = indicators['rsi']
        filters['rsi_exhaustion_ok'] = rsi > self.config.RSI_SHORT_THRESHOLD

        # 3. Volume Spike: Current volume > 4× average
        vol_current = indicators['volume_current']
        vol_mean = indicators['volume_mean_20']
        vol_ratio = vol_current / vol_mean if vol_mean > 0 else 0
        filters['volume_spike_ok'] = vol_ratio >= self.config.VRR_VOL_SPIKE_MULT

        # 4. Reversal Candle Structure: Bearish candle with strong upper wick
        wick_data = self.indicators.calculate_wick_ratio(current_candle, direction='bearish')
        filters['reversal_structure_ok'] = wick_data['is_reversal']

        # 5. Volume Divergence: Declining volume on the bullish push
        if self.config.VRR_ENABLE_VOL_DIVERGENCE:
            vol_div = self.indicators.calculate_volume_divergence(
                candles,
                self.config.VRR_DIVERGENCE_LOOKBACK
            )
            filters['volume_divergence_ok'] = vol_div['has_divergence']
        else:
            filters['volume_divergence_ok'] = True  # Skip if disabled

        # 6. Multi-Timeframe Confirmation
        if self.config.VRR_ENABLE_MTF:
            rsi_5m = indicators.get('rsi_5m', 50)
            filters['mtf_confirmation_ok'] = rsi_5m > self.config.VRR_MTF_RSI_SHORT
        else:
            filters['mtf_confirmation_ok'] = True  # Skip if disabled

        # 7. Structural Validation
        if self.config.VRR_ENABLE_STRUCTURE_CHECK:
            structure_ok = True

            # Must close within previous candle range
            if self.config.VRR_MUST_CLOSE_IN_PREV_RANGE:
                close_in_range = (current_candle['close'] >= prev_candle['low'] and
                                current_candle['close'] <= prev_candle['high'])
                structure_ok = structure_ok and close_in_range

            # Near liquidity zone (swing high)
            if self.config.VRR_CHECK_LIQUIDITY_ZONE:
                swing_points = self.indicators.find_swing_points(
                    candles,
                    self.config.VRR_LIQUIDITY_LOOKBACK
                )
                structure_ok = structure_ok and swing_points['near_liquidity_zone']

            filters['structure_ok'] = structure_ok
        else:
            filters['structure_ok'] = True

        # 8. Spread filter
        filters['spread_ok'] = orderbook['spread'] <= self.config.MAX_SPREAD

        # Calculate confidence
        filters_passed = sum(filters.values())
        total_filters = len(filters)
        confidence = filters_passed / total_filters

        # Signal is valid only if ALL filters pass
        signal_valid = all(filters.values())

        # Debug logging
        if enable_debug:
            decision = "VRR_SHORT_ENTRY" if signal_valid else "no_trade"
            print(f"[VRR][{candle_num}] {timestamp} | {decision} | "
                  f"direction_ok={filters['directional_move_ok']} (ATR_mult={dir_movement['atr_multiple']:.2f}) | "
                  f"rsi_ok={filters['rsi_exhaustion_ok']} (RSI={rsi:.1f}) | "
                  f"vol_spike_ok={filters['volume_spike_ok']} (ratio={vol_ratio:.2f}) | "
                  f"reversal_ok={filters['reversal_structure_ok']} (wick={wick_data['upper_wick_ratio']:.2f}) | "
                  f"vol_div_ok={filters['volume_divergence_ok']} | "
                  f"mtf_ok={filters['mtf_confirmation_ok']} | "
                  f"structure_ok={filters['structure_ok']} | "
                  f"spread_ok={filters['spread_ok']}")

        return signal_valid, confidence, filters

    def calculate_position_size(self, base_equity: float, rsi: float,
                               has_divergence: bool, mtf_confirms: bool) -> float:
        """
        Calculate dynamic position size based on setup quality

        Args:
            base_equity: Base equity to allocate
            rsi: Current RSI value
            has_divergence: Whether volume divergence exists
            mtf_confirms: Whether multi-timeframe confirms

        Returns:
            float: Position size multiplier (0.5, 1.0, or 1.2)
        """
        if not self.config.VRR_ENABLE_DYNAMIC_SIZE:
            return 1.0  # Fixed size

        # Full size (1.0x) for extreme RSI with divergence
        if rsi < self.config.VRR_FULL_SIZE_RSI_LONG or rsi > self.config.VRR_FULL_SIZE_RSI_SHORT:
            if not self.config.VRR_FULL_SIZE_REQUIRES_DIVERGENCE or has_divergence:
                size_mult = 1.0
            else:
                size_mult = 0.5  # Extreme RSI but no divergence = half size
        # Half size for moderate RSI levels
        elif self.config.VRR_HALF_SIZE_RSI_RANGE_LOW <= rsi <= self.config.VRR_HALF_SIZE_RSI_RANGE_HIGH:
            size_mult = 0.5
        else:
            size_mult = 1.0

        # Bonus for multi-timeframe confirmation
        if mtf_confirms and self.config.VRR_ENABLE_MTF:
            size_mult *= self.config.VRR_MTF_SIZE_MULTIPLIER

        return size_mult

    def check_adaptive_exit(self, position_side: str, indicators: Dict[str, Any],
                           current_candle: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check adaptive exit conditions (Volume Exhaustion Trail logic)

        Args:
            position_side: Current position side ('LONG' or 'SHORT')
            indicators: Current indicator values
            current_candle: Current candle data

        Returns:
            Tuple of (should_exit, reason)
        """
        # 1. Exit on volume drop below average
        if self.config.VRR_EXIT_ON_VOLUME_DROP:
            vol_current = indicators.get('volume_current', 0)
            vol_mean = indicators.get('volume_mean_20', 1)
            if vol_current < vol_mean:
                return True, "Volume dropped below average"

        # 2. Exit on RSI returning to neutral (50)
        if self.config.VRR_EXIT_ON_RSI_NEUTRAL:
            rsi = indicators.get('rsi', 50)
            if position_side == 'LONG' and rsi >= 50:
                return True, "RSI crossed above 50 (momentum faded)"
            elif position_side == 'SHORT' and rsi <= 50:
                return True, "RSI crossed below 50 (momentum faded)"

        # 3. Exit on high-volume counter candle
        if self.config.VRR_EXIT_ON_COUNTER_CANDLE:
            vol_current = indicators.get('volume_current', 0)
            vol_mean = indicators.get('volume_mean_20', 1)
            vol_ratio = vol_current / vol_mean if vol_mean > 0 else 0

            if vol_ratio > 2.0:  # High volume candle
                is_counter_candle = False
                if position_side == 'LONG' and current_candle['close'] < current_candle['open']:
                    is_counter_candle = True  # Bearish candle in LONG
                elif position_side == 'SHORT' and current_candle['close'] > current_candle['open']:
                    is_counter_candle = True  # Bullish candle in SHORT

                if is_counter_candle:
                    return True, "High-volume counter candle appeared"

        return False, ""

    def get_signal_summary(self, signal: SignalType, confidence: float,
                          filters: Dict[str, bool]) -> str:
        """
        Get a human-readable summary of the VRR signal

        Args:
            signal: Signal type
            confidence: Signal confidence (0-1)
            filters: Dictionary of filter results

        Returns:
            String summary
        """
        if signal == SignalType.NO_TRADE:
            failed_filters = [k for k, v in filters.items() if not v]
            return f"[VRR] NO_TRADE - Failed filters: {', '.join(failed_filters) if failed_filters else 'None'}"

        passed = sum(filters.values())
        total = len(filters)

        return f"[VRR] {signal.value} - Confidence: {confidence:.2%} ({passed}/{total} filters passed)"
