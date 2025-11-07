"""
Mock logger for backtesting mode
Provides silent logging that doesn't write to files
"""


class MockLogger:
    """Silent logger for backtesting"""

    def log_system_event(self, *args, **kwargs):
        """Mock system event logging"""
        pass

    def log_trade_entry(self, *args, **kwargs):
        """Mock trade entry logging"""
        pass

    def log_trade_exit(self, *args, **kwargs):
        """Mock trade exit logging"""
        pass

    def log_signal(self, *args, **kwargs):
        """Mock signal logging"""
        pass

    def log_position_update(self, *args, **kwargs):
        """Mock position update logging"""
        pass

    def log_risk_event(self, *args, **kwargs):
        """Mock risk event logging"""
        pass

    def log_error(self, *args, **kwargs):
        """Mock error logging"""
        pass

    def log_daily_summary(self, *args, **kwargs):
        """Mock daily summary logging"""
        pass
