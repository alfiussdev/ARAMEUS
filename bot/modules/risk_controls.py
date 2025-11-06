"""
Risk controls module for global risk management
Implements loss streak cooldown, daily drawdown limits, and global drawdown limits
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
from pathlib import Path


class RiskControls:
    """Global risk control system"""

    def __init__(self, config, logger):
        """
        Initialize risk controls

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

        # Risk state tracking
        self.loss_streak = 0
        self.cooldown_until: Optional[datetime] = None
        self.daily_pnl = 0.0
        self.daily_start_equity = 0.0
        self.equity_peak = 0.0
        self.current_equity = 0.0
        self.last_reset_date = datetime.now().date()

        # Trade history
        self.trade_history = []

        # State file path
        self.state_file = Path('data/risk_state.json')
        self.state_file.parent.mkdir(exist_ok=True)

        # Load previous state if exists
        self._load_state()

    def can_trade(self, current_equity: float) -> Tuple[bool, str]:
        """
        Check if trading is allowed based on risk controls

        Args:
            current_equity: Current account equity

        Returns:
            Tuple of (is_allowed, reason)
        """
        self.current_equity = current_equity

        # Update daily tracking if new day
        self._check_daily_reset()

        # 1. Check loss streak cooldown
        if self.cooldown_until is not None:
            if datetime.now() < self.cooldown_until:
                remaining = (self.cooldown_until - datetime.now()).total_seconds() / 3600
                return False, f"In cooldown period. {remaining:.1f} hours remaining after {self.loss_streak} consecutive losses"

            # Cooldown expired, reset
            self.cooldown_until = None
            self.logger.log_risk_event(
                event_type='COOLDOWN_EXPIRED',
                severity='INFO',
                message='Cooldown period expired, trading resumed'
            )

        # 2. Check daily drawdown limit
        daily_dd_pct = (self.daily_pnl / self.daily_start_equity) if self.daily_start_equity > 0 else 0

        if daily_dd_pct <= -self.config.DAILY_DRAWDOWN_LIMIT:
            return False, f"Daily drawdown limit reached ({daily_dd_pct:.2%}). Trading suspended until next day."

        # 3. Check global drawdown limit
        if self.equity_peak > 0:
            global_dd_pct = (current_equity - self.equity_peak) / self.equity_peak

            if global_dd_pct <= -self.config.GLOBAL_DRAWDOWN_LIMIT:
                self.logger.log_risk_event(
                    event_type='GLOBAL_DRAWDOWN_LIMIT',
                    severity='CRITICAL',
                    message=f'Global drawdown limit reached ({global_dd_pct:.2%}). Bot shutdown required.',
                    equity_peak=self.equity_peak,
                    current_equity=current_equity,
                    drawdown_pct=global_dd_pct
                )
                return False, f"CRITICAL: Global drawdown limit reached ({global_dd_pct:.2%}). Manual review required."

        # All checks passed
        return True, "Trading allowed"

    def record_trade(self, pair: str, pnl: float, is_winner: bool, exit_reason: str):
        """
        Record a completed trade and update risk state

        Args:
            pair: Trading pair
            pnl: Trade P&L in USDC
            is_winner: Whether trade was profitable
            exit_reason: Reason for trade exit
        """
        # Update daily P&L
        self.daily_pnl += pnl

        # Update loss streak
        if is_winner:
            # Reset loss streak on win
            if self.loss_streak > 0:
                self.logger.log_risk_event(
                    event_type='LOSS_STREAK_BROKEN',
                    severity='INFO',
                    message=f'Loss streak of {self.loss_streak} broken by winning trade',
                    previous_streak=self.loss_streak,
                    pnl=pnl
                )
            self.loss_streak = 0
        else:
            # Increment loss streak
            self.loss_streak += 1

            self.logger.log_risk_event(
                event_type='LOSS_RECORDED',
                severity='WARNING' if self.loss_streak >= 2 else 'INFO',
                message=f'Loss recorded. Current loss streak: {self.loss_streak}',
                loss_streak=self.loss_streak,
                pnl=pnl
            )

            # Check if cooldown should be triggered
            if self.loss_streak >= self.config.LOSS_STREAK_LIMIT:
                self.cooldown_until = datetime.now() + timedelta(hours=self.config.COOLDOWN_HOURS)

                self.logger.log_risk_event(
                    event_type='COOLDOWN_TRIGGERED',
                    severity='WARNING',
                    message=f'Cooldown triggered after {self.loss_streak} consecutive losses',
                    loss_streak=self.loss_streak,
                    cooldown_until=self.cooldown_until.isoformat(),
                    cooldown_hours=self.config.COOLDOWN_HOURS
                )

        # Update equity peak
        if self.current_equity > self.equity_peak:
            old_peak = self.equity_peak
            self.equity_peak = self.current_equity

            self.logger.log_risk_event(
                event_type='NEW_EQUITY_PEAK',
                severity='INFO',
                message=f'New equity peak reached: ${self.equity_peak:.2f}',
                old_peak=old_peak,
                new_peak=self.equity_peak
            )

        # Add to trade history
        self.trade_history.append({
            'timestamp': datetime.now().isoformat(),
            'pair': pair,
            'pnl': pnl,
            'is_winner': is_winner,
            'exit_reason': exit_reason,
            'equity': self.current_equity,
            'loss_streak': self.loss_streak
        })

        # Save state
        self._save_state()

    def _check_daily_reset(self):
        """Check if we need to reset daily tracking"""
        today = datetime.now().date()

        if today > self.last_reset_date:
            # New day, reset daily tracking
            self.logger.log_risk_event(
                event_type='DAILY_RESET',
                severity='INFO',
                message=f'Daily tracking reset. Previous day P&L: ${self.daily_pnl:.2f}',
                previous_date=self.last_reset_date.isoformat(),
                daily_pnl=self.daily_pnl,
                daily_pnl_pct=(self.daily_pnl / self.daily_start_equity * 100) if self.daily_start_equity > 0 else 0
            )

            self.daily_start_equity = self.current_equity
            self.daily_pnl = 0.0
            self.last_reset_date = today

            # Save state after reset
            self._save_state()

    def initialize_equity(self, starting_equity: float):
        """
        Initialize equity tracking

        Args:
            starting_equity: Starting equity amount
        """
        if self.equity_peak == 0:
            self.equity_peak = starting_equity
            self.current_equity = starting_equity
            self.daily_start_equity = starting_equity

            self.logger.log_risk_event(
                event_type='EQUITY_INITIALIZED',
                severity='INFO',
                message=f'Equity tracking initialized at ${starting_equity:.2f}',
                equity=starting_equity
            )

            self._save_state()

    def get_risk_status(self) -> Dict[str, Any]:
        """
        Get current risk control status

        Returns:
            Dictionary with risk status information
        """
        # Calculate current drawdowns
        daily_dd_pct = (self.daily_pnl / self.daily_start_equity * 100) if self.daily_start_equity > 0 else 0
        global_dd_pct = ((self.current_equity - self.equity_peak) / self.equity_peak * 100) if self.equity_peak > 0 else 0

        # Check if in cooldown
        in_cooldown = self.cooldown_until is not None and datetime.now() < self.cooldown_until
        cooldown_remaining = 0
        if in_cooldown:
            cooldown_remaining = (self.cooldown_until - datetime.now()).total_seconds() / 3600

        # Can trade check
        can_trade, reason = self.can_trade(self.current_equity)

        return {
            'can_trade': can_trade,
            'reason': reason,
            'loss_streak': self.loss_streak,
            'in_cooldown': in_cooldown,
            'cooldown_remaining_hours': cooldown_remaining,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': daily_dd_pct,
            'daily_drawdown_limit_pct': self.config.DAILY_DRAWDOWN_LIMIT * 100,
            'equity_peak': self.equity_peak,
            'current_equity': self.current_equity,
            'global_drawdown_pct': global_dd_pct,
            'global_drawdown_limit_pct': self.config.GLOBAL_DRAWDOWN_LIMIT * 100,
            'trades_today': len([t for t in self.trade_history if datetime.fromisoformat(t['timestamp']).date() == self.last_reset_date]),
            'total_trades': len(self.trade_history)
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get trading statistics

        Returns:
            Dictionary with trading statistics
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'average_win': 0,
                'average_loss': 0,
                'profit_factor': 0
            }

        winners = [t for t in self.trade_history if t['is_winner']]
        losers = [t for t in self.trade_history if not t['is_winner']]

        total_trades = len(self.trade_history)
        winning_trades = len(winners)
        losing_trades = len(losers)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(t['pnl'] for t in self.trade_history)
        total_wins = sum(t['pnl'] for t in winners)
        total_losses = abs(sum(t['pnl'] for t in losers))

        average_win = (total_wins / winning_trades) if winning_trades > 0 else 0
        average_loss = (total_losses / losing_trades) if losing_trades > 0 else 0

        profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf')

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'average_win': average_win,
            'average_loss': average_loss,
            'profit_factor': profit_factor,
            'current_streak': self.loss_streak if self.loss_streak > 0 else 0,
            'max_streak': max([t['loss_streak'] for t in self.trade_history], default=0)
        }

    def _save_state(self):
        """Save risk control state to file"""
        try:
            state = {
                'loss_streak': self.loss_streak,
                'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
                'daily_pnl': self.daily_pnl,
                'daily_start_equity': self.daily_start_equity,
                'equity_peak': self.equity_peak,
                'current_equity': self.current_equity,
                'last_reset_date': self.last_reset_date.isoformat(),
                'trade_history': self.trade_history[-100:]  # Keep last 100 trades
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            self.logger.log_error(e, context="save_risk_state")

    def _load_state(self):
        """Load risk control state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                self.loss_streak = state.get('loss_streak', 0)

                cooldown_str = state.get('cooldown_until')
                self.cooldown_until = datetime.fromisoformat(cooldown_str) if cooldown_str else None

                self.daily_pnl = state.get('daily_pnl', 0.0)
                self.daily_start_equity = state.get('daily_start_equity', 0.0)
                self.equity_peak = state.get('equity_peak', 0.0)
                self.current_equity = state.get('current_equity', 0.0)

                date_str = state.get('last_reset_date')
                self.last_reset_date = datetime.fromisoformat(date_str).date() if date_str else datetime.now().date()

                self.trade_history = state.get('trade_history', [])

                self.logger.log_system_event(
                    "Risk state loaded",
                    loss_streak=self.loss_streak,
                    equity_peak=self.equity_peak,
                    daily_pnl=self.daily_pnl
                )

        except Exception as e:
            self.logger.log_error(e, context="load_risk_state")

    def reset_state(self):
        """Reset risk control state (use with caution)"""
        self.loss_streak = 0
        self.cooldown_until = None
        self.daily_pnl = 0.0
        self.trade_history = []

        self.logger.log_risk_event(
            event_type='STATE_RESET',
            severity='WARNING',
            message='Risk control state manually reset'
        )

        self._save_state()
