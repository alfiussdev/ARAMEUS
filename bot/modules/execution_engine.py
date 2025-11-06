"""
Execution engine module for order management
Handles order placement, cancellation, and validation
"""

import time
import uuid
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime


class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ExecutionEngine:
    """Handle order execution and management"""

    def __init__(self, config, data_feed, logger):
        """
        Initialize execution engine

        Args:
            config: Configuration object
            data_feed: Data feed instance
            logger: Logger instance
        """
        self.config = config
        self.data_feed = data_feed
        self.logger = logger

        # Track active orders
        self.active_orders: Dict[str, Dict[str, Any]] = {}

        # Simulated fills for dry run mode
        self.simulated_positions: Dict[str, Dict[str, Any]] = {}

    def open_position(self, pair: str, side: str, position_params: Dict[str, Any],
                     entry_price: Optional[float] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Open a new position

        Args:
            pair: Trading pair
            side: Position side ('LONG' or 'SHORT')
            position_params: Position parameters from risk manager
            entry_price: Optional specific entry price (if None, uses market price)

        Returns:
            Tuple of (success, position_details)
        """
        try:
            # Generate order ID
            order_id = str(uuid.uuid4())

            # Get entry price
            if entry_price is None:
                orderbook = self.data_feed.get_orderbook(pair)
                if not orderbook:
                    self.logger.log_error(
                        Exception("Failed to get orderbook"),
                        context="open_position",
                        pair=pair
                    )
                    return False, None

                # Use mid price for market order
                entry_price = orderbook['mid_price']

            # Validate order parameters
            is_valid, reason = self._validate_order_params(
                pair, side, position_params['position_size'], entry_price
            )

            if not is_valid:
                self.logger.log_system_event(
                    "Order validation failed",
                    pair=pair,
                    side=side,
                    reason=reason
                )
                return False, None

            # Execute order based on mode
            if self.config.DRY_RUN:
                success, fill_price = self._simulate_market_order(
                    pair, side, position_params['position_size'], entry_price
                )
            else:
                success, fill_price = self._execute_market_order(
                    pair, side, position_params['position_size']
                )

            if not success:
                return False, None

            # Create position record
            position = {
                'order_id': order_id,
                'pair': pair,
                'side': side,
                'entry_price': fill_price,
                'entry_time': datetime.now(),
                'position_size': position_params['position_size'],
                'notional_value': position_params['notional_value'],
                'margin': position_params['margin'],
                'leverage': position_params['leverage'],
                'stop_loss_price': position_params['stop_loss_price'],
                'tp1_price': position_params['tp1_price'],
                'sl_pct': position_params['sl_pct'],
                'tp_pct': position_params['tp_pct'],
                'volatility_ratio': position_params['volatility_ratio'],
                'tp1_hit': False,
                'size_remaining': position_params['position_size'],
                'highest_price': fill_price if side == 'LONG' else None,
                'lowest_price': fill_price if side == 'SHORT' else None,
                'status': 'OPEN'
            }

            # Store in active positions
            if self.config.DRY_RUN:
                self.simulated_positions[pair] = position

            self.logger.log_system_event(
                "Position opened successfully",
                pair=pair,
                side=side,
                entry_price=fill_price,
                size=position_params['position_size'],
                stop_loss=position_params['stop_loss_price'],
                take_profit=position_params['tp1_price']
            )

            return True, position

        except Exception as e:
            self.logger.log_error(e, context="open_position", pair=pair, side=side)
            return False, None

    def close_position(self, pair: str, position: Dict[str, Any],
                      size: Optional[float] = None, reason: str = "MANUAL") -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Close a position (fully or partially)

        Args:
            pair: Trading pair
            position: Position details
            size: Size to close (if None, closes entire position)
            reason: Reason for closing

        Returns:
            Tuple of (success, exit_details)
        """
        try:
            # Determine size to close
            close_size = size if size is not None else position['size_remaining']

            if close_size <= 0:
                return False, None

            # Get exit price
            orderbook = self.data_feed.get_orderbook(pair)
            if not orderbook:
                return False, None

            exit_price = orderbook['mid_price']

            # Execute close order
            if self.config.DRY_RUN:
                success, fill_price = self._simulate_close_order(
                    pair, position['side'], close_size, exit_price
                )
            else:
                success, fill_price = self._execute_close_order(
                    pair, position['side'], close_size
                )

            if not success:
                return False, None

            # Calculate duration
            duration = (datetime.now() - position['entry_time']).total_seconds() / 60

            # Update position
            position['size_remaining'] -= close_size

            if position['size_remaining'] <= 0:
                position['status'] = 'CLOSED'
                position['exit_time'] = datetime.now()
                position['exit_price'] = fill_price
                position['exit_reason'] = reason

                # Remove from active positions
                if self.config.DRY_RUN and pair in self.simulated_positions:
                    del self.simulated_positions[pair]

            exit_details = {
                'exit_price': fill_price,
                'size_closed': close_size,
                'exit_reason': reason,
                'duration_minutes': duration
            }

            self.logger.log_system_event(
                "Position closed",
                pair=pair,
                side=position['side'],
                exit_price=fill_price,
                size_closed=close_size,
                reason=reason,
                duration_minutes=duration
            )

            return True, exit_details

        except Exception as e:
            self.logger.log_error(e, context="close_position", pair=pair, reason=reason)
            return False, None

    def _validate_order_params(self, pair: str, side: str, size: float,
                               price: float) -> Tuple[bool, str]:
        """
        Validate order parameters

        Args:
            pair: Trading pair
            side: Order side
            size: Order size
            price: Order price

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check size is positive
        if size <= 0:
            return False, "Size must be positive"

        # Check price is positive
        if price <= 0:
            return False, "Price must be positive"

        # Check minimum notional
        notional = size * price
        if notional < 10:
            return False, f"Notional value ({notional:.2f}) below minimum (10)"

        return True, "Valid"

    def _simulate_market_order(self, pair: str, side: str, size: float,
                              price: float) -> Tuple[bool, float]:
        """
        Simulate a market order execution (for dry run mode)

        Args:
            pair: Trading pair
            side: Order side
            size: Order size
            price: Expected price

        Returns:
            Tuple of (success, fill_price)
        """
        # Simulate slippage (0.01% - 0.05%)
        import random
        slippage = random.uniform(0.0001, 0.0005)

        if side == 'LONG':
            fill_price = price * (1 + slippage)  # Buy at ask
        else:
            fill_price = price * (1 - slippage)  # Sell at bid

        self.logger.log_system_event(
            "Simulated market order",
            pair=pair,
            side=side,
            size=size,
            fill_price=fill_price,
            slippage_pct=slippage * 100
        )

        return True, fill_price

    def _simulate_close_order(self, pair: str, side: str, size: float,
                             price: float) -> Tuple[bool, float]:
        """
        Simulate closing an order (for dry run mode)

        Args:
            pair: Trading pair
            side: Original position side
            size: Size to close
            price: Expected price

        Returns:
            Tuple of (success, fill_price)
        """
        # Simulate slippage
        import random
        slippage = random.uniform(0.0001, 0.0005)

        # Close order is opposite direction
        if side == 'LONG':
            fill_price = price * (1 - slippage)  # Sell at bid
        else:
            fill_price = price * (1 + slippage)  # Buy at ask

        self.logger.log_system_event(
            "Simulated close order",
            pair=pair,
            side='CLOSE_' + side,
            size=size,
            fill_price=fill_price
        )

        return True, fill_price

    def _execute_market_order(self, pair: str, side: str, size: float) -> Tuple[bool, float]:
        """
        Execute a real market order via Hyperliquid API

        Args:
            pair: Trading pair
            side: Order side
            size: Order size

        Returns:
            Tuple of (success, fill_price)
        """
        # This would integrate with Hyperliquid's actual order API
        # For now, this is a placeholder that should be implemented
        # based on Hyperliquid's SDK or REST API documentation

        self.logger.log_system_event(
            "Live trading not fully implemented",
            pair=pair,
            side=side,
            message="Please implement Hyperliquid order execution API"
        )

        # Return failure for now
        return False, 0.0

    def _execute_close_order(self, pair: str, side: str, size: float) -> Tuple[bool, float]:
        """
        Execute a real close order via Hyperliquid API

        Args:
            pair: Trading pair
            side: Original position side
            size: Size to close

        Returns:
            Tuple of (success, fill_price)
        """
        # This would integrate with Hyperliquid's actual order API
        # Placeholder for now

        self.logger.log_system_event(
            "Live trading not fully implemented",
            pair=pair,
            side='CLOSE_' + side,
            message="Please implement Hyperliquid close order API"
        )

        return False, 0.0

    def cancel_all_orders(self, pair: str) -> bool:
        """
        Cancel all pending orders for a pair

        Args:
            pair: Trading pair

        Returns:
            bool: Success status
        """
        try:
            if self.config.DRY_RUN:
                self.logger.log_system_event(
                    "Cancelled all orders (simulated)",
                    pair=pair
                )
                return True

            # Implement actual order cancellation via API
            return True

        except Exception as e:
            self.logger.log_error(e, context="cancel_all_orders", pair=pair)
            return False

    def get_open_position(self, pair: str) -> Optional[Dict[str, Any]]:
        """
        Get open position for a pair

        Args:
            pair: Trading pair

        Returns:
            Position details or None
        """
        if self.config.DRY_RUN:
            return self.simulated_positions.get(pair)
        else:
            # Get from API
            return self.data_feed.get_current_position(pair)

    def has_open_position(self, pair: str) -> bool:
        """
        Check if there's an open position for a pair

        Args:
            pair: Trading pair

        Returns:
            bool: True if position is open
        """
        position = self.get_open_position(pair)
        return position is not None and position.get('status') == 'OPEN'
