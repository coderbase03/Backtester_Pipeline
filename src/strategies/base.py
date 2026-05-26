"""
Base Strategy Class

Provides common functionality for all strategies including:
- Risk management
- Position sizing
- Order management (bracket orders, trailing stops)
- Trade direction control
- Logging
"""

import backtrader as bt
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(bt.Strategy):
    """
    Base strategy class with common functionality.
    
    All strategies should inherit from this class.
    
    Params:
        risk_pct (float): Risk per trade as % of portfolio (default: 2%)
        use_bracket (bool): Use bracket orders (TP/SL) 
        tp_pct (float): Take profit percentage (default: 3.0%)
        sl_pct (float): Stop loss percentage (default: 1.5%)
        trail_pct (float): Trailing stop percentage (0 = disabled)
        trade_direction (str): 'long', 'short', or 'both' (default: 'both')
        leverage (int): Leverage multiplier (default: 1)
        log_trades (bool): Log trade entries/exits
    """
    
    # ============================================================
    # STRATEGY METADATA - Override in subclass for TV chart indicators
    # ============================================================
    # Format: {'indicator_name': 'param_name'} or {'indicator_name': ['param1', 'param2']}
    # Example: {'sma_fast': 'fast_period', 'sma_slow': 'slow_period'}
    STRATEGY_INDICATORS: Dict[str, any] = {}
    
    params = (
        ('risk_pct', 1.0),        # Deprecated in sizing (kept for backward compatibility)
        ('use_bracket', True),    # Use bracket orders
        ('tp_pct', 3.0),          # Take profit 3%
        ('sl_pct', 1.5),          # Stop loss 1.5%
        ('trail_pct', 0.0),       # Trailing stop % (0 = disabled)
        ('trade_direction', 'both'),  # 'long', 'short', or 'both'
        ('leverage', 1),          # Leverage multiplier (1 = no leverage)
        ('cash_buffer_pct', 0.995),  # Maximum usable cash ratio for position sizing
        ('position_mode', 'full_cash'),  # fixed_units | fixed_notional | full_cash
        ('fixed_units', 1.0),     # Used when position_mode=fixed_units
        ('fixed_notional', 1000.0),  # Used when position_mode=fixed_notional
        ('log_trades', True),     # Log trades
    )
    
    def __init__(self):
        """Initialize base strategy."""
        self.order = None
        self.buy_price = None
        self.buy_size = None
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        
        # Store data reference
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # ATR for stop loss calculation
        self.atr = bt.indicators.ATR(self.datas[0], period=14)
    
    # ============================================================
    # TRADE DIRECTION HELPERS
    # ============================================================
    
    def should_trade_long(self) -> bool:
        """Check if long trades are allowed based on trade_direction param."""
        return self.p.trade_direction in ['long', 'both']
    
    def should_trade_short(self) -> bool:
        """Check if short trades are allowed based on trade_direction param."""
        return self.p.trade_direction in ['short', 'both']
    
    @classmethod
    def get_indicator_config(cls) -> Dict[str, any]:
        """
        Get indicator configuration for TV chart display.
        
        Returns dict mapping indicator names to their parameter names.
        Override STRATEGY_INDICATORS in subclass to define.
        
        Example:
            STRATEGY_INDICATORS = {
                'sma_fast': 'fast_period',
                'sma_slow': 'slow_period'
            }
        """
        return cls.STRATEGY_INDICATORS
    
    def log(self, txt, dt=None, level='INFO'):
        """Log message with timestamp."""
        dt = dt or self.datas[0].datetime.datetime(0)
        if self.p.log_trades:
            logger.log(getattr(logging, level), '%s - %s', dt.isoformat(), txt)
    
    def notify_order(self, order):
        """Handle order notifications."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED @ {order.executed.price:.2f}, '
                        f'Size: {order.executed.size:.4f}, '
                        f'Cost: {order.executed.value:.2f}')
                self.buy_price = order.executed.price
                self.buy_size = order.executed.size
            else:
                self.log(f'SELL EXECUTED @ {order.executed.price:.2f}, '
                        f'Size: {order.executed.size:.4f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.status}', level='WARNING')
        
        self.order = None
    
    def notify_trade(self, trade):
        """Handle trade notifications."""
        if not trade.isclosed:
            return
        
        self.trade_count += 1
        
        if trade.pnl > 0:
            self.wins += 1
            self.log(f'TRADE WIN - PnL: {trade.pnl:.2f} ({trade.pnlcomm:.2f} after comm)')
        else:
            self.losses += 1
            self.log(f'TRADE LOSS - PnL: {trade.pnl:.2f} ({trade.pnlcomm:.2f} after comm)')
    
    def calculate_position_size(self, stop_price: float = 0.0) -> float:
        """
        Calculate position size based on risk percentage.
        
        Supports fractional shares for crypto/high-priced assets.
        
        Args:
            stop_price: Stop loss price
            
        Returns:
            Position size (can be fractional for crypto)
        """
        current_price = self.dataclose[0]
        if current_price <= 0:
            return 0

        # Position sizing mode
        leverage = max(1, int(getattr(self.p, 'leverage', 1)))
        buffer_pct = getattr(self.p, 'cash_buffer_pct', 0.995)
        buffer_pct = max(0.05, min(1.0, float(buffer_pct)))
        mode = str(getattr(self.p, 'position_mode', 'fixed_units')).lower()

        if mode == 'fixed_units':
            size = float(getattr(self.p, 'fixed_units', 1.0))
        elif mode == 'fixed_notional':
            fixed_notional = max(0.0, float(getattr(self.p, 'fixed_notional', 1000.0)))
            size = (fixed_notional * leverage) / current_price if current_price > 0 else 0
        else:  # full_cash
            max_notional = self.broker.getcash() * buffer_pct * leverage
            size = max_notional / current_price
        
        # Handle NaN values
        import math
        if math.isnan(size) or math.isinf(size):
            return 0
        
        # For high-priced assets (crypto), keep fractional shares
        # For stocks < $1000, round to whole shares
        if current_price >= 1000:
            # Crypto/high-priced: keep 3 decimal places
            size = round(size, 3)
        else:
            # Stocks: round to whole shares
            size = int(size)
        
        # Ensure we have enough cash while keeping a tiny reserve.
        max_affordable = (self.broker.getcash() * buffer_pct * leverage) / current_price
        
        # Handle NaN for max_affordable
        if math.isnan(max_affordable) or math.isinf(max_affordable):
            max_affordable = 0
        
        if current_price >= 1000:
            max_affordable = round(max_affordable, 3)
        else:
            max_affordable = int(max_affordable)
        
        size = min(size, max_affordable)

        # Minimum size check
        min_size = 0.001 if current_price >= 1000 else 1
        if current_price < 1000 and size < 1 and max_affordable >= 1:
            # If risk-based size is too small but account can afford 1 share,
            # allow a minimum executable lot to avoid false "0 trade" runs.
            size = 1
        if size < min_size:
            return 0
        
        return size
    
    def buy_with_bracket(
        self,
        size: Optional[float] = None,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
    ):
        """
        Enter long position with bracket order (TP/SL).
        
        TP/SL is calculated based on percentage parameters (tp_pct, sl_pct).
        If sl_price or tp_price is provided explicitly, it overrides the percentage.
        
        Args:
            size: Position size (None = auto-calculate)
            sl_price: Stop loss price (None = percentage-based from sl_pct)
            tp_price: Take profit price (None = percentage-based from tp_pct)
        """
        if self.position:
            return None
        
        current_price = self.dataclose[0]
        
        # Calculate stop loss based on percentage
        if sl_price is None:
            sl_price = current_price * (1 - self.p.sl_pct / 100)
        
        # Calculate take profit based on percentage
        if tp_price is None:
            tp_price = current_price * (1 + self.p.tp_pct / 100)
        
        # Calculate position size if not provided
        if size is None:
            size = self.calculate_position_size(sl_price)
        
        if size <= 0:
            self.log("Cannot open position: size <= 0", level='WARNING')
            return None
        
        self.log(f'OPENING LONG - Size: {size}, Entry: {current_price:.2f}, '
                f'SL: {sl_price:.2f} ({self.p.sl_pct}%), TP: {tp_price:.2f} ({self.p.tp_pct}%)')
        
        # Create bracket order
        if self.p.use_bracket:
            if self.p.trail_pct > 0:
                # Bracket with trailing stop
                self.order = self.buy_bracket(
                    size=size,
                    stopprice=sl_price,
                    stopexec=bt.Order.StopTrail,
                    trailpercent=self.p.trail_pct,
                    limitprice=tp_price
                )
            else:
                # Standard bracket
                self.order = self.buy_bracket(
                    size=size,
                    stopprice=sl_price,
                    limitprice=tp_price
                )
        else:
            self.order = self.buy(size=size)
        
        return self.order
    
    def sell_with_bracket(
        self,
        size: Optional[float] = None,
        sl_price: Optional[float] = None,
        tp_price: Optional[float] = None,
    ):
        """
        Enter short position with bracket order (TP/SL).
        
        TP/SL is calculated based on percentage parameters (tp_pct, sl_pct).
        If sl_price or tp_price is provided explicitly, it overrides the percentage.
        
        Args:
            size: Position size (None = auto-calculate)
            sl_price: Stop loss price (None = percentage-based from sl_pct)
            tp_price: Take profit price (None = percentage-based from tp_pct)
        """
        if self.position:
            return None
        
        current_price = self.dataclose[0]
        
        # Calculate stop loss (above price for shorts) based on percentage
        if sl_price is None:
            sl_price = current_price * (1 + self.p.sl_pct / 100)
        
        # Calculate take profit (below price for shorts) based on percentage
        if tp_price is None:
            tp_price = current_price * (1 - self.p.tp_pct / 100)
        
        # Calculate position size if not provided
        if size is None:
            size = self.calculate_position_size(sl_price)
        
        if size <= 0:
            self.log("Cannot open position: size <= 0", level='WARNING')
            return None
        
        self.log(f'OPENING SHORT - Size: {size}, Entry: {current_price:.2f}, '
                f'SL: {sl_price:.2f} ({self.p.sl_pct}%), TP: {tp_price:.2f} ({self.p.tp_pct}%)')
        
        if self.p.use_bracket:
            self.order = self.sell_bracket(
                size=size,
                stopprice=sl_price,
                limitprice=tp_price
            )
        else:
            self.order = self.sell(size=size)
        
        return self.order
    
    def close_position(self):
        """Close current position."""
        if self.position:
            self.log(f'CLOSING POSITION - Size: {self.position.size}')
            self.close()
    
    def reverse_to_long(self, sl_price: float = None):
        """
        Swing trading: Short pozisyonu kapat ve Long pozisyon aç.
        Çift yönlü işlemler için ters sinyal geldiğinde kullanılır.
        
        Args:
            sl_price: Stop loss fiyatı (None = otomatik hesapla)
        """
        if self.position.size < 0:  # Short pozisyondaysak
            self.log('SWING: Closing Short -> Opening Long')
            self.close()  # Short'u kapat
            # Bir sonraki bar'da long açılacak (order pending)
            self._pending_long = True
            self._pending_sl = sl_price
        elif not self.position:
            self.buy_with_bracket(sl_price=sl_price)
    
    def reverse_to_short(self, sl_price: float = None):
        """
        Swing trading: Long pozisyonu kapat ve Short pozisyon aç.
        Çift yönlü işlemler için ters sinyal geldiğinde kullanılır.
        
        Args:
            sl_price: Stop loss fiyatı (None = otomatik hesapla)
        """
        if self.position.size > 0:  # Long pozisyondaysak
            self.log('SWING: Closing Long -> Opening Short')
            self.close()  # Long'u kapat
            # Bir sonraki bar'da short açılacak (order pending)
            self._pending_short = True
            self._pending_sl = sl_price
        elif not self.position:
            self.sell_with_bracket(sl_price=sl_price)
    
    def check_pending_reverse(self):
        """
        Pending swing işlemlerini kontrol et ve uygula.
        Stratejilerin next() metodunda çağrılmalı.
        """
        if not self.position:
            if getattr(self, '_pending_long', False):
                self._pending_long = False
                sl_price = getattr(self, '_pending_sl', None)
                self.buy_with_bracket(sl_price=sl_price)
            elif getattr(self, '_pending_short', False):
                self._pending_short = False
                sl_price = getattr(self, '_pending_sl', None)
                self.sell_with_bracket(sl_price=sl_price)
    
    def get_win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.trade_count == 0:
            return 0.0
        return (self.wins / self.trade_count) * 100
    
    def stop(self):
        """Called at end of backtest - log summary."""
        self.log(f'Strategy finished: {self.trade_count} trades, '
                f'Win Rate: {self.get_win_rate():.1f}%')
