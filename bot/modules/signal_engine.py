"""
Signal engine module for generating trading signals
Implements the multi-filter entry logic for LONG and SHORT signals
"""

from typing import Dict, Any, Optional, Tuple
from enum import Enum


class SignalType(Enum):
    """Signal types"""
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class SignalEngine:
    """Generate trading signals based on technical indicators and filters"""

    def __init__(self, config, logger):
        """
        Initialize signal engine

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

    def evaluate_signal(self, pair: str, indicators: Dict[str, Any],
                       orderbook: Dict[str, Any]) -> Tuple[SignalType, float, Dict[str, bool]]:
        """
        Evaluate trading signal based on indicators and filters

        Args:
            pair: Trading pair
            indicators: Dictionary of indicator values
            orderbook: Orderbook data with spread information

        Returns:
            Tuple of (signal_type, confidence, filters_passed)
        """
        # Check if we have all required indicators
        required_indicators = [
            'sma50', 'sma200', 'ema9', 'ema20', 'rsi', 'vwap',
            'atr_current', 'atr_mean', 'volatility_ratio',
            'volume_current', 'volume_mean_20', 'volume_mean_3',
            'current_close'
        ]

        for indicator in required_indicators:
            if indicator not in indicators:
                self.logger.log_system_event(
                    f"Missing indicator {indicator} for {pair}",
                    pair=pair,
                    available_indicators=list(indicators.keys())
                )
                return SignalType.NO_TRADE, 0.0, {}

        # Evaluate LONG conditions
        long_signal, long_confidence, long_filters = self._evaluate_long_signal(
            indicators, orderbook
        )

        # Evaluate SHORT conditions
        short_signal, short_confidence, short_filters = self._evaluate_short_signal(
            indicators, orderbook
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
        self.logger.log_signal(
            pair=pair,
            signal=signal.value,
            confidence=confidence,
            indicators=indicators,
            filters_passed=filters
        )

        return signal, confidence, filters

    def _evaluate_long_signal(self, indicators: Dict[str, Any],
                              orderbook: Dict[str, Any]) -> Tuple[bool, float, Dict[str, bool]]:
        """
        Evaluate LONG signal conditions

        Args:
            indicators: Dictionary of indicator values
            orderbook: Orderbook data

        Returns:
            Tuple of (signal_valid, confidence, filters_passed)
        """
        filters = {}

        # 1. Trend macro: SMA50 > SMA200
        filters['trend_macro'] = indicators['sma50'] > indicators['sma200']

        # 2. Momentum immediate: EMA9 > EMA20
        filters['momentum_immediate'] = indicators['ema9'] > indicators['ema20']

        # 3. Institutional bias: close > VWAP
        filters['institutional_bias'] = indicators['current_close'] > indicators['vwap']

        # 4. Healthy momentum (RSI): RSI > 55
        filters['rsi_threshold'] = indicators['rsi'] > self.config.RSI_LONG_THRESHOLD

        # 5. Strong relative volume
        vol_20_check = indicators['volume_current'] > (self.config.VOL_MULTIPLIER_20 * indicators['volume_mean_20'])
        vol_3_check = indicators['volume_current'] > (self.config.VOL_MULTIPLIER_3 * indicators['volume_mean_3'])
        filters['volume_relative'] = vol_20_check and vol_3_check

        # 6. 5-minute structure alignment (if available)
        if 'close_5m' in indicators and 'open_5m' in indicators:
            filters['structure_5m'] = indicators['close_5m'] > indicators['open_5m']

            # Optional: EMA20_5m confirmation
            if 'ema20_5m' in indicators:
                filters['structure_5m'] = filters['structure_5m'] and (
                    indicators['close_5m'] > indicators['ema20_5m']
                )
        else:
            # If no 5m data, pass this filter
            filters['structure_5m'] = True

        # 7. Spread filter (liquidity)
        filters['spread_check'] = orderbook['spread'] <= self.config.MAX_SPREAD

        # Calculate confidence based on how many filters passed
        filters_passed = sum(filters.values())
        total_filters = len(filters)
        confidence = filters_passed / total_filters

        # Signal is valid only if ALL filters pass
        signal_valid = all(filters.values())

        return signal_valid, confidence, filters

    def _evaluate_short_signal(self, indicators: Dict[str, Any],
                               orderbook: Dict[str, Any]) -> Tuple[bool, float, Dict[str, bool]]:
        """
        Evaluate SHORT signal conditions

        Args:
            indicators: Dictionary of indicator values
            orderbook: Orderbook data

        Returns:
            Tuple of (signal_valid, confidence, filters_passed)
        """
        filters = {}

        # 1. Trend macro: SMA50 < SMA200
        filters['trend_macro'] = indicators['sma50'] < indicators['sma200']

        # 2. Momentum immediate: EMA9 < EMA20
        filters['momentum_immediate'] = indicators['ema9'] < indicators['ema20']

        # 3. Institutional bias: close < VWAP
        filters['institutional_bias'] = indicators['current_close'] < indicators['vwap']

        # 4. Healthy momentum (RSI): RSI < 45
        filters['rsi_threshold'] = indicators['rsi'] < self.config.RSI_SHORT_THRESHOLD

        # 5. Strong relative volume
        vol_20_check = indicators['volume_current'] > (self.config.VOL_MULTIPLIER_20 * indicators['volume_mean_20'])
        vol_3_check = indicators['volume_current'] > (self.config.VOL_MULTIPLIER_3 * indicators['volume_mean_3'])
        filters['volume_relative'] = vol_20_check and vol_3_check

        # 6. 5-minute structure alignment (if available)
        if 'close_5m' in indicators and 'open_5m' in indicators:
            filters['structure_5m'] = indicators['close_5m'] < indicators['open_5m']

            # Optional: EMA20_5m confirmation
            if 'ema20_5m' in indicators:
                filters['structure_5m'] = filters['structure_5m'] and (
                    indicators['close_5m'] < indicators['ema20_5m']
                )
        else:
            # If no 5m data, pass this filter
            filters['structure_5m'] = True

        # 7. Spread filter (liquidity)
        filters['spread_check'] = orderbook['spread'] <= self.config.MAX_SPREAD

        # Calculate confidence based on how many filters passed
        filters_passed = sum(filters.values())
        total_filters = len(filters)
        confidence = filters_passed / total_filters

        # Signal is valid only if ALL filters pass
        signal_valid = all(filters.values())

        return signal_valid, confidence, filters

    def check_invalidation(self, position_side: str, indicators: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if current position should be invalidated based on changed conditions

        Args:
            position_side: Current position side ('LONG' or 'SHORT')
            indicators: Current indicator values

        Returns:
            Tuple of (should_invalidate, reason)
        """
        if position_side == 'LONG':
            # Check LONG invalidation conditions
            if indicators['ema9'] <= indicators['ema20']:
                return True, "EMA9 crossed below EMA20"

            if indicators['current_close'] < indicators['vwap']:
                return True, "Price fell below VWAP"

            if indicators['rsi'] < self.config.RSI_INVALIDATION_LONG:
                return True, f"RSI dropped below {self.config.RSI_INVALIDATION_LONG}"

        elif position_side == 'SHORT':
            # Check SHORT invalidation conditions
            if indicators['ema9'] >= indicators['ema20']:
                return True, "EMA9 crossed above EMA20"

            if indicators['current_close'] > indicators['vwap']:
                return True, "Price rose above VWAP"

            if indicators['rsi'] > self.config.RSI_INVALIDATION_SHORT:
                return True, f"RSI rose above {self.config.RSI_INVALIDATION_SHORT}"

        return False, ""

    def get_signal_summary(self, signal: SignalType, confidence: float,
                          filters: Dict[str, bool]) -> str:
        """
        Get a human-readable summary of the signal

        Args:
            signal: Signal type
            confidence: Signal confidence (0-1)
            filters: Dictionary of filter results

        Returns:
            String summary
        """
        if signal == SignalType.NO_TRADE:
            failed_filters = [k for k, v in filters.items() if not v]
            return f"NO_TRADE - Failed filters: {', '.join(failed_filters) if failed_filters else 'None'}"

        passed = sum(filters.values())
        total = len(filters)

        return f"{signal.value} - Confidence: {confidence:.2%} ({passed}/{total} filters passed)"
