"""
SMA Crossover Strategy

Classic moving average crossover strategy:
- Long when fast SMA crosses above slow SMA
- Exit when fast SMA crosses below slow SMA

Good for trending markets, simple and proven.
"""

import backtrader as bt
from .base import BaseStrategy


class SMACrossover(BaseStrategy):
    """
    SMA Crossover Strategy
    
    Params (inherited from BaseStrategy):
        trade_direction: 'long', 'short', or 'both'
        use_bracket, tp_pct, sl_pct, leverage, etc.
        
    Params (strategy-specific):
        fast_period: Fast SMA period (default: 10)
        slow_period: Slow SMA period (default: 30)
    """
    
    # TV Chart indicator configuration
    STRATEGY_INDICATORS = {
        'sma_fast': 'fast_period',
        'sma_slow': 'slow_period'
    }
    
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        # trade_direction is inherited from BaseStrategy
    )
    
    def __init__(self):
        super().__init__()
        
        # Moving averages
        self.fast_sma = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.slow_sma = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        
        # Crossover signal
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)
        
        self.log(f'SMA Crossover initialized: fast={self.p.fast_period}, slow={self.p.slow_period}')
    
    def next(self):
        if self.order:
            return
        
        # Pending swing işlemlerini kontrol et
        self.check_pending_reverse()
        
        price = self.data.close[0]
        
        if not self.position:
            # LONG: Fast crosses above slow
            if self.crossover[0] > 0 and self.should_trade_long():
                # Stop loss at slow SMA (support level)
                sl_price = min(self.slow_sma[0], price * 0.97)
                self.log(f'BUY SIGNAL - Fast SMA crossed above Slow SMA, SL: {sl_price:.2f}')
                self.buy_with_bracket(sl_price=sl_price)
            
            # SHORT: Fast crosses below slow
            elif self.crossover[0] < 0 and self.should_trade_short():
                sl_price = max(self.slow_sma[0], price * 1.03)
                self.log(f'SELL SIGNAL - Fast SMA crossed below Slow SMA, SL: {sl_price:.2f}')
                self.sell_with_bracket(sl_price=sl_price)
        
        else:
            # SWING TRADING: Ters sinyal gelince yön değiştir
            # Long pozisyondayken Short sinyali -> Kapat ve Short aç
            if self.position.size > 0 and self.crossover[0] < 0:
                if self.should_trade_short():
                    sl_price = max(self.slow_sma[0], price * 1.03)
                    self.reverse_to_short(sl_price=sl_price)
                else:
                    self.close_position()
            
            # Short pozisyondayken Long sinyali -> Kapat ve Long aç
            elif self.position.size < 0 and self.crossover[0] > 0:
                if self.should_trade_long():
                    sl_price = min(self.slow_sma[0], price * 0.97)
                    self.reverse_to_long(sl_price=sl_price)
                else:
                    self.close_position()
