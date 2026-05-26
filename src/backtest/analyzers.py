"""
Custom Analyzers for Backtrader

Provides detailed trade analysis and custom metrics.
"""

import backtrader as bt
from datetime import datetime
from typing import Dict, List, Any


class DetailedAnalyzer(bt.Analyzer):
    """
    Detailed trade analyzer that captures:
    - Individual trade details
    - Equity curve
    - Buy & Hold comparison
    - Drawdown curve
    - Daily returns
    """
    
    def __init__(self):
        self.trades = []
        self.equity_curve = []
        self.buy_hold_curve = []
        self.drawdown_curve = []
        self.trade_count = 0
        self._open_trades = {}  # Track open trade info by trade ref
        self.peak_value = 0
        self.initial_price = None
    
    def start(self):
        """Called at start of backtest."""
        self.start_value = self.strategy.broker.getvalue()
        self.peak_value = self.start_value
    
    def notify_trade(self, trade):
        """Capture trade details."""
        if trade.isopen:
            # Store info when trade opens
            self._open_trades[trade.ref] = {
                'size': trade.size,
                'entry_price': trade.price,
                'direction': 'LONG' if trade.size > 0 else 'SHORT',
            }
        
        if trade.isclosed:
            self.trade_count += 1
            
            # Get info from when trade opened
            open_info = self._open_trades.pop(trade.ref, {})
            direction = open_info.get('direction', 'LONG' if trade.pnl > 0 else 'SHORT')
            entry_price = open_info.get('entry_price', trade.price)
            trade_size = abs(open_info.get('size', trade.size)) or 1
            
            # Calculate exit price from PnL
            # For LONG: exit_price = entry_price + pnl/size
            # For SHORT: exit_price = entry_price - pnl/size
            pnl_per_share = trade.pnl / trade_size if trade_size else 0
            if direction == 'LONG':
                exit_price = entry_price + pnl_per_share
            else:
                exit_price = entry_price - pnl_per_share
            
            # Calculate PnL percentage
            pnl_pct = (trade.pnl / (entry_price * trade_size)) * 100 if entry_price and trade_size else 0
            
            self.trades.append({
                'trade_num': self.trade_count,
                'direction': direction,
                'entry_time': bt.num2date(trade.dtopen).isoformat(),
                'entry_price': round(entry_price, 2),
                'exit_time': bt.num2date(trade.dtclose).isoformat(),
                'exit_price': round(exit_price, 2),
                'size': trade_size,
                'pnl': round(trade.pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'commission': round(trade.commission, 2),
                'bars_held': trade.barlen,
            })
    
    def next(self):
        """Capture equity at each bar."""
        current_value = self.strategy.broker.getvalue()
        current_price = self.strategy.data.close[0]
        dt = self.strategy.datetime.datetime().isoformat()
        
        # Store initial price for Buy & Hold calculation
        if self.initial_price is None:
            self.initial_price = current_price
        
        # Calculate Buy & Hold value (as if we bought at start)
        buy_hold_value = self.start_value * (current_price / self.initial_price)
        
        # Calculate drawdown
        if current_value > self.peak_value:
            self.peak_value = current_value
        
        drawdown = 0
        if self.peak_value > 0:
            drawdown = ((self.peak_value - current_value) / self.peak_value) * 100
        
        # Store curves
        self.equity_curve.append({
            'datetime': dt,
            'value': round(current_value, 2),
        })
        
        self.buy_hold_curve.append({
            'datetime': dt,
            'value': round(buy_hold_value, 2),
        })
        
        self.drawdown_curve.append({
            'datetime': dt,
            'drawdown': round(drawdown, 2),
        })
    
    def get_analysis(self):
        """Return analysis results."""
        # Calculate Buy & Hold final return
        buy_hold_return = 0
        if self.buy_hold_curve:
            buy_hold_final = self.buy_hold_curve[-1]['value']
            buy_hold_return = round((buy_hold_final / self.start_value - 1) * 100, 2)
        
        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'buy_hold_curve': self.buy_hold_curve,
            'drawdown_curve': self.drawdown_curve,
            'total_trades': self.trade_count,
            'buy_hold_return': buy_hold_return,
        }


