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

    # ========================================================================
    # VRR STRATEGY CONFIGURATION (Volatility Rejection Reversal)
    # ========================================================================

    # Strategy Selection
    STRATEGY_TYPE = os.getenv('STRATEGY_TYPE', 'PULLBACK').upper()  # VRR or PULLBACK

    # VRR Entry Conditions
    VRR_DIRECTION_PERIOD = int(os.getenv('VRR_DIRECTION_PERIOD', '5'))
    VRR_DIRECTION_ATR_MULT = float(os.getenv('VRR_DIRECTION_ATR_MULT', '1.8'))
    RSI_EXTREME_LONG = int(os.getenv('RSI_EXTREME_LONG', '20'))
    RSI_EXTREME_SHORT = int(os.getenv('RSI_EXTREME_SHORT', '80'))

    # VRR Volume Filters
    VRR_VOL_SPIKE_MULT = float(os.getenv('VRR_VOL_SPIKE_MULT', '4.0'))
    VRR_VOL_PERIOD = int(os.getenv('VRR_VOL_PERIOD', '20'))
    VRR_VOL_CONFIRMATION_PERIOD = int(os.getenv('VRR_VOL_CONFIRMATION_PERIOD', '10'))

    # VRR Candle Structure
    VRR_MIN_WICK_RATIO = float(os.getenv('VRR_MIN_WICK_RATIO', '0.40'))
    VRR_STRONG_WICK_RATIO = float(os.getenv('VRR_STRONG_WICK_RATIO', '0.70'))
    VRR_MIN_BODY_RATIO = float(os.getenv('VRR_MIN_BODY_RATIO', '0.20'))

    # VRR Volume Divergence
    VRR_ENABLE_VOL_DIVERGENCE = os.getenv('VRR_ENABLE_VOL_DIVERGENCE', 'true').lower() == 'true'
    VRR_DIVERGENCE_LOOKBACK = int(os.getenv('VRR_DIVERGENCE_LOOKBACK', '3'))

    # VRR Market Regime Filters
    VRR_ENABLE_VOL_FILTER = os.getenv('VRR_ENABLE_VOL_FILTER', 'true').lower() == 'true'
    VRR_ATR_CURRENT_PERIOD = int(os.getenv('VRR_ATR_CURRENT_PERIOD', '14'))
    VRR_ATR_BASELINE_PERIOD = int(os.getenv('VRR_ATR_BASELINE_PERIOD', '50'))
    VRR_ATR_MIN_RATIO = float(os.getenv('VRR_ATR_MIN_RATIO', '1.2'))

    VRR_ENABLE_TREND_FILTER = os.getenv('VRR_ENABLE_TREND_FILTER', 'true').lower() == 'true'
    VRR_EMA_FAST = int(os.getenv('VRR_EMA_FAST', '20'))
    VRR_EMA_SLOW = int(os.getenv('VRR_EMA_SLOW', '50'))
    VRR_MIN_EMA_SEPARATION = float(os.getenv('VRR_MIN_EMA_SEPARATION', '0.003'))

    VRR_ENABLE_TIME_FILTER = os.getenv('VRR_ENABLE_TIME_FILTER', 'true').lower() == 'true'
    VRR_START_HOUR = int(os.getenv('VRR_START_HOUR', '12'))
    VRR_END_HOUR = int(os.getenv('VRR_END_HOUR', '22'))

    # VRR Multi-Timeframe Confirmation
    VRR_ENABLE_MTF = os.getenv('VRR_ENABLE_MTF', 'true').lower() == 'true'
    VRR_CONFIRMATION_TIMEFRAME = os.getenv('VRR_CONFIRMATION_TIMEFRAME', '5m')
    VRR_MTF_RSI_LONG = int(os.getenv('VRR_MTF_RSI_LONG', '30'))
    VRR_MTF_RSI_SHORT = int(os.getenv('VRR_MTF_RSI_SHORT', '70'))

    # VRR Structural Validation
    VRR_ENABLE_STRUCTURE_CHECK = os.getenv('VRR_ENABLE_STRUCTURE_CHECK', 'true').lower() == 'true'
    VRR_MUST_CLOSE_IN_PREV_RANGE = os.getenv('VRR_MUST_CLOSE_IN_PREV_RANGE', 'true').lower() == 'true'
    VRR_CHECK_LIQUIDITY_ZONE = os.getenv('VRR_CHECK_LIQUIDITY_ZONE', 'true').lower() == 'true'
    VRR_LIQUIDITY_LOOKBACK = int(os.getenv('VRR_LIQUIDITY_LOOKBACK', '20'))

    # VRR Adaptive Exit
    TP2_RATIO = float(os.getenv('TP2_RATIO', '3.0'))
    VRR_EXIT_ON_VOLUME_DROP = os.getenv('VRR_EXIT_ON_VOLUME_DROP', 'true').lower() == 'true'
    VRR_EXIT_ON_RSI_NEUTRAL = os.getenv('VRR_EXIT_ON_RSI_NEUTRAL', 'true').lower() == 'true'
    VRR_EXIT_ON_COUNTER_CANDLE = os.getenv('VRR_EXIT_ON_COUNTER_CANDLE', 'true').lower() == 'true'

    # VRR Dynamic Position Sizing
    VRR_ENABLE_DYNAMIC_SIZE = os.getenv('VRR_ENABLE_DYNAMIC_SIZE', 'true').lower() == 'true'
    VRR_FULL_SIZE_RSI_LONG = int(os.getenv('VRR_FULL_SIZE_RSI_LONG', '20'))
    VRR_FULL_SIZE_RSI_SHORT = int(os.getenv('VRR_FULL_SIZE_RSI_SHORT', '80'))
    VRR_FULL_SIZE_REQUIRES_DIVERGENCE = os.getenv('VRR_FULL_SIZE_REQUIRES_DIVERGENCE', 'true').lower() == 'true'
    VRR_HALF_SIZE_RSI_RANGE_LOW = int(os.getenv('VRR_HALF_SIZE_RSI_RANGE_LOW', '70'))
    VRR_HALF_SIZE_RSI_RANGE_HIGH = int(os.getenv('VRR_HALF_SIZE_RSI_RANGE_HIGH', '75'))
    VRR_MTF_SIZE_MULTIPLIER = float(os.getenv('VRR_MTF_SIZE_MULTIPLIER', '1.2'))

    # VRR Fail-Safe Conditions
    VRR_MAX_CANDLES_WAIT = int(os.getenv('VRR_MAX_CANDLES_WAIT', '3'))
    VRR_CANCEL_ON_VWAP_CROSS = os.getenv('VRR_CANCEL_ON_VWAP_CROSS', 'true').lower() == 'true'
    VRR_CANCEL_ON_NEW_EXPANSION = os.getenv('VRR_CANCEL_ON_NEW_EXPANSION', 'true').lower() == 'true'

    # ========================================================================
    # DPC STRATEGY CONFIGURATION (Dynamic Pullback Continuation)
    # ========================================================================

    # DPC Market Regime Filters
    DPC_ENABLE_EMA_STACK = os.getenv('DPC_ENABLE_EMA_STACK', 'true').lower() == 'true'
    DPC_EMA_FAST = int(os.getenv('DPC_EMA_FAST', '20'))
    DPC_EMA_MID = int(os.getenv('DPC_EMA_MID', '50'))
    DPC_EMA_SLOW = int(os.getenv('DPC_EMA_SLOW', '100'))

    DPC_ENABLE_VOL_FILTER = os.getenv('DPC_ENABLE_VOL_FILTER', 'true').lower() == 'true'
    DPC_ATR_CURRENT_PERIOD = int(os.getenv('DPC_ATR_CURRENT_PERIOD', '14'))
    DPC_ATR_BASELINE_PERIOD = int(os.getenv('DPC_ATR_BASELINE_PERIOD', '50'))
    DPC_ATR_MIN_RATIO = float(os.getenv('DPC_ATR_MIN_RATIO', '1.1'))

    DPC_ENABLE_CHOP_FILTER = os.getenv('DPC_ENABLE_CHOP_FILTER', 'true').lower() == 'true'
    DPC_CHOP_LOOKBACK = int(os.getenv('DPC_CHOP_LOOKBACK', '30'))
    DPC_MAX_EMA20_CROSSES = int(os.getenv('DPC_MAX_EMA20_CROSSES', '2'))

    DPC_ENABLE_TIME_FILTER = os.getenv('DPC_ENABLE_TIME_FILTER', 'true').lower() == 'true'
    DPC_START_HOUR = int(os.getenv('DPC_START_HOUR', '7'))
    DPC_END_HOUR = int(os.getenv('DPC_END_HOUR', '20'))

    # DPC Pullback Detection
    DPC_MIN_PULLBACK_CANDLES = int(os.getenv('DPC_MIN_PULLBACK_CANDLES', '3'))
    DPC_SWING_LOOKBACK = int(os.getenv('DPC_SWING_LOOKBACK', '20'))
    DPC_FIB_MIN = float(os.getenv('DPC_FIB_MIN', '0.382'))
    DPC_FIB_MAX = float(os.getenv('DPC_FIB_MAX', '0.618'))
    DPC_RSI_PULLBACK_MIN = int(os.getenv('DPC_RSI_PULLBACK_MIN', '45'))
    DPC_RSI_PULLBACK_MAX = int(os.getenv('DPC_RSI_PULLBACK_MAX', '55'))

    # DPC Entry Conditions
    DPC_MUST_CLOSE_BEYOND_EMA20 = os.getenv('DPC_MUST_CLOSE_BEYOND_EMA20', 'true').lower() == 'true'
    DPC_RSI_LONG_ENTRY_MIN = int(os.getenv('DPC_RSI_LONG_ENTRY_MIN', '50'))
    DPC_RSI_LONG_ENTRY_MAX = int(os.getenv('DPC_RSI_LONG_ENTRY_MAX', '55'))
    DPC_RSI_SHORT_ENTRY_MIN = int(os.getenv('DPC_RSI_SHORT_ENTRY_MIN', '45'))
    DPC_RSI_SHORT_ENTRY_MAX = int(os.getenv('DPC_RSI_SHORT_ENTRY_MAX', '50'))
    DPC_VOL_SPIKE_MULT = float(os.getenv('DPC_VOL_SPIKE_MULT', '1.8'))
    DPC_VOL_PERIOD = int(os.getenv('DPC_VOL_PERIOD', '10'))
    DPC_MAX_WICK_RATIO = float(os.getenv('DPC_MAX_WICK_RATIO', '0.30'))
    DPC_ENABLE_MTF = os.getenv('DPC_ENABLE_MTF', 'true').lower() == 'true'

    # DPC Position Sizing
    DPC_ENABLE_DYNAMIC_SIZING = os.getenv('DPC_ENABLE_DYNAMIC_SIZING', 'true').lower() == 'true'
    DPC_BASE_MARGIN_PCT = float(os.getenv('DPC_BASE_MARGIN_PCT', '0.15'))
    DPC_HIGH_VOL_ATR_RATIO = float(os.getenv('DPC_HIGH_VOL_ATR_RATIO', '1.5'))
    DPC_HIGH_VOL_MARGIN_PCT = float(os.getenv('DPC_HIGH_VOL_MARGIN_PCT', '0.10'))
    DPC_LOW_VOL_ATR_RATIO = float(os.getenv('DPC_LOW_VOL_ATR_RATIO', '1.0'))
    DPC_LOW_VOL_MARGIN_PCT = float(os.getenv('DPC_LOW_VOL_MARGIN_PCT', '0.20'))

    # DPC Exit Logic
    DPC_SL_TYPE = os.getenv('DPC_SL_TYPE', 'swing')
    DPC_SWING_SL_BUFFER = float(os.getenv('DPC_SWING_SL_BUFFER', '0.002'))
    DPC_FIXED_SL_PCT = float(os.getenv('DPC_FIXED_SL_PCT', '0.025'))
    DPC_ADJUST_SL_BY_ATR = os.getenv('DPC_ADJUST_SL_BY_ATR', 'true').lower() == 'true'
    DPC_HIGH_VOL_SL_MULT = float(os.getenv('DPC_HIGH_VOL_SL_MULT', '1.3'))
    DPC_LOW_VOL_SL_MULT = float(os.getenv('DPC_LOW_VOL_SL_MULT', '0.8'))
    DPC_ENABLE_BREAKEVEN_MOVE = os.getenv('DPC_ENABLE_BREAKEVEN_MOVE', 'true').lower() == 'true'
    DPC_BE_RSI_LONG = int(os.getenv('DPC_BE_RSI_LONG', '70'))
    DPC_BE_RSI_SHORT = int(os.getenv('DPC_BE_RSI_SHORT', '30'))
    DPC_BE_BUFFER = float(os.getenv('DPC_BE_BUFFER', '0.005'))

    # DPC Momentum Exit
    DPC_EXIT_ON_RSI_REVERSAL = os.getenv('DPC_EXIT_ON_RSI_REVERSAL', 'true').lower() == 'true'
    DPC_EXIT_ON_VOL_FADE = os.getenv('DPC_EXIT_ON_VOL_FADE', 'true').lower() == 'true'
    DPC_VOL_FADE_CANDLES = int(os.getenv('DPC_VOL_FADE_CANDLES', '2'))
    DPC_VOL_FADE_RATIO = float(os.getenv('DPC_VOL_FADE_RATIO', '0.60'))
    DPC_EXIT_ON_EMA_CROSS = os.getenv('DPC_EXIT_ON_EMA_CROSS', 'true').lower() == 'true'

    # ========================================================================
    # LSR (Liquidity Sweep + Reaction Engine) Strategy Parameters
    # ========================================================================

    # LSR Market Regime Filters
    LSR_ATR_MIN_RATIO = float(os.getenv('LSR_ATR_MIN_RATIO', '1.0'))
    LSR_MAX_SPREAD_PCT = float(os.getenv('LSR_MAX_SPREAD_PCT', '0.0025'))
    LSR_START_HOUR = int(os.getenv('LSR_START_HOUR', '7'))
    LSR_END_HOUR = int(os.getenv('LSR_END_HOUR', '20'))

    # LSR Structure Detection (Swing Levels with Multiple Touches)
    LSR_MIN_TOUCHES = int(os.getenv('LSR_MIN_TOUCHES', '3'))
    LSR_TOUCH_TOLERANCE = float(os.getenv('LSR_TOUCH_TOLERANCE', '0.008'))
    LSR_STRUCTURE_LOOKBACK = int(os.getenv('LSR_STRUCTURE_LOOKBACK', '60'))

    # LSR Liquidity Sweep Detection
    LSR_SWEEP_VOLUME_MULT = float(os.getenv('LSR_SWEEP_VOLUME_MULT', '2.5'))
    LSR_SWEEP_MIN_WICK = float(os.getenv('LSR_SWEEP_MIN_WICK', '0.50'))

    # LSR RSI Divergence
    LSR_RSI_LOOKBACK = int(os.getenv('LSR_RSI_LOOKBACK', '10'))

    # LSR Confirmation Candle
    LSR_CONFIRM_VOLUME_MULT = float(os.getenv('LSR_CONFIRM_VOLUME_MULT', '1.2'))
    LSR_CONFIRM_MAX_SPREAD = float(os.getenv('LSR_CONFIRM_MAX_SPREAD', '0.002'))
    LSR_CONFIRM_TIMEOUT = int(os.getenv('LSR_CONFIRM_TIMEOUT', '3'))

    # LSR Stop Loss
    LSR_MAX_SL_PCT = float(os.getenv('LSR_MAX_SL_PCT', '0.006'))
    LSR_SL_VOLATILITY_MULT = float(os.getenv('LSR_SL_VOLATILITY_MULT', '1.25'))
    LSR_HIGH_VOL_ATR_THRESHOLD = float(os.getenv('LSR_HIGH_VOL_ATR_THRESHOLD', '1.5'))

    # LSR Take Profit
    LSR_TP1_RR = float(os.getenv('LSR_TP1_RR', '2.5'))
    LSR_TP2_RR = float(os.getenv('LSR_TP2_RR', '4.0'))
    LSR_TP1_CLOSE_PCT = float(os.getenv('LSR_TP1_CLOSE_PCT', '0.50'))

    # LSR Trailing Stop
    LSR_TRAILING_ACTIVATION_RR = float(os.getenv('LSR_TRAILING_ACTIVATION_RR', '2.5'))
    LSR_TRAILING_DISTANCE_RR = float(os.getenv('LSR_TRAILING_DISTANCE_RR', '0.8'))

    # LSR Invalidation Exit
    LSR_INVALIDATION_CANDLES = int(os.getenv('LSR_INVALIDATION_CANDLES', '2'))
    LSR_VOLUME_FADE_MULT = float(os.getenv('LSR_VOLUME_FADE_MULT', '0.5'))
    LSR_EXIT_ON_RSI_EXTREME = os.getenv('LSR_EXIT_ON_RSI_EXTREME', 'true').lower() == 'true'
    LSR_RSI_LONG_EXIT = int(os.getenv('LSR_RSI_LONG_EXIT', '70'))
    LSR_RSI_SHORT_EXIT = int(os.getenv('LSR_RSI_SHORT_EXIT', '30'))

    # Timeframes
    PRIMARY_TIMEFRAME = os.getenv('PRIMARY_TIMEFRAME', '1m')
    CONFIRMATION_TIMEFRAME = os.getenv('CONFIRMATION_TIMEFRAME', '5m')

    # Position Management (used by both strategies)
    TP1_CLOSE_PCT = float(os.getenv('TP1_CLOSE_PCT', '0.50'))
    ENABLE_TRAILING_STOP = os.getenv('ENABLE_TRAILING_STOP', 'true').lower() == 'true'
    TRAILING_STOP_ACTIVATION = float(os.getenv('TRAILING_STOP_ACTIVATION', '2.0'))
    TRAILING_STOP_DISTANCE = float(os.getenv('TRAILING_STOP_DISTANCE', '0.5'))

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
