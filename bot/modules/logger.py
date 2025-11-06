"""
Structured logging module for the trading bot
Provides comprehensive logging for trades, decisions, and system events
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import structlog


class BotLogger:
    """Structured logger for the trading bot"""

    def __init__(self, log_level: str = 'INFO', log_to_file: bool = True, log_to_console: bool = True):
        """
        Initialize the bot logger

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Whether to log to file
            log_to_console: Whether to log to console
        """
        self.log_level = getattr(logging, log_level.upper())
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console

        # Create logs directory if it doesn't exist
        self.logs_dir = Path('logs')
        self.logs_dir.mkdir(exist_ok=True)

        # Setup structlog
        self._setup_structlog()

        # Create separate loggers for different purposes
        self.system_logger = structlog.get_logger('system')
        self.trade_logger = structlog.get_logger('trade')
        self.decision_logger = structlog.get_logger('decision')
        self.risk_logger = structlog.get_logger('risk')

    def _setup_structlog(self):
        """Configure structlog with processors and handlers"""
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]

        # Add JSON renderer for file output
        if self.log_to_file:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Configure standard logging
        logging.basicConfig(
            format="%(message)s",
            level=self.log_level,
            handlers=self._get_handlers()
        )

    def _get_handlers(self) -> list:
        """Get logging handlers based on configuration"""
        handlers = []

        if self.log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.log_level)
            handlers.append(console_handler)

        if self.log_to_file:
            # Main log file with rotation
            today = datetime.now().strftime('%Y%m%d')
            main_log_file = self.logs_dir / f'bot_{today}.log'
            file_handler = logging.FileHandler(main_log_file)
            file_handler.setLevel(self.log_level)
            handlers.append(file_handler)

            # Separate file for trades
            trade_log_file = self.logs_dir / f'trades_{today}.log'
            self.trade_file_handler = logging.FileHandler(trade_log_file)
            self.trade_file_handler.setLevel(logging.INFO)

        return handlers

    def log_system_event(self, event: str, **kwargs):
        """
        Log a system event

        Args:
            event: Event description
            **kwargs: Additional event data
        """
        self.system_logger.info(event, **kwargs)

    def log_trade_entry(self, pair: str, side: str, entry_price: float, size: float,
                       margin: float, leverage: float, indicators: Dict[str, Any], **kwargs):
        """
        Log a trade entry

        Args:
            pair: Trading pair
            side: LONG or SHORT
            entry_price: Entry price
            size: Position size
            margin: Margin used
            leverage: Leverage used
            indicators: Dictionary of indicator values at entry
            **kwargs: Additional trade data
        """
        trade_data = {
            'event': 'TRADE_ENTRY',
            'timestamp': datetime.now().isoformat(),
            'pair': pair,
            'side': side,
            'entry_price': entry_price,
            'size': size,
            'margin': margin,
            'leverage': leverage,
            'indicators': indicators,
            **kwargs
        }

        self.trade_logger.info('trade_entry', **trade_data)

        # Also write to trade file
        if self.log_to_file:
            with open(self.logs_dir / f'trades_{datetime.now().strftime("%Y%m%d")}.log', 'a') as f:
                f.write(json.dumps(trade_data) + '\n')

    def log_trade_exit(self, pair: str, side: str, entry_price: float, exit_price: float,
                      size: float, pnl: float, pnl_pct: float, exit_reason: str,
                      duration_minutes: float, **kwargs):
        """
        Log a trade exit

        Args:
            pair: Trading pair
            side: LONG or SHORT
            entry_price: Entry price
            exit_price: Exit price
            size: Position size closed
            pnl: Profit/Loss in USDC
            pnl_pct: Profit/Loss percentage
            exit_reason: Reason for exit (TP1, TRAILING, STOP_LOSS, INVALIDATION, etc.)
            duration_minutes: Trade duration in minutes
            **kwargs: Additional trade data
        """
        trade_data = {
            'event': 'TRADE_EXIT',
            'timestamp': datetime.now().isoformat(),
            'pair': pair,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size': size,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'duration_minutes': duration_minutes,
            **kwargs
        }

        self.trade_logger.info('trade_exit', **trade_data)

        # Also write to trade file
        if self.log_to_file:
            with open(self.logs_dir / f'trades_{datetime.now().strftime("%Y%m%d")}.log', 'a') as f:
                f.write(json.dumps(trade_data) + '\n')

    def log_signal(self, pair: str, signal: str, confidence: float, indicators: Dict[str, Any],
                   filters_passed: Dict[str, bool], **kwargs):
        """
        Log a trading signal evaluation

        Args:
            pair: Trading pair
            signal: Signal type (LONG, SHORT, NO_TRADE)
            confidence: Signal confidence (0-1)
            indicators: Current indicator values
            filters_passed: Dictionary of filter results
            **kwargs: Additional signal data
        """
        signal_data = {
            'event': 'SIGNAL_EVALUATION',
            'timestamp': datetime.now().isoformat(),
            'pair': pair,
            'signal': signal,
            'confidence': confidence,
            'indicators': indicators,
            'filters_passed': filters_passed,
            **kwargs
        }

        self.decision_logger.info('signal_evaluation', **signal_data)

    def log_position_update(self, pair: str, side: str, update_type: str, **kwargs):
        """
        Log a position update (TP1 hit, trailing stop update, etc.)

        Args:
            pair: Trading pair
            side: LONG or SHORT
            update_type: Type of update (TP1_HIT, TRAILING_UPDATE, SL_MOVED, etc.)
            **kwargs: Additional update data
        """
        update_data = {
            'event': 'POSITION_UPDATE',
            'timestamp': datetime.now().isoformat(),
            'pair': pair,
            'side': side,
            'update_type': update_type,
            **kwargs
        }

        self.trade_logger.info('position_update', **update_data)

    def log_risk_event(self, event_type: str, severity: str, message: str, **kwargs):
        """
        Log a risk management event

        Args:
            event_type: Type of risk event (LOSS_STREAK, DAILY_LIMIT, GLOBAL_LIMIT, etc.)
            severity: Severity level (INFO, WARNING, CRITICAL)
            message: Event description
            **kwargs: Additional risk data
        """
        risk_data = {
            'event': 'RISK_EVENT',
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'message': message,
            **kwargs
        }

        if severity == 'CRITICAL':
            self.risk_logger.critical('risk_event', **risk_data)
        elif severity == 'WARNING':
            self.risk_logger.warning('risk_event', **risk_data)
        else:
            self.risk_logger.info('risk_event', **risk_data)

    def log_error(self, error: Exception, context: str, **kwargs):
        """
        Log an error with context

        Args:
            error: Exception object
            context: Context where error occurred
            **kwargs: Additional error data
        """
        error_data = {
            'event': 'ERROR',
            'timestamp': datetime.now().isoformat(),
            'context': context,
            'error_type': type(error).__name__,
            'error_message': str(error),
            **kwargs
        }

        self.system_logger.error('error', **error_data, exc_info=True)

    def log_daily_summary(self, summary: Dict[str, Any]):
        """
        Log a daily summary of trading activity

        Args:
            summary: Dictionary containing daily statistics
        """
        summary_data = {
            'event': 'DAILY_SUMMARY',
            'timestamp': datetime.now().isoformat(),
            **summary
        }

        self.system_logger.info('daily_summary', **summary_data)

        # Write to separate summary file
        if self.log_to_file:
            summary_file = self.logs_dir / 'daily_summaries.log'
            with open(summary_file, 'a') as f:
                f.write(json.dumps(summary_data) + '\n')


# Global logger instance
_logger_instance: Optional[BotLogger] = None


def get_logger() -> BotLogger:
    """
    Get the global logger instance

    Returns:
        BotLogger: The global logger instance
    """
    global _logger_instance
    if _logger_instance is None:
        from bot.config import Config
        _logger_instance = BotLogger(
            log_level=Config.LOG_LEVEL,
            log_to_file=Config.LOG_TO_FILE,
            log_to_console=Config.LOG_TO_CONSOLE
        )
    return _logger_instance
