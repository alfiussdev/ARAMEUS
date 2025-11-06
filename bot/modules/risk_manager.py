"""
Risk management module for position sizing and risk calculations
Implements ATR-based stop loss and take profit calculations
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional


class RiskManager:
    """Manage risk parameters and position sizing"""

    def __init__(self, config, logger):
        """
        Initialize risk manager

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

    def calculate_position_parameters(self, equity: float, entry_price: float,
                                     volatility_ratio: float, side: str) -> Dict[str, Any]:
        """
        Calculate position parameters including size, SL, and TP

        IMPORTANT: Position size is inversely proportional to volatility_ratio
        to keep dollar risk constant across different volatility regimes.

        Args:
            equity: Current account equity in USDC
            entry_price: Intended entry price
            volatility_ratio: Current volatility ratio (ATR_current / ATR_mean)
            side: Position side ('LONG' or 'SHORT')

        Returns:
            Dictionary with position parameters
        """
        # Determine margin allocation based on volatility
        margin_pct = self._get_margin_allocation(volatility_ratio)
        margin = equity * margin_pct

        # Determine leverage based on volatility
        leverage = self._get_leverage(volatility_ratio)

        # Calculate stop loss percentage (wider stops in high volatility)
        sl_pct = self._calculate_sl_percentage(volatility_ratio, leverage)

        # Calculate take profit percentage (fixed R:R ratio)
        tp_pct = sl_pct * self.config.RISK_REWARD_RATIO

        # Calculate stop loss and take profit prices
        if side == 'LONG':
            stop_loss_price = entry_price * (1 - sl_pct)
            tp1_price = entry_price * (1 + tp_pct)
        else:  # SHORT
            stop_loss_price = entry_price * (1 + sl_pct)
            tp1_price = entry_price * (1 - tp_pct)

        # Calculate fixed dollar risk per trade
        risk_per_trade_usdc = margin * self.config.MAX_LOSS_PER_TRADE

        # Calculate position size inversely proportional to volatility_ratio
        # This keeps dollar risk constant: wider stops = smaller position
        #
        # Example with $10,000 equity, 20% margin, 10x leverage:
        #   Base notional = $2,000 × 10 = $20,000
        #
        # Scenario 1: Low volatility (ratio = 0.8)
        #   - SL = 0.5% × 0.8 = 0.4% (tighter stop)
        #   - Adjusted notional = $20,000 / 0.8 = $25,000 (larger position)
        #   - Risk = $25,000 × 0.4% = $100
        #
        # Scenario 2: Normal volatility (ratio = 1.0)
        #   - SL = 0.5% × 1.0 = 0.5% (normal stop)
        #   - Adjusted notional = $20,000 / 1.0 = $20,000 (normal position)
        #   - Risk = $20,000 × 0.5% = $100
        #
        # Scenario 3: High volatility (ratio = 1.5)
        #   - SL = 0.5% × 1.5 = 0.75% (wider stop)
        #   - Adjusted notional = $20,000 / 1.5 = $13,333 (smaller position)
        #   - Risk = $13,333 × 0.75% = $100
        #
        # Result: Constant $100 risk across all volatility regimes

        base_notional = margin * leverage

        # Adjust notional inversely to volatility_ratio
        # When volatility is high (ratio > 1), reduce notional
        # When volatility is low (ratio < 1), can increase notional
        adjusted_notional = base_notional / volatility_ratio

        # Calculate position size
        position_size = adjusted_notional / entry_price

        # Recalculate actual notional with adjusted size
        notional_value = position_size * entry_price

        # Validate that actual risk matches target
        actual_risk_usdc = position_size * entry_price * sl_pct
        actual_risk_pct = sl_pct * leverage

        # Log if risk calculation differs significantly from target
        if abs(actual_risk_usdc - risk_per_trade_usdc) > (risk_per_trade_usdc * 0.1):
            self.logger.log_risk_event(
                event_type='RISK_CALCULATION_ADJUSTMENT',
                severity='INFO',
                message=f'Risk adjusted for volatility: target=${risk_per_trade_usdc:.2f}, actual=${actual_risk_usdc:.2f}',
                target_risk=risk_per_trade_usdc,
                actual_risk=actual_risk_usdc,
                volatility_ratio=volatility_ratio
            )

        if actual_risk_pct > self.config.MAX_LOSS_PER_TRADE:
            self.logger.log_risk_event(
                event_type='RISK_CALCULATION_WARNING',
                severity='WARNING',
                message=f'Calculated risk ({actual_risk_pct:.2%}) exceeds max allowed ({self.config.MAX_LOSS_PER_TRADE:.2%})',
                sl_pct=sl_pct,
                leverage=leverage,
                volatility_ratio=volatility_ratio
            )

        return {
            'margin': margin,
            'margin_pct': margin_pct,
            'leverage': leverage,
            'position_size': position_size,
            'notional_value': notional_value,
            'sl_pct': sl_pct,
            'tp_pct': tp_pct,
            'stop_loss_price': stop_loss_price,
            'tp1_price': tp1_price,
            'risk_per_trade_usdc': risk_per_trade_usdc,
            'risk_per_trade_pct': risk_per_trade_usdc / equity,
            'volatility_ratio': volatility_ratio,
            'actual_risk_usdc': actual_risk_usdc
        }

    def _get_margin_allocation(self, volatility_ratio: float) -> float:
        """
        Determine margin allocation based on volatility

        Args:
            volatility_ratio: Current volatility ratio

        Returns:
            Margin percentage (0-1)
        """
        # Adjust margin based on volatility
        if volatility_ratio > self.config.VOL_RATIO_HIGH_THRESHOLD:
            # High volatility: use less margin (15%)
            return 0.15
        elif volatility_ratio < self.config.VOL_RATIO_LOW_THRESHOLD:
            # Low volatility: can use less margin (10%)
            return 0.10
        else:
            # Normal volatility: standard allocation (20%)
            return self.config.MAX_EQUITY_PER_TRADE

    def _get_leverage(self, volatility_ratio: float) -> int:
        """
        Determine leverage based on volatility

        Args:
            volatility_ratio: Current volatility ratio

        Returns:
            Leverage multiplier
        """
        # Adjust leverage based on volatility
        if volatility_ratio > self.config.VOL_RATIO_HIGH_THRESHOLD:
            # High volatility: use lower leverage
            return self.config.MIN_LEVERAGE  # 8x
        elif volatility_ratio < self.config.VOL_RATIO_LOW_THRESHOLD:
            # Low volatility: can use higher leverage
            return self.config.MAX_LEVERAGE  # 12x
        else:
            # Normal volatility: default leverage
            return self.config.DEFAULT_LEVERAGE  # 10x

    def _calculate_sl_percentage(self, volatility_ratio: float, leverage: int) -> float:
        """
        Calculate stop loss percentage based on volatility

        Args:
            volatility_ratio: Current volatility ratio
            leverage: Leverage being used

        Returns:
            Stop loss percentage (as decimal, e.g., 0.005 for 0.5%)
        """
        # Base SL adjusted by volatility
        sl_pct = self.config.BASE_SL_PCT * volatility_ratio

        # Ensure SL doesn't exceed maximum allowed risk
        max_sl_pct = self.config.MAX_LOSS_PER_TRADE / leverage

        # Cap the SL at the maximum allowed
        sl_pct = min(sl_pct, max_sl_pct)

        return sl_pct

    def calculate_trailing_stop(self, side: str, highest_price: float, lowest_price: float,
                               atr_current: float, volatility_ratio: float) -> float:
        """
        Calculate trailing stop price

        Args:
            side: Position side ('LONG' or 'SHORT')
            highest_price: Highest price reached (for LONG)
            lowest_price: Lowest price reached (for SHORT)
            atr_current: Current ATR value
            volatility_ratio: Current volatility ratio

        Returns:
            Trailing stop price
        """
        trailing_distance = atr_current * volatility_ratio

        if side == 'LONG':
            trailing_stop = highest_price - trailing_distance
        else:  # SHORT
            trailing_stop = lowest_price + trailing_distance

        return trailing_stop

    def validate_position_size(self, position_size: float, entry_price: float,
                              equity: float, leverage: int) -> Tuple[bool, str]:
        """
        Validate that position size is within acceptable limits

        Args:
            position_size: Proposed position size
            entry_price: Entry price
            equity: Current equity
            leverage: Leverage being used

        Returns:
            Tuple of (is_valid, reason)
        """
        notional = position_size * entry_price
        margin_required = notional / leverage

        # Check if margin required exceeds maximum per trade
        if margin_required > equity * self.config.MAX_EQUITY_PER_TRADE:
            return False, f"Margin required ({margin_required:.2f}) exceeds maximum ({equity * self.config.MAX_EQUITY_PER_TRADE:.2f})"

        # Check if we have enough equity
        if margin_required > equity:
            return False, f"Insufficient equity ({equity:.2f}) for required margin ({margin_required:.2f})"

        # Check minimum position size (avoid dust trades)
        min_notional = 10.0  # Minimum $10 notional
        if notional < min_notional:
            return False, f"Position size too small (notional: {notional:.2f}, minimum: {min_notional})"

        return True, "Position size valid"

    def calculate_pnl(self, side: str, entry_price: float, exit_price: float,
                     position_size: float, fees_pct: float = 0.0005) -> Dict[str, float]:
        """
        Calculate P&L for a trade

        Args:
            side: Position side ('LONG' or 'SHORT')
            entry_price: Entry price
            exit_price: Exit price
            position_size: Position size
            fees_pct: Trading fees percentage (default 0.05%)

        Returns:
            Dictionary with P&L details
        """
        if side == 'LONG':
            price_change = exit_price - entry_price
        else:  # SHORT
            price_change = entry_price - exit_price

        pnl_gross = price_change * position_size

        # Calculate fees (both entry and exit)
        entry_notional = entry_price * position_size
        exit_notional = exit_price * position_size
        total_fees = (entry_notional + exit_notional) * fees_pct

        pnl_net = pnl_gross - total_fees

        # Calculate percentage returns
        pnl_pct = (price_change / entry_price) * 100  # As percentage

        return {
            'pnl_gross': pnl_gross,
            'pnl_net': pnl_net,
            'fees': total_fees,
            'pnl_pct': pnl_pct,
            'entry_notional': entry_notional,
            'exit_notional': exit_notional
        }

    def assess_trade_quality(self, pnl_pct: float, duration_minutes: float,
                            exit_reason: str) -> Dict[str, Any]:
        """
        Assess the quality of a completed trade

        Args:
            pnl_pct: P&L percentage
            duration_minutes: Trade duration in minutes
            exit_reason: Reason for exit

        Returns:
            Dictionary with trade quality metrics
        """
        # Classify trade result
        if pnl_pct > 0:
            if exit_reason in ['TP1', 'TRAILING']:
                result = 'WINNER_PLANNED'
            else:
                result = 'WINNER_EARLY'
        else:
            if exit_reason == 'STOP_LOSS':
                result = 'LOSER_CONTROLLED'
            else:
                result = 'LOSER_INVALIDATION'

        # Calculate R-multiple (how many times our risk did we make/lose)
        # Assuming risk was 1R
        if pnl_pct > 0:
            r_multiple = abs(pnl_pct) / (self.config.BASE_SL_PCT * 100)
        else:
            r_multiple = -abs(pnl_pct) / (self.config.BASE_SL_PCT * 100)

        # Assess hold time
        if duration_minutes < 5:
            hold_time_quality = 'TOO_SHORT'
        elif duration_minutes > 240:  # More than 4 hours
            hold_time_quality = 'LONG_HOLD'
        else:
            hold_time_quality = 'NORMAL'

        return {
            'result': result,
            'r_multiple': r_multiple,
            'hold_time_quality': hold_time_quality,
            'is_winner': pnl_pct > 0,
            'exit_type': exit_reason
        }

    def get_risk_summary(self, equity: float, margin_used: float,
                        open_positions: int) -> Dict[str, Any]:
        """
        Get a summary of current risk metrics

        Args:
            equity: Current equity
            margin_used: Currently used margin
            open_positions: Number of open positions

        Returns:
            Dictionary with risk summary
        """
        margin_available = equity - margin_used
        margin_utilization = margin_used / equity if equity > 0 else 0

        return {
            'equity': equity,
            'margin_used': margin_used,
            'margin_available': margin_available,
            'margin_utilization_pct': margin_utilization * 100,
            'open_positions': open_positions,
            'max_additional_positions': int(margin_available / (equity * self.config.MAX_EQUITY_PER_TRADE))
        }
