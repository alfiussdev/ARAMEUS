"""
LSR (Liquidity Sweep + Reaction Engine) Signal Engine

Detects false breakouts (liquidity sweeps) followed by quick reversals.
Ideal for range-bound or transitional markets where price hunts stops before reversing.

Entry Logic:
1. Detect swing high/low with multiple touches (support/resistance)
2. Identify liquidity sweep: price breaks level with volume spike, large wick, closes back inside
3. Confirm RSI divergence (price new high/low, RSI doesn't follow)
4. Wait for confirmation candle (close opposite to sweep, volume ≥1.2× avg)

Exit Logic:
- SL: Beyond sweep wick (max 0.6% of notional)
- TP1: 2.5R (50% close), TP2: 4R
- Invalidation: Price re-enters sweep zone and closes inside for 2 candles
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
import numpy as np

from bot.modules.signal_engine import SignalType


class LSRSignalEngine:
    """Signal generation engine for Liquidity Sweep + Reaction strategy"""

    def __init__(self, config, logger, indicator_engine):
        """
        Initialize LSR signal engine

        Args:
            config: Configuration object
            logger: Logger instance
            indicator_engine: IndicatorEngine instance
        """
        self.config = config
        self.logger = logger
        self.indicator_engine = indicator_engine

        # Market regime filters
        self.atr_min_ratio = getattr(config, 'LSR_ATR_MIN_RATIO', 1.0)
        self.max_spread_pct = getattr(config, 'LSR_MAX_SPREAD_PCT', 0.0025)  # 0.25%
        self.start_hour = getattr(config, 'LSR_START_HOUR', 7)
        self.end_hour = getattr(config, 'LSR_END_HOUR', 20)

        # Structure detection
        self.min_touches = getattr(config, 'LSR_MIN_TOUCHES', 3)
        self.touch_tolerance = getattr(config, 'LSR_TOUCH_TOLERANCE', 0.008)  # 0.8%

        # Sweep detection
        self.sweep_volume_mult = getattr(config, 'LSR_SWEEP_VOLUME_MULT', 2.5)
        self.sweep_min_wick = getattr(config, 'LSR_SWEEP_MIN_WICK', 0.50)  # 50%

        # Confirmation
        self.confirm_volume_mult = getattr(config, 'LSR_CONFIRM_VOLUME_MULT', 1.2)
        self.confirm_max_spread = getattr(config, 'LSR_CONFIRM_MAX_SPREAD', 0.002)  # 0.2%
        self.confirm_timeout_candles = getattr(config, 'LSR_CONFIRM_TIMEOUT', 3)

        # Exit settings
        self.max_sl_pct = getattr(config, 'LSR_MAX_SL_PCT', 0.006)  # 0.6%
        self.base_sl_pct = getattr(config, 'BASE_SL_PCT', 0.025)
        self.risk_reward_ratio = getattr(config, 'RISK_REWARD_RATIO', 2.5)
        self.tp2_rr = getattr(config, 'LSR_TP2_RR', 4.0)

        # Invalidation
        self.invalidation_candles = getattr(config, 'LSR_INVALIDATION_CANDLES', 2)
        self.volume_fade_mult = getattr(config, 'LSR_VOLUME_FADE_MULT', 0.5)

        # State tracking (for confirmation logic)
        self.pending_sweep: Optional[Dict] = None

    def evaluate_signal(self, pair: str, indicators: Dict[str, Any],
                       orderbook: Dict[str, Any], candles: List[Dict[str, Any]],
                       enable_debug: bool = False, candle_num: int = 0,
                       timestamp: datetime = None) -> Tuple[SignalType, float, Dict]:
        """
        Main entry point: evaluate LSR signal conditions

        Args:
            pair: Trading pair
            indicators: Dict with calculated indicators
            orderbook: Simulated orderbook
            candles: List of recent candles for pattern analysis
            enable_debug: Enable debug logging
            candle_num: Current candle number (for debug)
            timestamp: Current timestamp

        Returns:
            (SignalType, confidence, filters_dict)
        """
        # Check market regime first
        if not self._check_market_regime(indicators, candles, timestamp):
            return SignalType.NO_TRADE, 0.0, {'regime_ok': False}

        # Detect swing structure
        structure = self.indicator_engine.detect_swing_levels_with_touches(
            candles, self.min_touches, self.touch_tolerance
        )

        if not structure['has_valid_structure']:
            return SignalType.NO_TRADE, 0.0, {'structure_ok': False}

        # Check for liquidity sweeps
        sweep_result = self._detect_sweep_event(candles, structure, indicators)

        if sweep_result['sweep_detected']:
            # Store pending sweep for next candle confirmation
            self.pending_sweep = {
                'direction': sweep_result['direction'],
                'level': sweep_result['level'],
                'sweep_data': sweep_result['sweep_data'],
                'divergence': sweep_result['divergence'],
                'candle_num': candle_num,
                'timestamp': timestamp
            }

            if enable_debug:
                print(f"[{candle_num}] {timestamp} | SWEEP DETECTED: {sweep_result['direction']} at {sweep_result['level']:.4f}")

            return SignalType.NO_TRADE, 0.0, {'sweep_pending': True}

        # Check if we have a pending sweep awaiting confirmation
        if self.pending_sweep:
            # Check timeout
            candles_since_sweep = candle_num - self.pending_sweep['candle_num']
            if candles_since_sweep > self.confirm_timeout_candles:
                if enable_debug:
                    print(f"[{candle_num}] {timestamp} | SWEEP TIMEOUT: {self.pending_sweep['direction']}")
                self.pending_sweep = None
                return SignalType.NO_TRADE, 0.0, {'sweep_timeout': True}

            # Check confirmation
            is_confirmed = self._check_confirmation_candle(
                candles, self.pending_sweep, indicators, orderbook
            )

            if is_confirmed:
                direction = self.pending_sweep['direction']
                confidence = 0.75 + (self.pending_sweep['divergence']['divergence_strength'] * 0.25)

                if enable_debug:
                    print(f"[{candle_num}] {timestamp} | SWEEP CONFIRMED: {direction} | conf={confidence:.2f}")

                # Clear pending sweep
                signal = SignalType.LONG if direction == 'bullish_sweep' else SignalType.SHORT
                filters = {
                    'sweep_confirmed': True,
                    'divergence_strength': self.pending_sweep['divergence']['divergence_strength'],
                    'sweep_distance': self.pending_sweep['sweep_data']['sweep_distance']
                }
                self.pending_sweep = None
                return signal, confidence, filters

        return SignalType.NO_TRADE, 0.0, {'no_conditions': True}

    def _check_market_regime(self, indicators: Dict[str, Any],
                            candles: List[Dict[str, Any]],
                            timestamp: Optional[datetime]) -> bool:
        """
        Check if market conditions are suitable for LSR

        Filters:
        - Volatility: ATR(14) ≥ 1.0× ATR(50)
        - Spread: ≤ 0.25%
        - Time: London + NY overlap (07:00-20:00 UTC)
        """
        # Volatility filter
        volatility_ratio = indicators.get('volatility_ratio', 0)
        if volatility_ratio < self.atr_min_ratio:
            return False

        # Spread filter (simulated in backtest)
        spread = indicators.get('spread', 0.001)
        if spread > self.max_spread_pct:
            return False

        # Time filter
        if timestamp:
            hour = timestamp.hour
            if not (self.start_hour <= hour < self.end_hour):
                return False

        return True

    def _detect_sweep_event(self, candles: List[Dict[str, Any]],
                           structure: Dict[str, Any],
                           indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect liquidity sweep on support or resistance

        Returns:
            dict: {
                'sweep_detected': bool,
                'direction': 'bullish_sweep' or 'bearish_sweep',
                'level': float (level that was swept),
                'sweep_data': dict from detect_liquidity_sweep(),
                'divergence': dict from detect_rsi_divergence()
            }
        """
        if len(candles) < 20:
            return {'sweep_detected': False}

        # Get RSI values for divergence check
        rsi_values = []
        for i in range(-10, 0):  # Last 10 candles
            if abs(i) <= len(candles):
                idx = len(candles) + i
                if idx >= 0:
                    # Calculate RSI for this candle (simplified - use indicator engine)
                    rsi_val = indicators.get('rsi', 50)  # Use current RSI as proxy
                    rsi_values.append(rsi_val)

        # Pad RSI values to match candle count
        while len(rsi_values) < 10:
            rsi_values.insert(0, 50)

        # Check for bullish sweep (sweeps support, reacts up)
        if structure['support_level'] is not None:
            sweep_data = self.indicator_engine.detect_liquidity_sweep(
                candles, structure['support_level'], 'bullish_sweep',
                self.sweep_volume_mult, self.sweep_min_wick
            )

            if sweep_data['is_sweep']:
                # Check for bullish divergence
                divergence = self.indicator_engine.detect_rsi_divergence(
                    candles, rsi_values, 'bullish', lookback=10
                )

                if divergence['has_divergence']:
                    return {
                        'sweep_detected': True,
                        'direction': 'bullish_sweep',
                        'level': structure['support_level'],
                        'sweep_data': sweep_data,
                        'divergence': divergence
                    }

        # Check for bearish sweep (sweeps resistance, reacts down)
        if structure['resistance_level'] is not None:
            sweep_data = self.indicator_engine.detect_liquidity_sweep(
                candles, structure['resistance_level'], 'bearish_sweep',
                self.sweep_volume_mult, self.sweep_min_wick
            )

            if sweep_data['is_sweep']:
                # Check for bearish divergence
                divergence = self.indicator_engine.detect_rsi_divergence(
                    candles, rsi_values, 'bearish', lookback=10
                )

                if divergence['has_divergence']:
                    return {
                        'sweep_detected': True,
                        'direction': 'bearish_sweep',
                        'level': structure['resistance_level'],
                        'sweep_data': sweep_data,
                        'divergence': divergence
                    }

        return {'sweep_detected': False}

    def _check_confirmation_candle(self, candles: List[Dict[str, Any]],
                                   pending_sweep: Dict,
                                   indicators: Dict[str, Any],
                                   orderbook: Dict[str, Any]) -> bool:
        """
        Check if current candle confirms the sweep (reaction in opposite direction)

        Confirmation requirements:
        - Close opposite to sweep (bullish after support sweep, bearish after resistance sweep)
        - Volume ≥ 1.2× average
        - Spread ≤ 0.2%
        """
        if len(candles) < 2:
            return False

        current_candle = candles[-1]
        prev_candle = candles[-2]

        direction = pending_sweep['direction']

        # Calculate volume ratio
        if len(candles) >= 21:
            vol_candles = candles[-21:-1]
            avg_volume = np.mean([c['volume'] for c in vol_candles])
            volume_ratio = current_candle['volume'] / avg_volume if avg_volume > 0 else 0
        else:
            volume_ratio = 1.0

        # Check spread
        spread = orderbook.get('spread', 0.001)

        # Confirmation logic
        if direction == 'bullish_sweep':
            # Expect bullish confirmation (close > open)
            is_bullish_candle = current_candle['close'] > current_candle['open']
            closes_above_level = current_candle['close'] > pending_sweep['level']

            volume_ok = volume_ratio >= self.confirm_volume_mult
            spread_ok = spread <= self.confirm_max_spread

            return is_bullish_candle and closes_above_level and volume_ok and spread_ok

        elif direction == 'bearish_sweep':
            # Expect bearish confirmation (close < open)
            is_bearish_candle = current_candle['close'] < current_candle['open']
            closes_below_level = current_candle['close'] < pending_sweep['level']

            volume_ok = volume_ratio >= self.confirm_volume_mult
            spread_ok = spread <= self.confirm_max_spread

            return is_bearish_candle and closes_below_level and volume_ok and spread_ok

        return False

    def calculate_position_size(self, base_equity: float, entry_price: float,
                               sweep_distance: float, volatility_ratio: float) -> float:
        """
        Calculate adaptive position size based on sweep quality and volatility

        Args:
            base_equity: Current equity
            entry_price: Entry price
            sweep_distance: How far price swept beyond level (%)
            volatility_ratio: ATR_14 / ATR_50

        Returns:
            position_size: Size as % of equity (0.10 = 10%)
        """
        # Base size: 10-20% of equity
        base_size_pct = 0.15

        # Adjust for volatility
        if volatility_ratio > 1.3:
            base_size_pct = 0.10  # Higher vol = smaller size
        elif volatility_ratio < 1.0:
            base_size_pct = 0.20  # Lower vol = larger size

        # Adjust for sweep distance (larger sweep = higher conviction)
        if sweep_distance > 0.5:  # >0.5% sweep
            base_size_pct *= 1.1
        elif sweep_distance < 0.2:  # <0.2% sweep
            base_size_pct *= 0.9

        return min(base_size_pct, 0.20)  # Cap at 20%

    def check_invalidation(self, position_side: str, indicators: Dict[str, Any],
                          candles: List[Dict[str, Any]],
                          sweep_level: float) -> Tuple[bool, str]:
        """
        Check if LSR setup is invalidated (price re-enters sweep zone)

        Invalidation occurs when:
        - Price closes back inside sweep zone for 2 consecutive candles
        - Volume drops below 0.5× average (momentum lost)

        Args:
            position_side: 'LONG' or 'SHORT'
            indicators: Current indicators
            candles: Recent candles
            sweep_level: The level that was swept

        Returns:
            (should_exit, reason)
        """
        if len(candles) < 3:
            return False, ""

        current_candle = candles[-1]
        prev_candle = candles[-2]

        # Check if price re-entered sweep zone
        if position_side == 'LONG':
            # LONG invalidated if price closes below support again
            current_below = current_candle['close'] < sweep_level
            prev_below = prev_candle['close'] < sweep_level

            if current_below and prev_below:
                return True, "Price re-entered sweep zone (below support)"

        elif position_side == 'SHORT':
            # SHORT invalidated if price closes above resistance again
            current_above = current_candle['close'] > sweep_level
            prev_above = prev_candle['close'] > sweep_level

            if current_above and prev_above:
                return True, "Price re-entered sweep zone (above resistance)"

        # Check for volume fade
        if len(candles) >= 21:
            vol_candles = candles[-21:-1]
            avg_volume = np.mean([c['volume'] for c in vol_candles])
            current_volume = current_candle['volume']
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            if volume_ratio < self.volume_fade_mult:
                return True, f"Volume fade (ratio={volume_ratio:.2f})"

        return False, ""

    def check_adaptive_exit(self, position_side: str, indicators: Dict[str, Any],
                           current_candle: Dict[str, Any]) -> Tuple[bool, str]:
        """
        LSR doesn't use adaptive exits - uses invalidation logic instead

        Returns:
            (False, "")
        """
        return False, ""
