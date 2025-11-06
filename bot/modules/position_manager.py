"""
Position manager module for monitoring and managing open positions
Handles TP1, trailing stops, invalidation, and stop loss monitoring
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class PositionManager:
    """Manage open positions and their exit conditions"""

    def __init__(self, config, execution_engine, risk_manager, signal_engine, logger):
        """
        Initialize position manager

        Args:
            config: Configuration object
            execution_engine: Execution engine instance
            risk_manager: Risk manager instance
            signal_engine: Signal engine instance
            logger: Logger instance
        """
        self.config = config
        self.execution = execution_engine
        self.risk_manager = risk_manager
        self.signal_engine = signal_engine
        self.logger = logger

    def monitor_position(self, pair: str, position: Dict[str, Any],
                        current_price: float, indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Monitor an open position and check for exit conditions

        Args:
            pair: Trading pair
            position: Position details
            current_price: Current market price
            indicators: Current indicator values

        Returns:
            Exit action details if position should be closed, None otherwise
        """
        side = position['side']

        # 1. Check stop loss
        sl_triggered, sl_reason = self._check_stop_loss(position, current_price)
        if sl_triggered:
            return {
                'action': 'CLOSE_ALL',
                'reason': 'STOP_LOSS',
                'details': sl_reason
            }

        # 2. Check for signal invalidation
        invalidated, inv_reason = self.signal_engine.check_invalidation(side, indicators)
        if invalidated:
            return {
                'action': 'CLOSE_ALL',
                'reason': f'INVALIDATION_{side}',
                'details': inv_reason
            }

        # 3. Check TP1 (if not yet hit)
        if not position['tp1_hit']:
            tp1_hit = self._check_tp1(position, current_price)
            if tp1_hit:
                return {
                    'action': 'CLOSE_PARTIAL',
                    'size_pct': 0.5,  # Close 50%
                    'reason': 'TP1',
                    'details': 'First take profit target reached'
                }

        # 4. Check trailing stop (if TP1 already hit)
        if position['tp1_hit']:
            trailing_triggered, trail_reason = self._check_trailing_stop(
                position, current_price, indicators
            )
            if trailing_triggered:
                return {
                    'action': 'CLOSE_ALL',
                    'reason': 'TRAILING_STOP',
                    'details': trail_reason
                }

        # No exit conditions met
        return None

    def _check_stop_loss(self, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """
        Check if stop loss is triggered

        Args:
            position: Position details
            current_price: Current market price

        Returns:
            Tuple of (is_triggered, reason)
        """
        side = position['side']
        stop_loss_price = position['stop_loss_price']

        if side == 'LONG':
            if current_price <= stop_loss_price:
                return True, f"Price ({current_price:.4f}) hit stop loss ({stop_loss_price:.4f})"
        else:  # SHORT
            if current_price >= stop_loss_price:
                return True, f"Price ({current_price:.4f}) hit stop loss ({stop_loss_price:.4f})"

        return False, ""

    def _check_tp1(self, position: Dict[str, Any], current_price: float) -> bool:
        """
        Check if TP1 is reached

        Args:
            position: Position details
            current_price: Current market price

        Returns:
            bool: True if TP1 is reached
        """
        side = position['side']
        tp1_price = position['tp1_price']

        if side == 'LONG':
            return current_price >= tp1_price
        else:  # SHORT
            return current_price <= tp1_price

    def _check_trailing_stop(self, position: Dict[str, Any], current_price: float,
                            indicators: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if trailing stop is triggered

        Args:
            position: Position details
            current_price: Current market price
            indicators: Current indicator values

        Returns:
            Tuple of (is_triggered, reason)
        """
        side = position['side']

        # Update highest/lowest price
        if side == 'LONG':
            if position['highest_price'] is None or current_price > position['highest_price']:
                position['highest_price'] = current_price

            # Calculate trailing stop
            trailing_stop = self.risk_manager.calculate_trailing_stop(
                side=side,
                highest_price=position['highest_price'],
                lowest_price=0,  # Not used for LONG
                atr_current=indicators['atr_current'],
                volatility_ratio=position['volatility_ratio']
            )

            # Check if price fell below trailing stop
            if current_price <= trailing_stop:
                return True, f"Price ({current_price:.4f}) hit trailing stop ({trailing_stop:.4f})"

        else:  # SHORT
            if position['lowest_price'] is None or current_price < position['lowest_price']:
                position['lowest_price'] = current_price

            # Calculate trailing stop
            trailing_stop = self.risk_manager.calculate_trailing_stop(
                side=side,
                highest_price=0,  # Not used for SHORT
                lowest_price=position['lowest_price'],
                atr_current=indicators['atr_current'],
                volatility_ratio=position['volatility_ratio']
            )

            # Check if price rose above trailing stop
            if current_price >= trailing_stop:
                return True, f"Price ({current_price:.4f}) hit trailing stop ({trailing_stop:.4f})"

        return False, ""

    def handle_tp1(self, pair: str, position: Dict[str, Any]) -> bool:
        """
        Handle TP1 hit: close 50% and move SL to breakeven

        Args:
            pair: Trading pair
            position: Position details

        Returns:
            bool: Success status
        """
        try:
            # Close 50% of position
            close_size = position['size_remaining'] * 0.5

            success, exit_details = self.execution.close_position(
                pair=pair,
                position=position,
                size=close_size,
                reason='TP1'
            )

            if not success:
                self.logger.log_error(
                    Exception("Failed to close position at TP1"),
                    context="handle_tp1",
                    pair=pair
                )
                return False

            # Update position state
            position['tp1_hit'] = True
            position['stop_loss_price'] = position['entry_price']  # Move to breakeven

            # Log the update
            self.logger.log_position_update(
                pair=pair,
                side=position['side'],
                update_type='TP1_HIT',
                size_closed=close_size,
                size_remaining=position['size_remaining'],
                new_stop_loss=position['stop_loss_price'],
                exit_price=exit_details['exit_price']
            )

            return True

        except Exception as e:
            self.logger.log_error(e, context="handle_tp1", pair=pair)
            return False

    def close_position_fully(self, pair: str, position: Dict[str, Any],
                           reason: str, details: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Close a position completely

        Args:
            pair: Trading pair
            position: Position details
            reason: Reason for closing
            details: Additional details

        Returns:
            Tuple of (success, pnl_data)
        """
        try:
            # Close remaining position
            success, exit_details = self.execution.close_position(
                pair=pair,
                position=position,
                size=None,  # Close all
                reason=reason
            )

            if not success:
                self.logger.log_error(
                    Exception("Failed to close position"),
                    context="close_position_fully",
                    pair=pair,
                    reason=reason
                )
                return False, None

            # Calculate P&L
            pnl_data = self.risk_manager.calculate_pnl(
                side=position['side'],
                entry_price=position['entry_price'],
                exit_price=exit_details['exit_price'],
                position_size=position['position_size'],
                fees_pct=0.0005  # 0.05% fees
            )

            # Assess trade quality
            trade_quality = self.risk_manager.assess_trade_quality(
                pnl_pct=pnl_data['pnl_pct'],
                duration_minutes=exit_details['duration_minutes'],
                exit_reason=reason
            )

            # Combine all data
            trade_summary = {
                **pnl_data,
                **trade_quality,
                'exit_details': exit_details,
                'position': position
            }

            # Log trade exit
            self.logger.log_trade_exit(
                pair=pair,
                side=position['side'],
                entry_price=position['entry_price'],
                exit_price=exit_details['exit_price'],
                size=position['position_size'],
                pnl=pnl_data['pnl_net'],
                pnl_pct=pnl_data['pnl_pct'],
                exit_reason=reason,
                duration_minutes=exit_details['duration_minutes'],
                indicators_at_exit=details,
                r_multiple=trade_quality['r_multiple'],
                trade_quality=trade_quality['result']
            )

            return True, trade_summary

        except Exception as e:
            self.logger.log_error(e, context="close_position_fully", pair=pair)
            return False, None

    def update_position_state(self, pair: str, position: Dict[str, Any],
                            current_price: float, indicators: Dict[str, Any]):
        """
        Update position state (highest/lowest prices for trailing)

        Args:
            pair: Trading pair
            position: Position details
            current_price: Current market price
            indicators: Current indicator values
        """
        side = position['side']

        # Update highest price for LONG
        if side == 'LONG':
            if position['highest_price'] is None or current_price > position['highest_price']:
                old_highest = position['highest_price']
                position['highest_price'] = current_price

                # Calculate new trailing stop
                if position['tp1_hit']:
                    trailing_stop = self.risk_manager.calculate_trailing_stop(
                        side=side,
                        highest_price=position['highest_price'],
                        lowest_price=0,
                        atr_current=indicators['atr_current'],
                        volatility_ratio=position['volatility_ratio']
                    )

                    self.logger.log_position_update(
                        pair=pair,
                        side=side,
                        update_type='TRAILING_UPDATE',
                        old_highest=old_highest,
                        new_highest=position['highest_price'],
                        trailing_stop=trailing_stop
                    )

        # Update lowest price for SHORT
        elif side == 'SHORT':
            if position['lowest_price'] is None or current_price < position['lowest_price']:
                old_lowest = position['lowest_price']
                position['lowest_price'] = current_price

                # Calculate new trailing stop
                if position['tp1_hit']:
                    trailing_stop = self.risk_manager.calculate_trailing_stop(
                        side=side,
                        highest_price=0,
                        lowest_price=position['lowest_price'],
                        atr_current=indicators['atr_current'],
                        volatility_ratio=position['volatility_ratio']
                    )

                    self.logger.log_position_update(
                        pair=pair,
                        side=side,
                        update_type='TRAILING_UPDATE',
                        old_lowest=old_lowest,
                        new_lowest=position['lowest_price'],
                        trailing_stop=trailing_stop
                    )

    def get_position_summary(self, position: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        Get a summary of position status

        Args:
            position: Position details
            current_price: Current market price

        Returns:
            Dictionary with position summary
        """
        side = position['side']

        # Calculate unrealized P&L
        if side == 'LONG':
            unrealized_pnl_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
        else:
            unrealized_pnl_pct = ((position['entry_price'] - current_price) / position['entry_price']) * 100

        unrealized_pnl = (unrealized_pnl_pct / 100) * (position['entry_price'] * position['size_remaining'])

        # Calculate distance to SL and TP
        if side == 'LONG':
            distance_to_sl_pct = ((current_price - position['stop_loss_price']) / current_price) * 100
            distance_to_tp_pct = ((position['tp1_price'] - current_price) / current_price) * 100
        else:
            distance_to_sl_pct = ((position['stop_loss_price'] - current_price) / current_price) * 100
            distance_to_tp_pct = ((current_price - position['tp1_price']) / current_price) * 100

        duration_minutes = (datetime.now() - position['entry_time']).total_seconds() / 60

        return {
            'pair': position['pair'],
            'side': side,
            'entry_price': position['entry_price'],
            'current_price': current_price,
            'size_remaining': position['size_remaining'],
            'unrealized_pnl': unrealized_pnl,
            'unrealized_pnl_pct': unrealized_pnl_pct,
            'stop_loss_price': position['stop_loss_price'],
            'tp1_price': position['tp1_price'],
            'tp1_hit': position['tp1_hit'],
            'distance_to_sl_pct': distance_to_sl_pct,
            'distance_to_tp_pct': distance_to_tp_pct,
            'duration_minutes': duration_minutes
        }
