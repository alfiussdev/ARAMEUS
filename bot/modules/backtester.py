"""
Backtesting engine for the Aggressive Compound Bot
Simulates trading strategy on historical data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import deque

from bot.config import Config
from bot.modules.indicators import IndicatorEngine
from bot.modules.signal_engine import SignalEngine, SignalType
from bot.modules.risk_manager import RiskManager
from bot.modules.risk_controls import RiskControls
from bot.modules.performance_metrics import PerformanceMetrics
from bot.modules.mock_logger import MockLogger


class Backtester:
    """Backtest trading strategy on historical data"""

    def __init__(self, config, initial_equity: float = 10000):
        """
        Initialize backtester

        Args:
            config: Configuration object
            initial_equity: Starting equity in USDC
        """
        self.config = config
        self.initial_equity = initial_equity
        self.current_equity = initial_equity

        # Initialize mock logger for backtest (silent)
        mock_logger = MockLogger()

        # Initialize modules with mock logger
        self.indicator_engine = IndicatorEngine(config)
        self.signal_engine = SignalEngine(config, mock_logger)
        self.risk_manager = RiskManager(config, mock_logger)
        self.risk_controls = RiskControls(config, mock_logger, backtest_mode=True)

        # State tracking
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Dict] = []
        self.equity_curve = [initial_equity]

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def run(self, data_1m: pd.DataFrame, data_5m: Optional[pd.DataFrame] = None,
            pair: str = "HYPE/USDC") -> Dict[str, Any]:
        """
        Run backtest on historical data

        Args:
            data_1m: DataFrame with 1-minute candles
            data_5m: DataFrame with 5-minute candles (optional)
            pair: Trading pair

        Returns:
            Dictionary with backtest results
        """
        print(f"\n{'='*70}")
        print(f"  BACKTESTING {pair}")
        print(f"  StrategyEngine: AggressiveCompoundBot v1.2 loaded for {pair} backtest")
        print(f"  Period: {data_1m['timestamp'].min()} to {data_1m['timestamp'].max()}")
        print(f"  Candles: {len(data_1m)}")
        print(f"  Initial Equity: ${self.initial_equity:,.2f}")
        print(f"{'='*70}\n")

        # Initialize risk controls
        self.risk_controls.initialize_equity(self.initial_equity)

        # Warm up period (need 200 candles for SMA200)
        warmup_candles = max(self.config.SMA_LONG_PERIOD, 200)

        if len(data_1m) < warmup_candles:
            raise ValueError(f"Not enough data. Need at least {warmup_candles} candles, got {len(data_1m)}")

        # Feed warmup data
        print(f"Warming up indicators ({warmup_candles} candles)...")
        for i in range(warmup_candles):
            candle = self._row_to_candle(data_1m.iloc[i])
            self.indicator_engine.update_candles(pair, candle, '1m')

            # Also feed 5m data if available
            if data_5m is not None and i < len(data_5m):
                candle_5m = self._row_to_candle(data_5m.iloc[i])
                self.indicator_engine.update_candles(pair, candle_5m, '5m')

        print(f"Starting backtest simulation...\n")

        # Candle counter for debug logging (first 5000 candles after warmup)
        candles_processed = 0
        debug_limit = 5000

        # Main backtest loop
        for i in range(warmup_candles, len(data_1m)):
            candle = self._row_to_candle(data_1m.iloc[i])
            self.indicator_engine.update_candles(pair, candle, '1m')

            # Update 5m data if available
            if data_5m is not None and i < len(data_5m):
                candle_5m = self._row_to_candle(data_5m.iloc[i])
                self.indicator_engine.update_candles(pair, candle_5m, '5m')

            # Calculate indicators
            indicators = self.indicator_engine.calculate_all_indicators(pair)
            if not indicators:
                continue

            current_price = candle['close']
            current_time = candle['timestamp']

            # Increment candle counter
            candles_processed += 1
            enable_debug = candles_processed <= debug_limit

            # Check if we have an open position
            if pair in self.positions:
                self._manage_position(pair, current_price, current_time, indicators)
            else:
                # Look for entry signals
                self._look_for_entry(pair, current_price, current_time, indicators,
                                   enable_debug=enable_debug, candle_num=candles_processed)

            # Update equity curve
            unrealized_pnl = self._calculate_unrealized_pnl(current_price)
            self.equity_curve.append(self.current_equity + unrealized_pnl)

            # Progress update every 1000 candles
            if (i - warmup_candles) % 1000 == 0:
                progress = (i - warmup_candles) / (len(data_1m) - warmup_candles) * 100
                print(f"  Progress: {progress:.1f}% | Trades: {self.total_trades} | Equity: ${self.current_equity:,.2f}")

        # Close any remaining positions
        if pair in self.positions:
            self._close_position(pair, data_1m.iloc[-1]['close'],
                                data_1m.iloc[-1]['timestamp'], "BACKTEST_END")

        print(f"\n{'='*70}")
        print(f"  BACKTEST COMPLETED")
        print(f"  Total Trades: {self.total_trades}")
        print(f"  Final Equity: ${self.current_equity:,.2f}")
        print(f"  Total Return: {((self.current_equity - self.initial_equity) / self.initial_equity * 100):.2f}%")
        print(f"{'='*70}\n")

        # Calculate performance metrics
        metrics_calc = PerformanceMetrics(self.trades, self.initial_equity)
        metrics = metrics_calc.calculate_all_metrics()

        return {
            'trades': self.trades,
            'metrics': metrics,
            'equity_curve': self.equity_curve,
            'final_equity': self.current_equity,
            'initial_equity': self.initial_equity
        }

    def _look_for_entry(self, pair: str, current_price: float,
                       current_time: datetime, indicators: Dict,
                       enable_debug: bool = False, candle_num: int = 0):
        """Look for entry signals"""

        # Check if trading is allowed
        can_trade, reason = self.risk_controls.can_trade(self.current_equity)

        if enable_debug:
            risk_ok = can_trade
            risk_reason = reason if not can_trade else "OK"

        if not can_trade:
            if enable_debug:
                print(f"[{candle_num}] {current_time} | NO_TRADE | risk_limits_ok=False ({risk_reason})")
            return

        # Simulate orderbook (spread check)
        orderbook = {
            'best_bid': current_price * 0.9995,
            'best_ask': current_price * 1.0005,
            'mid_price': current_price,
            'spread': 0.001  # 0.1% simulated spread
        }

        # Evaluate signal with debug mode
        signal, confidence, filters = self.signal_engine.evaluate_signal(
            pair, indicators, orderbook, enable_debug=enable_debug,
            candle_num=candle_num, timestamp=current_time
        )

        if signal != SignalType.NO_TRADE:
            # Calculate position parameters
            position_params = self.risk_manager.calculate_position_parameters(
                equity=self.current_equity,
                entry_price=current_price,
                volatility_ratio=indicators['volatility_ratio'],
                side=signal.value
            )

            # Validate position size
            is_valid, validation_reason = self.risk_manager.validate_position_size(
                position_size=position_params['position_size'],
                entry_price=current_price,
                equity=self.current_equity,
                leverage=position_params['leverage']
            )

            if is_valid:
                self._open_position(pair, signal.value, current_price,
                                  current_time, position_params, indicators)
                if enable_debug:
                    print(f"[{candle_num}] {current_time} | POSITION OPENED: {signal.value} | "
                          f"size={position_params['position_size']:.4f} | price={current_price:.4f}")
            else:
                # Log when signal is rejected by RiskManager
                print(f"[{candle_num}] {current_time} | SIGNAL REJECTED BY RISK_MANAGER | "
                      f"signal={signal.value} | reason={validation_reason} | "
                      f"proposed_size={position_params['position_size']:.4f}")

    def _open_position(self, pair: str, side: str, entry_price: float,
                      entry_time: datetime, position_params: Dict, indicators: Dict):
        """Open a new position"""

        # Simulate slippage
        slippage = 0.0003  # 0.03%
        if side == 'LONG':
            fill_price = entry_price * (1 + slippage)
        else:
            fill_price = entry_price * (1 - slippage)

        # Create position
        position = {
            'pair': pair,
            'side': side,
            'entry_price': fill_price,
            'entry_time': entry_time,
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
            'indicators_at_entry': indicators.copy()
        }

        self.positions[pair] = position
        self.total_trades += 1

    def _manage_position(self, pair: str, current_price: float,
                        current_time: datetime, indicators: Dict):
        """Manage open position"""

        position = self.positions[pair]
        side = position['side']

        # 1. Check stop loss
        if side == 'LONG' and current_price <= position['stop_loss_price']:
            self._close_position(pair, current_price, current_time, "STOP_LOSS")
            return

        if side == 'SHORT' and current_price >= position['stop_loss_price']:
            self._close_position(pair, current_price, current_time, "STOP_LOSS")
            return

        # 2. Check invalidation
        should_invalidate, _ = self.signal_engine.check_invalidation(side, indicators)
        if should_invalidate:
            self._close_position(pair, current_price, current_time, f"INVALIDATION_{side}")
            return

        # 3. Check TP1 (if not hit yet)
        if not position['tp1_hit']:
            tp1_hit = False

            if side == 'LONG' and current_price >= position['tp1_price']:
                tp1_hit = True
            elif side == 'SHORT' and current_price <= position['tp1_price']:
                tp1_hit = True

            if tp1_hit:
                # Close 50%
                self._close_partial_position(pair, current_price, current_time, "TP1", 0.5)
                # Move SL to breakeven
                position['stop_loss_price'] = position['entry_price']
                position['tp1_hit'] = True
                return

        # 4. Check trailing stop (if TP1 hit)
        if position['tp1_hit']:
            # Update highest/lowest
            if side == 'LONG':
                if position['highest_price'] is None or current_price > position['highest_price']:
                    position['highest_price'] = current_price

                # Calculate trailing stop
                trailing_stop = self.risk_manager.calculate_trailing_stop(
                    side=side,
                    highest_price=position['highest_price'],
                    lowest_price=0,
                    atr_current=indicators['atr_current'],
                    volatility_ratio=position['volatility_ratio']
                )

                if current_price <= trailing_stop:
                    self._close_position(pair, current_price, current_time, "TRAILING_STOP")
                    return

            else:  # SHORT
                if position['lowest_price'] is None or current_price < position['lowest_price']:
                    position['lowest_price'] = current_price

                trailing_stop = self.risk_manager.calculate_trailing_stop(
                    side=side,
                    highest_price=0,
                    lowest_price=position['lowest_price'],
                    atr_current=indicators['atr_current'],
                    volatility_ratio=position['volatility_ratio']
                )

                if current_price >= trailing_stop:
                    self._close_position(pair, current_price, current_time, "TRAILING_STOP")
                    return

    def _close_partial_position(self, pair: str, exit_price: float,
                                exit_time: datetime, reason: str, pct: float):
        """Close partial position (for TP1)"""

        position = self.positions[pair]
        close_size = position['size_remaining'] * pct

        # Update position
        position['size_remaining'] -= close_size

        # Calculate P&L for closed portion (not tracked separately in backtest)
        # Just log that TP1 was hit

    def _close_position(self, pair: str, exit_price: float,
                       exit_time: datetime, reason: str):
        """Close entire position"""

        position = self.positions.pop(pair)

        # Simulate slippage
        slippage = 0.0003
        if position['side'] == 'LONG':
            fill_price = exit_price * (1 - slippage)
        else:
            fill_price = exit_price * (1 + slippage)

        # Calculate P&L
        pnl_data = self.risk_manager.calculate_pnl(
            side=position['side'],
            entry_price=position['entry_price'],
            exit_price=fill_price,
            position_size=position['position_size'],
            fees_pct=0.0005
        )

        # Update equity
        self.current_equity += pnl_data['pnl_net']

        # Duration
        duration = (exit_time - position['entry_time']).total_seconds() / 60

        # Assess trade quality
        trade_quality = self.risk_manager.assess_trade_quality(
            pnl_pct=pnl_data['pnl_pct'],
            duration_minutes=duration,
            exit_reason=reason
        )

        # Record trade
        trade = {
            'pair': pair,
            'side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': fill_price,
            'entry_time': position['entry_time'],
            'exit_time': exit_time,
            'position_size': position['position_size'],
            'pnl_gross': pnl_data['pnl_gross'],
            'pnl_net': pnl_data['pnl_net'],
            'pnl_pct': pnl_data['pnl_pct'],
            'fees': pnl_data['fees'],
            'exit_reason': reason,
            'duration_minutes': duration,
            'r_multiple': trade_quality['r_multiple'],
            'result': trade_quality['result'],
            'tp1_hit': position['tp1_hit']
        }

        self.trades.append(trade)

        # Track wins/losses
        if pnl_data['pnl_net'] > 0:
            self.winning_trades += 1
            is_winner = True
        else:
            self.losing_trades += 1
            is_winner = False

        # Update risk controls
        self.risk_controls.record_trade(
            pair=pair,
            pnl=pnl_data['pnl_net'],
            is_winner=is_winner,
            exit_reason=reason
        )

    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate total unrealized P&L"""

        total_pnl = 0

        for pair, position in self.positions.items():
            if position['side'] == 'LONG':
                price_change = current_price - position['entry_price']
            else:
                price_change = position['entry_price'] - current_price

            pnl = price_change * position['size_remaining']
            total_pnl += pnl

        return total_pnl

    def _row_to_candle(self, row) -> Dict:
        """Convert DataFrame row to candle dict"""

        return {
            'timestamp': row['timestamp'] if isinstance(row['timestamp'], datetime) else pd.to_datetime(row['timestamp']),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume'])
        }
