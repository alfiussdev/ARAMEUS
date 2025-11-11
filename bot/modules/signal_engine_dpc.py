"""
Signal engine module for DPC (Dynamic Pullback Continuation) strategy
Implements trend-following entries on clean pullbacks with fibonacci confirmation
"""

from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from datetime import datetime
import numpy as np


class SignalType(Enum):
    """Signal types"""
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class DPCSignalEngine:
    """Generate DPC trading signals based on pullback continuation patterns"""

    def __init__(self, config, logger, indicators_engine):
        """
        Initialize DPC signal engine

        Args:
            config: Configuration object
            logger: Logger instance
            indicators_engine: IndicatorEngine instance
        """
        self.config = config
        self.logger = logger
        self.indicators = indicators_engine

    def evaluate_signal(self, pair: str, indicators: Dict[str, Any],
                       orderbook: Dict[str, Any], candles: list,
                       enable_debug: bool = False,
                       candle_num: int = 0, timestamp=None) -> Tuple[SignalType, float, Dict[str, bool]]:
        """
        Evaluate DPC trading signal based on pullback continuation

        Args:
            pair: Trading pair
            indicators: Dictionary of indicator values
            orderbook: Orderbook data
            candles: List of recent candles
            enable_debug: Enable detailed debug logging
            candle_num: Candle number for debug logging
            timestamp: Timestamp for debug logging

        Returns:
            Tuple of (signal_type, confidence, filters_passed)
        """
        # Check minimum required indicators
        required_indicators = ['rsi', 'ema9', 'ema20', 'atr_current', 'volume_current', 'volume_mean_20', 'current_close']

        for indicator in required_indicators:
            if indicator not in indicators:
                return SignalType.NO_TRADE, 0.0, {}

        # Check market regime filters first (fast reject)
        if not self._check_market_regime(indicators, candles, timestamp):
            return SignalType.NO_TRADE, 0.0, {'regime_ok': False}

        # Evaluate LONG conditions
        long_signal, long_confidence, long_filters = self._evaluate_long_signal(
            indicators, orderbook, candles, enable_debug, candle_num, timestamp
        )

        # Evaluate SHORT conditions
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

        # Log signal
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
        Check if market regime is suitable for DPC trading

        Returns:
            bool: True if regime is suitable
        """
        # 1. Volatility Filter: ATR_current >= 1.1× ATR_baseline
        if self.config.DPC_ENABLE_VOL_FILTER:
            atr_current = indicators.get('atr_current')
            atr_mean = indicators.get('atr_mean')

            if atr_current and atr_mean and atr_mean > 0:
                atr_ratio = atr_current / atr_mean
                if atr_ratio < self.config.DPC_ATR_MIN_RATIO:
                    return False  # Too low volatility
            else:
                return False

        # 2. Time Filter: Only trade London/NY overlap
        if self.config.DPC_ENABLE_TIME_FILTER and timestamp:
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    dt = datetime.now()
            else:
                dt = timestamp if isinstance(timestamp, datetime) else datetime.now()

            hour_utc = dt.hour
            if hour_utc < self.config.DPC_START_HOUR or hour_utc >= self.config.DPC_END_HOUR:
                return False  # Outside trading hours

        # 3. Chop Filter: Avoid ranging markets
        if self.config.DPC_ENABLE_CHOP_FILTER and len(candles) >= self.config.DPC_CHOP_LOOKBACK:
            ema20_crosses = self._count_ema20_crosses(candles, self.config.DPC_CHOP_LOOKBACK)
            if ema20_crosses > self.config.DPC_MAX_EMA20_CROSSES:
                return False  # Too choppy

        return True

    def _count_ema20_crosses(self, candles: list, lookback: int) -> int:
        """Count how many times price crossed EMA20 in lookback period"""
        if len(candles) < lookback + 20:
            return 0

        crosses = 0
        recent_candles = candles[-lookback:]

        # Calculate EMA20 for each candle
        for i in range(1, len(recent_candles)):
            # Simple approximation: use close prices
            closes = [c['close'] for c in candles[-lookback-20+i:- lookback+i if lookback-i > 0 else None]]
            ema20 = self.indicators.calculate_ema(np.array(closes), 20)

            prev_close = recent_candles[i-1]['close']
            curr_close = recent_candles[i]['close']

            # Check if crossed
            if (prev_close < ema20 and curr_close > ema20) or (prev_close > ema20 and curr_close < ema20):
                crosses += 1

        return crosses

    def _detect_pullback(self, candles: list, direction: str) -> Dict[str, Any]:
        """
        Detect if there's a valid pullback

        Args:
            candles: List of candles
            direction: 'up' for long trend, 'down' for short trend

        Returns:
            dict with pullback info
        """
        if len(candles) < self.config.DPC_SWING_LOOKBACK + self.config.DPC_MIN_PULLBACK_CANDLES:
            return {'valid': False}

        # Find swing high/low
        lookback_candles = candles[-self.config.DPC_SWING_LOOKBACK:]

        if direction == 'up':
            # Find swing low for uptrend
            swing_price = min(c['low'] for c in lookback_candles)
            swing_idx = next(i for i, c in enumerate(lookback_candles) if c['low'] == swing_price)

            # Find recent high after swing
            high_candles = lookback_candles[swing_idx:]
            if not high_candles:
                return {'valid': False}

            recent_high = max(c['high'] for c in high_candles)

            # Check if we had consecutive down candles (pullback)
            recent_candles = candles[-self.config.DPC_MIN_PULLBACK_CANDLES:]
            has_pullback = all(c['close'] < c['open'] for c in recent_candles)

            if not has_pullback:
                return {'valid': False}

            # Calculate Fibonacci retracement
            current_price = candles[-1]['close']
            swing_range = recent_high - swing_price
            if swing_range == 0:
                return {'valid': False}

            retracement = (recent_high - current_price) / swing_range

        else:  # direction == 'down'
            # Find swing high for downtrend
            swing_price = max(c['high'] for c in lookback_candles)
            swing_idx = next(i for i, c in enumerate(lookback_candles) if c['high'] == swing_price)

            # Find recent low after swing
            low_candles = lookback_candles[swing_idx:]
            if not low_candles:
                return {'valid': False}

            recent_low = min(c['low'] for c in low_candles)

            # Check if we had consecutive up candles (pullback)
            recent_candles = candles[-self.config.DPC_MIN_PULLBACK_CANDLES:]
            has_pullback = all(c['close'] > c['open'] for c in recent_candles)

            if not has_pullback:
                return {'valid': False}

            # Calculate Fibonacci retracement
            current_price = candles[-1]['close']
            swing_range = swing_price - recent_low
            if swing_range == 0:
                return {'valid': False}

            retracement = (current_price - recent_low) / swing_range

        # Check if retracement is in valid range (0.382 - 0.618)
        valid_fib = self.config.DPC_FIB_MIN <= retracement <= self.config.DPC_FIB_MAX

        return {
            'valid': valid_fib,
            'swing_price': swing_price,
            'retracement': retracement,
            'has_pullback_candles': has_pullback
        }

    def _evaluate_long_signal(self, indicators: Dict[str, Any],
                              orderbook: Dict[str, Any], candles: list,
                              enable_debug: bool = False,
                              candle_num: int = 0, timestamp=None) -> Tuple[bool, float, Dict[str, bool]]:
        """Evaluate LONG signal (pullback in uptrend)"""
        filters = {}

        # Need EMA100 - calculate it
        if len(candles) < 100:
            return False, 0.0, {'not_enough_data': False}

        closes = np.array([c['close'] for c in candles])
        ema20 = self.indicators.calculate_ema(closes, 20)
        ema50 = self.indicators.calculate_ema(closes, 50)
        ema100 = self.indicators.calculate_ema(closes, 100)

        # 1. EMA Stack: EMA20 > EMA50 > EMA100
        if self.config.DPC_ENABLE_EMA_STACK:
            filters['ema_stack_ok'] = ema20 > ema50 > ema100
        else:
            filters['ema_stack_ok'] = True

        # 2. Pullback Detection with Fibonacci
        pullback_info = self._detect_pullback(candles, 'up')
        filters['pullback_valid'] = pullback_info['valid']

        # 3. RSI in pullback zone (45-55)
        rsi = indicators['rsi']
        filters['rsi_pullback_ok'] = self.config.DPC_RSI_PULLBACK_MIN <= rsi <= self.config.DPC_RSI_PULLBACK_MAX

        # 4. Price reclaimed EMA20
        current_close = indicators['current_close']
        if self.config.DPC_MUST_CLOSE_BEYOND_EMA20:
            filters['price_reclaim_ok'] = current_close > ema20
        else:
            filters['price_reclaim_ok'] = True

        # 5. RSI momentum resumption (50-55)
        filters['rsi_momentum_ok'] = self.config.DPC_RSI_LONG_ENTRY_MIN <= rsi <= self.config.DPC_RSI_LONG_ENTRY_MAX

        # 6. Volume confirmation
        vol_current = indicators['volume_current']
        vol_mean_10 = np.mean([c['volume'] for c in candles[-10:]])
        vol_ratio = vol_current / vol_mean_10 if vol_mean_10 > 0 else 0
        filters['volume_ok'] = vol_ratio >= self.config.DPC_VOL_SPIKE_MULT

        # 7. Candle structure (wick ≤ 30%)
        current_candle = candles[-1]
        wick_data = self.indicators.calculate_wick_ratio(current_candle)
        filters['candle_structure_ok'] = max(wick_data['upper_wick_ratio'], wick_data['lower_wick_ratio']) <= self.config.DPC_MAX_WICK_RATIO

        # 8. Multi-timeframe confirmation (5m)
        if self.config.DPC_ENABLE_MTF:
            close_5m = indicators.get('close_5m')
            ema20_5m = indicators.get('ema20_5m')
            if close_5m and ema20_5m:
                filters['mtf_ok'] = close_5m > ema20_5m
            else:
                filters['mtf_ok'] = False
        else:
            filters['mtf_ok'] = True

        # 9. Spread filter
        filters['spread_ok'] = orderbook['spread'] <= self.config.MAX_SPREAD

        # Calculate confidence
        filters_passed = sum(filters.values())
        total_filters = len(filters)
        confidence = filters_passed / total_filters

        signal_valid = all(filters.values())

        if enable_debug:
            decision = "DPC_LONG_ENTRY" if signal_valid else "no_trade"
            print(f"[DPC][{candle_num}] {timestamp} | {decision} | "
                  f"ema_stack={filters['ema_stack_ok']} (20>{ema20:.2f}, 50>{ema50:.2f}, 100>{ema100:.2f}) | "
                  f"pullback={filters['pullback_valid']} (fib={pullback_info.get('retracement', 0):.3f}) | "
                  f"rsi_pullback={filters['rsi_pullback_ok']} | "
                  f"price_reclaim={filters['price_reclaim_ok']} | "
                  f"rsi_momentum={filters['rsi_momentum_ok']} (RSI={rsi:.1f}) | "
                  f"vol_ok={filters['volume_ok']} (ratio={vol_ratio:.2f}) | "
                  f"candle_ok={filters['candle_structure_ok']} | "
                  f"mtf_ok={filters['mtf_ok']} | "
                  f"spread_ok={filters['spread_ok']}")

        return signal_valid, confidence, filters

    def _evaluate_short_signal(self, indicators: Dict[str, Any],
                               orderbook: Dict[str, Any], candles: list,
                               enable_debug: bool = False,
                               candle_num: int = 0, timestamp=None) -> Tuple[bool, float, Dict[str, bool]]:
        """Evaluate SHORT signal (pullback in downtrend)"""
        filters = {}

        # Need EMA100
        if len(candles) < 100:
            return False, 0.0, {'not_enough_data': False}

        closes = np.array([c['close'] for c in candles])
        ema20 = self.indicators.calculate_ema(closes, 20)
        ema50 = self.indicators.calculate_ema(closes, 50)
        ema100 = self.indicators.calculate_ema(closes, 100)

        # 1. EMA Stack: EMA20 < EMA50 < EMA100
        if self.config.DPC_ENABLE_EMA_STACK:
            filters['ema_stack_ok'] = ema20 < ema50 < ema100
        else:
            filters['ema_stack_ok'] = True

        # 2. Pullback Detection
        pullback_info = self._detect_pullback(candles, 'down')
        filters['pullback_valid'] = pullback_info['valid']

        # 3. RSI in pullback zone
        rsi = indicators['rsi']
        filters['rsi_pullback_ok'] = self.config.DPC_RSI_PULLBACK_MIN <= rsi <= self.config.DPC_RSI_PULLBACK_MAX

        # 4. Price broke below EMA20
        current_close = indicators['current_close']
        if self.config.DPC_MUST_CLOSE_BEYOND_EMA20:
            filters['price_reclaim_ok'] = current_close < ema20
        else:
            filters['price_reclaim_ok'] = True

        # 5. RSI momentum resumption (45-50)
        filters['rsi_momentum_ok'] = self.config.DPC_RSI_SHORT_ENTRY_MIN <= rsi <= self.config.DPC_RSI_SHORT_ENTRY_MAX

        # 6. Volume
        vol_current = indicators['volume_current']
        vol_mean_10 = np.mean([c['volume'] for c in candles[-10:]])
        vol_ratio = vol_current / vol_mean_10 if vol_mean_10 > 0 else 0
        filters['volume_ok'] = vol_ratio >= self.config.DPC_VOL_SPIKE_MULT

        # 7. Candle structure
        current_candle = candles[-1]
        wick_data = self.indicators.calculate_wick_ratio(current_candle)
        filters['candle_structure_ok'] = max(wick_data['upper_wick_ratio'], wick_data['lower_wick_ratio']) <= self.config.DPC_MAX_WICK_RATIO

        # 8. MTF
        if self.config.DPC_ENABLE_MTF:
            close_5m = indicators.get('close_5m')
            ema20_5m = indicators.get('ema20_5m')
            if close_5m and ema20_5m:
                filters['mtf_ok'] = close_5m < ema20_5m
            else:
                filters['mtf_ok'] = False
        else:
            filters['mtf_ok'] = True

        # 9. Spread
        filters['spread_ok'] = orderbook['spread'] <= self.config.MAX_SPREAD

        filters_passed = sum(filters.values())
        total_filters = len(filters)
        confidence = filters_passed / total_filters

        signal_valid = all(filters.values())

        if enable_debug:
            decision = "DPC_SHORT_ENTRY" if signal_valid else "no_trade"
            print(f"[DPC][{candle_num}] {timestamp} | {decision} | "
                  f"ema_stack={filters['ema_stack_ok']} | "
                  f"pullback={filters['pullback_valid']} (fib={pullback_info.get('retracement', 0):.3f}) | "
                  f"rsi_pullback={filters['rsi_pullback_ok']} | "
                  f"price_reclaim={filters['price_reclaim_ok']} | "
                  f"rsi_momentum={filters['rsi_momentum_ok']} (RSI={rsi:.1f}) | "
                  f"vol_ok={filters['volume_ok']} (ratio={vol_ratio:.2f}) | "
                  f"candle_ok={filters['candle_structure_ok']} | "
                  f"mtf_ok={filters['mtf_ok']} | "
                  f"spread_ok={filters['spread_ok']}")

        return signal_valid, confidence, filters

    def check_invalidation(self, position_side: str, indicators: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if position should be invalidated based on momentum exit rules

        Args:
            position_side: 'LONG' or 'SHORT'
            indicators: Current indicator values

        Returns:
            Tuple of (should_invalidate, reason)
        """
        if position_side == 'LONG':
            # RSI reversal exit
            if self.config.DPC_EXIT_ON_RSI_REVERSAL:
                if indicators.get('rsi', 50) < 50:
                    return True, "RSI crossed below 50 (momentum reversed)"

            # EMA cross exit
            if self.config.DPC_EXIT_ON_EMA_CROSS:
                current_close = indicators.get('current_close', 0)
                ema9 = indicators.get('ema9', 0)
                ema20 = indicators.get('ema20', 0)

                if current_close < ema20 and ema9 < ema20:
                    return True, "Price below EMA20 and EMA9 crossed down"

        else:  # SHORT
            if self.config.DPC_EXIT_ON_RSI_REVERSAL:
                if indicators.get('rsi', 50) > 50:
                    return True, "RSI crossed above 50 (momentum reversed)"

            if self.config.DPC_EXIT_ON_EMA_CROSS:
                current_close = indicators.get('current_close', 0)
                ema9 = indicators.get('ema9', 0)
                ema20 = indicators.get('ema20', 0)

                if current_close > ema20 and ema9 > ema20:
                    return True, "Price above EMA20 and EMA9 crossed up"

        return False, ""

    def get_signal_summary(self, signal: SignalType, confidence: float,
                          filters: Dict[str, bool]) -> str:
        """Get human-readable summary of DPC signal"""
        if signal == SignalType.NO_TRADE:
            failed_filters = [k for k, v in filters.items() if not v]
            return f"[DPC] NO_TRADE - Failed filters: {', '.join(failed_filters) if failed_filters else 'None'}"

        passed = sum(filters.values())
        total = len(filters)
        return f"[DPC] {signal.value} - Confidence: {confidence:.2%} ({passed}/{total} filters passed)"
