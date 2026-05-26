"""
RSI Mean Reversion Strategy

Mean reversion strategy using RSI:
- Long when RSI oversold and starts recovering
- Short when RSI overbought and starts declining

Works best in ranging markets.
"""

import backtrader as bt
from .base import BaseStrategy


class RSIMeanReversion(BaseStrategy):
    """
    RSI Mean Reversion Strategy
    
    Params (inherited from BaseStrategy):
        trade_direction: 'long', 'short', or 'both'
        use_bracket, tp_pct, sl_pct, leverage, etc.
        
    Params (strategy-specific):
        rsi_period: RSI calculation period
        oversold: Oversold threshold (default: 30)
        overbought: Overbought threshold (default: 70)
    """
    
    # TV Chart indicator configuration
    STRATEGY_INDICATORS = {
        'rsi': 'rsi_period'
    }
    
    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
        # trade_direction is inherited from BaseStrategy
    )
    
    def __init__(self):
        super().__init__()
        
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        
        self.log(f'RSI Mean Reversion initialized: period={self.p.rsi_period}, '
                 f'oversold={self.p.oversold}, overbought={self.p.overbought}')
    
    def next(self):
        if self.order:
            return
        
        rsi = self.rsi[0]
        rsi_prev = self.rsi[-1] if len(self.rsi) > 1 else rsi
        price = self.data.close[0]
        atr = self.atr[0] if self.atr[0] == self.atr[0] else price * 0.02
        
        if not self.position:
            # LONG: RSI was oversold and is now rising
            if rsi_prev < self.p.oversold and rsi > rsi_prev:
                if self.should_trade_long():
                    sl_price = price - 2 * atr
                    self.log(f'LONG SIGNAL - RSI oversold: {rsi:.1f}, SL: {sl_price:.2f}')
                    self.buy_with_bracket(sl_price=sl_price)
            
            # SHORT: RSI was overbought and is now falling
            elif rsi_prev > self.p.overbought and rsi < rsi_prev:
                if self.should_trade_short():
                    sl_price = price + 2 * atr
                    self.log(f'SHORT SIGNAL - RSI overbought: {rsi:.1f}, SL: {sl_price:.2f}')
                    self.sell_with_bracket(sl_price=sl_price)
        
        else:
            # Exit conditions if not using bracket
            if not self.p.use_bracket:
                # Exit long when RSI overbought
                if self.position.size > 0 and rsi > self.p.overbought:
                    self.log(f'EXIT LONG - RSI overbought: {rsi:.1f}')
                    self.close_position()
                
                # Exit short when RSI oversold
                elif self.position.size < 0 and rsi < self.p.oversold:
                    self.log(f'EXIT SHORT - RSI oversold: {rsi:.1f}')
                    self.close_position()
