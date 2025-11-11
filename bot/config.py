"""
Configuration module for Aggressive Compound Bot v1.2
Loads settings from environment variables and provides centralized configuration
"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Centralized configuration for the trading bot"""

    # Hyperliquid API Configuration
    HYPERLIQUID_API_KEY = os.getenv('HYPERLIQUID_API_KEY', '')
    HYPERLIQUID_SECRET_KEY = os.getenv('HYPERLIQUID_SECRET_KEY', '')
    HYPERLIQUID_WALLET_ADDRESS = os.getenv('HYPERLIQUID_WALLET_ADDRESS', '')

    # Trading Configuration
    TRADING_PAIRS: List[str] = os.getenv('TRADING_PAIRS', 'HYPE/USDC,ZEC/USDC').split(',')
    DEFAULT_LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '10'))
    MAX_LEVERAGE = int(os.getenv('MAX_LEVERAGE', '12'))
    MIN_LEVERAGE = int(os.getenv('MIN_LEVERAGE', '8'))

    # Risk Management
    MAX_EQUITY_PER_TRADE = float(os.getenv('MAX_EQUITY_PER_TRADE', '0.20'))  # 20%
    MAX_LOSS_PER_TRADE = float(os.getenv('MAX_LOSS_PER_TRADE', '0.05'))     # 5%
    DAILY_DRAWDOWN_LIMIT = float(os.getenv('DAILY_DRAWDOWN_LIMIT', '0.15'))  # 15%
    GLOBAL_DRAWDOWN_LIMIT = float(os.getenv('GLOBAL_DRAWDOWN_LIMIT', '0.25')) # 25%
    LOSS_STREAK_LIMIT = int(os.getenv('LOSS_STREAK_LIMIT', '3'))
    COOLDOWN_HOURS = int(os.getenv('COOLDOWN_HOURS', '12'))

    # Trading Parameters
    BASE_SL_PCT = float(os.getenv('BASE_SL_PCT', '0.005'))  # 0.5%
    RISK_REWARD_RATIO = float(os.getenv('RISK_REWARD_RATIO', '2.2'))
    MAX_SPREAD = float(os.getenv('MAX_SPREAD', '0.0015'))  # 0.15%

    # Volatility Thresholds
    VOL_RATIO_MIN = float(os.getenv('VOL_RATIO_MIN', '0.8'))
    VOL_RATIO_MAX = float(os.getenv('VOL_RATIO_MAX', '2.0'))
    VOL_RATIO_HIGH_THRESHOLD = float(os.getenv('VOL_RATIO_HIGH_THRESHOLD', '1.5'))
    VOL_RATIO_LOW_THRESHOLD = float(os.getenv('VOL_RATIO_LOW_THRESHOLD', '0.9'))

    # Volume Filters
    VOL_MULTIPLIER_20 = float(os.getenv('VOL_MULTIPLIER_20', '1.8'))
    VOL_MULTIPLIER_3 = float(os.getenv('VOL_MULTIPLIER_3', '1.2'))

    # RSI Thresholds
    RSI_LONG_THRESHOLD = int(os.getenv('RSI_LONG_THRESHOLD', '55'))
    RSI_LONG_MAX = int(os.getenv('RSI_LONG_MAX', '100'))  # Max RSI for LONG entry (anti-exhaustion)
    RSI_SHORT_THRESHOLD = int(os.getenv('RSI_SHORT_THRESHOLD', '45'))
    RSI_SHORT_MIN = int(os.getenv('RSI_SHORT_MIN', '0'))  # Min RSI for SHORT entry (anti-exhaustion)
    RSI_INVALIDATION_LONG = int(os.getenv('RSI_INVALIDATION_LONG', '50'))
    RSI_INVALIDATION_SHORT = int(os.getenv('RSI_INVALIDATION_SHORT', '50'))

    # Invalidation Mode
    # NONE: No early invalidation, only stops
    # LIGHT: Only RSI invalidation
    # MODERATE: RSI + VWAP invalidation
    # AGGRESSIVE: RSI + VWAP + EMA cross invalidation (original)
    INVALIDATION_MODE = os.getenv('INVALIDATION_MODE', 'AGGRESSIVE').upper()

    # Indicator Periods
    SMA_SHORT_PERIOD = int(os.getenv('SMA_SHORT_PERIOD', '50'))
    SMA_LONG_PERIOD = int(os.getenv('SMA_LONG_PERIOD', '200'))
    EMA_FAST_PERIOD = int(os.getenv('EMA_FAST_PERIOD', '9'))
    EMA_SLOW_PERIOD = int(os.getenv('EMA_SLOW_PERIOD', '20'))
    RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
    ATR_PERIOD = int(os.getenv('ATR_PERIOD', '14'))
    ATR_MEAN_PERIOD = int(os.getenv('ATR_MEAN_PERIOD', '50'))
    VOL_MEAN_PERIOD_20 = int(os.getenv('VOL_MEAN_PERIOD_20', '20'))
    VOL_MEAN_PERIOD_3 = int(os.getenv('VOL_MEAN_PERIOD_3', '3'))

    # Market Regime Filter (NEW - filters out ranging/low volatility markets)
    ENABLE_REGIME_FILTER = os.getenv('ENABLE_REGIME_FILTER', 'false').lower() == 'true'
    ATR_SHORT_PERIOD = int(os.getenv('ATR_SHORT_PERIOD', '20'))  # Short ATR for regime
    ATR_LONG_PERIOD = int(os.getenv('ATR_LONG_PERIOD', '100'))   # Long ATR for regime
    ATR_RATIO_THRESHOLD = float(os.getenv('ATR_RATIO_THRESHOLD', '0.8'))  # Min ATR_short/ATR_long
    ENABLE_ADX_FILTER = os.getenv('ENABLE_ADX_FILTER', 'false').lower() == 'true'
    ADX_PERIOD = int(os.getenv('ADX_PERIOD', '14'))
    ADX_THRESHOLD = float(os.getenv('ADX_THRESHOLD', '20'))  # Min ADX for trending market

    # 5-minute timeframe periods (for multi-timeframe analysis)
    EMA20_5M_PERIOD = 20  # EMA on 5-minute candles

    # Execution Settings
    ORDER_TIMEOUT_SECONDS = int(os.getenv('ORDER_TIMEOUT_SECONDS', '30'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY_SECONDS = int(os.getenv('RETRY_DELAY_SECONDS', '2'))

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
    LOG_TO_CONSOLE = os.getenv('LOG_TO_CONSOLE', 'true').lower() == 'true'

    # Mode
    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
    TESTNET = os.getenv('TESTNET', 'false').lower() == 'true'

    @classmethod
    def validate(cls) -> bool:
        """
        Validate configuration settings

        Returns:
            bool: True if configuration is valid, raises ValueError otherwise
        """
        if not cls.DRY_RUN:
            if not cls.HYPERLIQUID_API_KEY:
                raise ValueError("HYPERLIQUID_API_KEY is required for live trading")
            if not cls.HYPERLIQUID_SECRET_KEY:
                raise ValueError("HYPERLIQUID_SECRET_KEY is required for live trading")
            if not cls.HYPERLIQUID_WALLET_ADDRESS:
                raise ValueError("HYPERLIQUID_WALLET_ADDRESS is required for live trading")

        if cls.MIN_LEVERAGE > cls.MAX_LEVERAGE:
            raise ValueError("MIN_LEVERAGE cannot be greater than MAX_LEVERAGE")

        if cls.DEFAULT_LEVERAGE < cls.MIN_LEVERAGE or cls.DEFAULT_LEVERAGE > cls.MAX_LEVERAGE:
            raise ValueError("DEFAULT_LEVERAGE must be between MIN_LEVERAGE and MAX_LEVERAGE")

        if cls.MAX_EQUITY_PER_TRADE <= 0 or cls.MAX_EQUITY_PER_TRADE > 1:
            raise ValueError("MAX_EQUITY_PER_TRADE must be between 0 and 1")

        if cls.RISK_REWARD_RATIO <= 1:
            raise ValueError("RISK_REWARD_RATIO must be greater than 1")

        return True

    @classmethod
    def get_summary(cls) -> dict:
        """
        Get a summary of the current configuration

        Returns:
            dict: Configuration summary (excluding sensitive data)
        """
        return {
            'trading_pairs': cls.TRADING_PAIRS,
            'default_leverage': cls.DEFAULT_LEVERAGE,
            'max_equity_per_trade': cls.MAX_EQUITY_PER_TRADE,
            'max_loss_per_trade': cls.MAX_LOSS_PER_TRADE,
            'risk_reward_ratio': cls.RISK_REWARD_RATIO,
            'daily_drawdown_limit': cls.DAILY_DRAWDOWN_LIMIT,
            'global_drawdown_limit': cls.GLOBAL_DRAWDOWN_LIMIT,
            'loss_streak_limit': cls.LOSS_STREAK_LIMIT,
            'cooldown_hours': cls.COOLDOWN_HOURS,
            'dry_run': cls.DRY_RUN,
            'testnet': cls.TESTNET
        }
