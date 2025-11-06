"""
Aggressive Compound Bot v1.2 - Main Entry Point
Trading bot for Hyperliquid HYPE/USDC and ZEC/USDC perpetual contracts
"""

import time
import signal
import sys
from datetime import datetime
from typing import Dict, Any

from bot.config import Config
from bot.modules.logger import get_logger
from bot.modules.data_feed import HyperliquidDataFeed, SimulatedDataFeed
from bot.modules.indicators import IndicatorEngine
from bot.modules.signal_engine import SignalEngine, SignalType
from bot.modules.risk_manager import RiskManager
from bot.modules.execution_engine import ExecutionEngine
from bot.modules.position_manager import PositionManager
from bot.modules.risk_controls import RiskControls


class AggressiveCompoundBot:
    """Main bot orchestrator"""

    def __init__(self):
        """Initialize the bot and all its components"""
        print("=" * 70)
        print("  AGGRESSIVE COMPOUND BOT v1.2 - ARCANUM")
        print("  Trading on Hyperliquid: HYPE/USDC, ZEC/USDC")
        print("=" * 70)

        # Validate configuration
        try:
            Config.validate()
        except ValueError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)

        # Initialize logger
        self.logger = get_logger()
        self.logger.log_system_event("Bot initialization started", config=Config.get_summary())

        # Initialize data feed
        if Config.DRY_RUN:
            self.logger.log_system_event("Running in DRY RUN mode with simulated data")
            self.data_feed = SimulatedDataFeed(Config, self.logger)
        else:
            self.logger.log_system_event("Running in LIVE mode")
            self.data_feed = HyperliquidDataFeed(Config, self.logger)

        # Validate connection
        if not self.data_feed.validate_connection():
            self.logger.log_error(
                Exception("Failed to connect to Hyperliquid API"),
                context="initialization"
            )
            sys.exit(1)

        # Initialize modules
        self.indicator_engine = IndicatorEngine(Config)
        self.signal_engine = SignalEngine(Config, self.logger)
        self.risk_manager = RiskManager(Config, self.logger)
        self.execution_engine = ExecutionEngine(Config, self.data_feed, self.logger)
        self.risk_controls = RiskControls(Config, self.logger)

        # Position manager needs multiple dependencies
        self.position_manager = PositionManager(
            Config,
            self.execution_engine,
            self.risk_manager,
            self.signal_engine,
            self.logger
        )

        # Trading state
        self.running = False
        self.positions: Dict[str, Any] = {}

        # Performance tracking
        self.start_time = datetime.now()
        self.signals_generated = 0
        self.trades_executed = 0

        self.logger.log_system_event("Bot initialization completed successfully")

    def run(self):
        """Main bot loop"""
        self.running = True

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.log_system_event("Bot started")

        try:
            # Initialize equity tracking
            account_state = self.data_feed.get_account_state()
            if account_state:
                self.risk_controls.initialize_equity(account_state['equity'])

            # Main loop
            while self.running:
                self._run_cycle()
                time.sleep(5)  # 5 second cycle (candles close every minute)

        except Exception as e:
            self.logger.log_error(e, context="main_loop")
        finally:
            self._shutdown()

    def _run_cycle(self):
        """Run one complete trading cycle"""
        try:
            # Get account state
            account_state = self.data_feed.get_account_state()
            if not account_state:
                self.logger.log_system_event("Failed to get account state, skipping cycle")
                return

            current_equity = account_state['equity']

            # Check if trading is allowed
            can_trade, reason = self.risk_controls.can_trade(current_equity)
            if not can_trade:
                self.logger.log_system_event(
                    "Trading not allowed",
                    reason=reason,
                    risk_status=self.risk_controls.get_risk_status()
                )
                # Still monitor open positions even if we can't open new ones
                self._monitor_positions()
                return

            # Process each trading pair
            for pair in Config.TRADING_PAIRS:
                self._process_pair(pair, current_equity)

        except Exception as e:
            self.logger.log_error(e, context="run_cycle")

    def _process_pair(self, pair: str, current_equity: float):
        """
        Process a single trading pair

        Args:
            pair: Trading pair to process
            current_equity: Current account equity
        """
        try:
            # Update candle data
            candle_1m = self.data_feed.get_latest_candle(pair, '1m')
            candle_5m = self.data_feed.get_latest_candle(pair, '5m')

            if not candle_1m:
                return

            # Update indicator buffers
            self.indicator_engine.update_candles(pair, candle_1m, '1m')
            if candle_5m:
                self.indicator_engine.update_candles(pair, candle_5m, '5m')

            # Check if we have enough data
            if not self.indicator_engine.has_enough_data(pair):
                buffer_size = self.indicator_engine.get_buffer_size(pair, '1m')
                if buffer_size % 50 == 0:  # Log every 50 candles
                    self.logger.log_system_event(
                        f"Collecting data for {pair}",
                        buffer_size=buffer_size,
                        required=Config.SMA_LONG_PERIOD
                    )
                return

            # Calculate indicators
            indicators = self.indicator_engine.calculate_all_indicators(pair)
            if not indicators:
                return

            # Get orderbook data
            orderbook = self.data_feed.get_orderbook(pair)
            if not orderbook:
                return

            # Check if we have an open position
            has_position = self.execution_engine.has_open_position(pair)

            if has_position:
                # Monitor existing position
                position = self.execution_engine.get_open_position(pair)
                if position:
                    self._handle_open_position(pair, position, indicators['current_close'], indicators)
            else:
                # Look for entry signals
                if self.risk_controls.can_trade(current_equity)[0]:
                    self._look_for_entry(pair, indicators, orderbook, current_equity)

        except Exception as e:
            self.logger.log_error(e, context="process_pair", pair=pair)

    def _look_for_entry(self, pair: str, indicators: Dict[str, Any],
                       orderbook: Dict[str, Any], current_equity: float):
        """
        Look for entry signals

        Args:
            pair: Trading pair
            indicators: Current indicators
            orderbook: Orderbook data
            current_equity: Current account equity
        """
        # Evaluate signal
        signal, confidence, filters = self.signal_engine.evaluate_signal(
            pair, indicators, orderbook
        )

        self.signals_generated += 1

        # If we have a valid signal, execute
        if signal != SignalType.NO_TRADE:
            self.logger.log_system_event(
                f"Signal detected: {signal.value}",
                pair=pair,
                confidence=confidence,
                filters=filters
            )

            # Calculate position parameters
            position_params = self.risk_manager.calculate_position_parameters(
                equity=current_equity,
                entry_price=indicators['current_close'],
                volatility_ratio=indicators['volatility_ratio'],
                side=signal.value
            )

            # Validate position size
            is_valid, reason = self.risk_manager.validate_position_size(
                position_size=position_params['position_size'],
                entry_price=indicators['current_close'],
                equity=current_equity,
                leverage=position_params['leverage']
            )

            if not is_valid:
                self.logger.log_system_event(
                    "Position validation failed",
                    pair=pair,
                    reason=reason
                )
                return

            # Open position
            success, position = self.execution_engine.open_position(
                pair=pair,
                side=signal.value,
                position_params=position_params,
                entry_price=indicators['current_close']
            )

            if success:
                self.trades_executed += 1

                # Log trade entry
                self.logger.log_trade_entry(
                    pair=pair,
                    side=signal.value,
                    entry_price=position['entry_price'],
                    size=position['position_size'],
                    margin=position['margin'],
                    leverage=position['leverage'],
                    indicators=indicators,
                    confidence=confidence,
                    filters_passed=filters,
                    stop_loss=position['stop_loss_price'],
                    take_profit=position['tp1_price']
                )

                # Store position
                self.positions[pair] = position

    def _handle_open_position(self, pair: str, position: Dict[str, Any],
                             current_price: float, indicators: Dict[str, Any]):
        """
        Handle monitoring and management of an open position

        Args:
            pair: Trading pair
            position: Position details
            current_price: Current market price
            indicators: Current indicators
        """
        # Update position state (highest/lowest prices)
        self.position_manager.update_position_state(
            pair, position, current_price, indicators
        )

        # Monitor for exit conditions
        exit_action = self.position_manager.monitor_position(
            pair, position, current_price, indicators
        )

        if not exit_action:
            return

        # Handle exit action
        if exit_action['action'] == 'CLOSE_PARTIAL':
            # Handle TP1
            success = self.position_manager.handle_tp1(pair, position)
            if success:
                self.logger.log_system_event(
                    "TP1 executed, position partially closed",
                    pair=pair,
                    reason=exit_action['reason']
                )

        elif exit_action['action'] == 'CLOSE_ALL':
            # Close position completely
            success, trade_summary = self.position_manager.close_position_fully(
                pair=pair,
                position=position,
                reason=exit_action['reason'],
                details=exit_action['details']
            )

            if success:
                # Record trade with risk controls
                self.risk_controls.record_trade(
                    pair=pair,
                    pnl=trade_summary['pnl_net'],
                    is_winner=trade_summary['is_winner'],
                    exit_reason=exit_action['reason']
                )

                # Remove from positions
                if pair in self.positions:
                    del self.positions[pair]

                # Log summary
                self.logger.log_system_event(
                    "Position closed",
                    pair=pair,
                    pnl=trade_summary['pnl_net'],
                    pnl_pct=trade_summary['pnl_pct'],
                    result=trade_summary['result'],
                    r_multiple=trade_summary['r_multiple']
                )

    def _monitor_positions(self):
        """Monitor all open positions"""
        for pair in Config.TRADING_PAIRS:
            position = self.execution_engine.get_open_position(pair)
            if position:
                orderbook = self.data_feed.get_orderbook(pair)
                indicators = self.indicator_engine.calculate_all_indicators(pair)

                if orderbook and indicators:
                    self._handle_open_position(
                        pair, position, orderbook['mid_price'], indicators
                    )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.log_system_event("Shutdown signal received", signal=signum)
        self.running = False

    def _shutdown(self):
        """Graceful shutdown"""
        self.logger.log_system_event("Bot shutdown initiated")

        # Close all open positions (optional, comment out if you want to keep them)
        # for pair in self.positions.keys():
        #     position = self.positions[pair]
        #     self.execution_engine.close_position(pair, position, reason="SHUTDOWN")

        # Log final statistics
        runtime = (datetime.now() - self.start_time).total_seconds() / 3600
        stats = self.risk_controls.get_statistics()
        risk_status = self.risk_controls.get_risk_status()

        self.logger.log_daily_summary({
            'runtime_hours': runtime,
            'signals_generated': self.signals_generated,
            'trades_executed': self.trades_executed,
            'statistics': stats,
            'risk_status': risk_status
        })

        self.logger.log_system_event(
            "Bot shutdown completed",
            runtime_hours=runtime,
            total_trades=stats['total_trades'],
            win_rate=stats['win_rate'],
            total_pnl=stats['total_pnl']
        )

        print("\n" + "=" * 70)
        print("  Bot shutdown completed")
        print("  Runtime: {:.2f} hours".format(runtime))
        print("  Trades executed: {}".format(stats['total_trades']))
        print("  Win rate: {:.1f}%".format(stats['win_rate']))
        print("  Total P&L: ${:.2f}".format(stats['total_pnl']))
        print("=" * 70)


def main():
    """Main entry point"""
    bot = AggressiveCompoundBot()
    bot.run()


if __name__ == "__main__":
    main()
