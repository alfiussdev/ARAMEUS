"""
Performance metrics calculator for backtesting results
Calculates Sharpe ratio, max drawdown, win rate, profit factor, and more
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timedelta


class PerformanceMetrics:
    """Calculate comprehensive performance metrics for trading results"""

    def __init__(self, trades: List[Dict[str, Any]], initial_equity: float):
        """
        Initialize performance metrics calculator

        Args:
            trades: List of completed trades
            initial_equity: Starting equity
        """
        self.trades = trades
        self.initial_equity = initial_equity
        self.df_trades = pd.DataFrame(trades) if trades else pd.DataFrame()

    def calculate_all_metrics(self) -> Dict[str, Any]:
        """
        Calculate all performance metrics

        Returns:
            Dictionary with comprehensive metrics
        """
        if len(self.trades) == 0:
            return self._get_empty_metrics()

        return {
            'overview': self._calculate_overview(),
            'returns': self._calculate_returns(),
            'risk': self._calculate_risk_metrics(),
            'trade_analysis': self._calculate_trade_metrics(),
            'time_analysis': self._calculate_time_metrics(),
            'streaks': self._calculate_streaks(),
            'monthly_performance': self._calculate_monthly_performance()
        }

    def _calculate_overview(self) -> Dict[str, Any]:
        """Calculate overview metrics"""
        final_equity = self.initial_equity + self.df_trades['pnl_net'].sum()
        total_return = (final_equity - self.initial_equity) / self.initial_equity * 100

        return {
            'initial_equity': self.initial_equity,
            'final_equity': final_equity,
            'total_pnl': self.df_trades['pnl_net'].sum(),
            'total_return_pct': total_return,
            'total_trades': len(self.trades),
            'total_fees': self.df_trades['fees'].sum(),
            'net_profit': self.df_trades['pnl_net'].sum()
        }

    def _calculate_returns(self) -> Dict[str, Any]:
        """Calculate return-based metrics"""
        returns = self.df_trades['pnl_net'].values
        equity_curve = self._build_equity_curve()

        # Daily returns
        daily_returns = []
        if len(equity_curve) > 1:
            daily_returns = np.diff(equity_curve) / equity_curve[:-1]

        # Sharpe Ratio (annualized, assuming 252 trading days)
        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0

        # Sortino Ratio (using downside deviation)
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 1 and np.std(downside_returns) > 0:
            sortino_ratio = np.mean(daily_returns) / np.std(downside_returns) * np.sqrt(252)
        else:
            sortino_ratio = 0

        # Calmar Ratio (return / max drawdown)
        max_dd = self._calculate_max_drawdown(equity_curve)
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        calmar_ratio = total_return / abs(max_dd) if max_dd != 0 else 0

        return {
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'total_return_pct': total_return * 100,
            'annualized_return_pct': self._annualize_return(total_return),
            'daily_return_mean': np.mean(daily_returns) * 100 if len(daily_returns) > 0 else 0,
            'daily_return_std': np.std(daily_returns) * 100 if len(daily_returns) > 0 else 0
        }

    def _calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate risk metrics"""
        equity_curve = self._build_equity_curve()

        max_dd = self._calculate_max_drawdown(equity_curve)
        max_dd_duration = self._calculate_max_dd_duration(equity_curve)

        # Value at Risk (95% confidence)
        returns = self.df_trades['pnl_net'].values
        var_95 = np.percentile(returns, 5) if len(returns) > 0 else 0

        # Conditional Value at Risk (CVaR / Expected Shortfall)
        returns_below_var = returns[returns <= var_95]
        cvar_95 = np.mean(returns_below_var) if len(returns_below_var) > 0 else 0

        return {
            'max_drawdown_pct': max_dd * 100,
            'max_drawdown_duration_days': max_dd_duration,
            'value_at_risk_95': var_95,
            'conditional_var_95': cvar_95,
            'volatility_pct': np.std(returns) if len(returns) > 0 else 0
        }

    def _calculate_trade_metrics(self) -> Dict[str, Any]:
        """Calculate trade-level metrics"""
        winners = self.df_trades[self.df_trades['pnl_net'] > 0]
        losers = self.df_trades[self.df_trades['pnl_net'] <= 0]

        win_rate = len(winners) / len(self.df_trades) * 100 if len(self.df_trades) > 0 else 0

        avg_win = winners['pnl_net'].mean() if len(winners) > 0 else 0
        avg_loss = abs(losers['pnl_net'].mean()) if len(losers) > 0 else 0

        # Profit Factor
        total_wins = winners['pnl_net'].sum() if len(winners) > 0 else 0
        total_losses = abs(losers['pnl_net'].sum()) if len(losers) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Average R-multiple
        r_multiples = self.df_trades['r_multiple'].values if 'r_multiple' in self.df_trades.columns else []
        avg_r_multiple = np.mean(r_multiples) if len(r_multiples) > 0 else 0

        # Expectancy
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)

        # Best and worst trades
        best_trade = self.df_trades['pnl_net'].max() if len(self.df_trades) > 0 else 0
        worst_trade = self.df_trades['pnl_net'].min() if len(self.df_trades) > 0 else 0

        return {
            'total_trades': len(self.df_trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_r_multiple': avg_r_multiple,
            'expectancy': expectancy,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'avg_trade_pnl': self.df_trades['pnl_net'].mean()
        }

    def _calculate_time_metrics(self) -> Dict[str, Any]:
        """Calculate time-based metrics"""
        if 'entry_time' not in self.df_trades.columns or 'exit_time' not in self.df_trades.columns:
            return {}

        # Trade duration
        durations = []
        for _, trade in self.df_trades.iterrows():
            if isinstance(trade['entry_time'], str):
                entry = pd.to_datetime(trade['entry_time'])
                exit_time = pd.to_datetime(trade['exit_time'])
            else:
                entry = trade['entry_time']
                exit_time = trade['exit_time']

            duration = (exit_time - entry).total_seconds() / 3600  # hours
            durations.append(duration)

        avg_duration = np.mean(durations) if durations else 0

        # Trading period
        all_times = pd.to_datetime(self.df_trades['entry_time'])
        trading_days = (all_times.max() - all_times.min()).days

        # Trades per day
        trades_per_day = len(self.df_trades) / max(trading_days, 1)

        return {
            'avg_trade_duration_hours': avg_duration,
            'min_trade_duration_hours': min(durations) if durations else 0,
            'max_trade_duration_hours': max(durations) if durations else 0,
            'total_trading_days': trading_days,
            'trades_per_day': trades_per_day
        }

    def _calculate_streaks(self) -> Dict[str, Any]:
        """Calculate winning and losing streaks"""
        if len(self.df_trades) == 0:
            return {}

        wins = (self.df_trades['pnl_net'] > 0).astype(int).values

        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0

        for is_win in wins:
            if is_win:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    current_streak = 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    current_streak = -1
                max_loss_streak = max(max_loss_streak, abs(current_streak))

        return {
            'max_winning_streak': max_win_streak,
            'max_losing_streak': max_loss_streak,
            'current_streak': current_streak
        }

    def _calculate_monthly_performance(self) -> List[Dict[str, Any]]:
        """Calculate performance by month"""
        if 'entry_time' not in self.df_trades.columns:
            return []

        df = self.df_trades.copy()
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['month'] = df['entry_time'].dt.to_period('M')

        monthly = df.groupby('month').agg({
            'pnl_net': ['sum', 'count'],
        }).reset_index()

        monthly.columns = ['month', 'pnl', 'trades']
        monthly['month'] = monthly['month'].astype(str)

        return monthly.to_dict('records')

    def _build_equity_curve(self) -> np.ndarray:
        """Build equity curve from trades"""
        equity = [self.initial_equity]

        for trade in self.trades:
            equity.append(equity[-1] + trade['pnl_net'])

        return np.array(equity)

    def _calculate_max_drawdown(self, equity_curve: np.ndarray) -> float:
        """
        Calculate maximum drawdown

        Args:
            equity_curve: Array of equity values

        Returns:
            Maximum drawdown as percentage (negative value)
        """
        if len(equity_curve) == 0:
            return 0

        peak = equity_curve[0]
        max_dd = 0

        for value in equity_curve:
            if value > peak:
                peak = value

            dd = (value - peak) / peak
            if dd < max_dd:
                max_dd = dd

        return max_dd

    def _calculate_max_dd_duration(self, equity_curve: np.ndarray) -> int:
        """
        Calculate maximum drawdown duration in days

        Args:
            equity_curve: Array of equity values

        Returns:
            Maximum drawdown duration in days
        """
        if len(equity_curve) == 0:
            return 0

        peak = equity_curve[0]
        peak_idx = 0
        max_duration = 0
        current_duration = 0

        for i, value in enumerate(equity_curve):
            if value > peak:
                peak = value
                peak_idx = i
                current_duration = 0
            else:
                current_duration = i - peak_idx
                if current_duration > max_duration:
                    max_duration = current_duration

        return max_duration

    def _annualize_return(self, total_return: float) -> float:
        """
        Annualize total return

        Args:
            total_return: Total return as decimal

        Returns:
            Annualized return percentage
        """
        if 'entry_time' not in self.df_trades.columns:
            return 0

        all_times = pd.to_datetime(self.df_trades['entry_time'])
        trading_days = (all_times.max() - all_times.min()).days

        if trading_days == 0:
            return 0

        years = trading_days / 365.25
        annualized = (1 + total_return) ** (1 / years) - 1

        return annualized * 100

    def _get_empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            'overview': {
                'initial_equity': self.initial_equity,
                'final_equity': self.initial_equity,
                'total_pnl': 0,
                'total_return_pct': 0,
                'total_trades': 0
            },
            'returns': {},
            'risk': {},
            'trade_analysis': {},
            'time_analysis': {},
            'streaks': {},
            'monthly_performance': []
        }

    def get_equity_curve(self) -> pd.DataFrame:
        """
        Get equity curve as DataFrame

        Returns:
            DataFrame with timestamp and equity columns
        """
        if len(self.trades) == 0:
            return pd.DataFrame({'timestamp': [], 'equity': []})

        equity = [self.initial_equity]
        timestamps = [pd.to_datetime(self.trades[0]['entry_time'])]

        for trade in self.trades:
            equity.append(equity[-1] + trade['pnl_net'])
            timestamps.append(pd.to_datetime(trade['exit_time']))

        return pd.DataFrame({
            'timestamp': timestamps,
            'equity': equity
        })

    def print_summary(self, metrics: Dict[str, Any]):
        """
        Print formatted summary of metrics

        Args:
            metrics: Metrics dictionary from calculate_all_metrics()
        """
        print("\n" + "=" * 70)
        print("  BACKTEST PERFORMANCE SUMMARY")
        print("=" * 70)

        # Overview
        overview = metrics['overview']
        print(f"\n📊 OVERVIEW")
        print(f"  Initial Equity:    ${overview['initial_equity']:,.2f}")
        print(f"  Final Equity:      ${overview['final_equity']:,.2f}")
        print(f"  Total P&L:         ${overview['total_pnl']:,.2f}")
        print(f"  Total Return:      {overview['total_return_pct']:.2f}%")
        print(f"  Total Trades:      {overview['total_trades']}")
        print(f"  Total Fees:        ${overview['total_fees']:,.2f}")

        # Returns
        if 'returns' in metrics and metrics['returns']:
            returns = metrics['returns']
            print(f"\n📈 RETURNS")
            print(f"  Sharpe Ratio:      {returns.get('sharpe_ratio', 0):.2f}")
            print(f"  Sortino Ratio:     {returns.get('sortino_ratio', 0):.2f}")
            print(f"  Calmar Ratio:      {returns.get('calmar_ratio', 0):.2f}")
            print(f"  Annualized Return: {returns.get('annualized_return_pct', 0):.2f}%")

        # Risk
        if 'risk' in metrics and metrics['risk']:
            risk = metrics['risk']
            print(f"\n⚠️  RISK METRICS")
            print(f"  Max Drawdown:      {risk.get('max_drawdown_pct', 0):.2f}%")
            print(f"  Max DD Duration:   {risk.get('max_drawdown_duration_days', 0)} days")
            print(f"  VaR (95%):         ${risk.get('value_at_risk_95', 0):.2f}")

        # Trade Analysis
        if 'trade_analysis' in metrics and metrics['trade_analysis']:
            trade = metrics['trade_analysis']
            print(f"\n🎯 TRADE ANALYSIS")
            print(f"  Win Rate:          {trade.get('win_rate_pct', 0):.2f}%")
            print(f"  Winning Trades:    {trade.get('winning_trades', 0)}")
            print(f"  Losing Trades:     {trade.get('losing_trades', 0)}")
            print(f"  Profit Factor:     {trade.get('profit_factor', 0):.2f}")
            print(f"  Avg Win:           ${trade.get('avg_win', 0):.2f}")
            print(f"  Avg Loss:          ${trade.get('avg_loss', 0):.2f}")
            print(f"  Avg R-Multiple:    {trade.get('avg_r_multiple', 0):.2f}R")
            print(f"  Expectancy:        ${trade.get('expectancy', 0):.2f}")
            print(f"  Best Trade:        ${trade.get('best_trade', 0):.2f}")
            print(f"  Worst Trade:       ${trade.get('worst_trade', 0):.2f}")

        # Time Analysis
        if 'time_analysis' in metrics and metrics['time_analysis']:
            time_metrics = metrics['time_analysis']
            print(f"\n⏱️  TIME ANALYSIS")
            print(f"  Avg Trade Duration: {time_metrics.get('avg_trade_duration_hours', 0):.1f} hours")
            print(f"  Total Trading Days: {time_metrics.get('total_trading_days', 0)}")
            print(f"  Trades per Day:     {time_metrics.get('trades_per_day', 0):.2f}")

        # Streaks
        if 'streaks' in metrics and metrics['streaks']:
            streaks = metrics['streaks']
            print(f"\n🔥 STREAKS")
            print(f"  Max Win Streak:    {streaks.get('max_winning_streak', 0)}")
            print(f"  Max Loss Streak:   {streaks.get('max_losing_streak', 0)}")

        print("\n" + "=" * 70)
