"""
SMC (Smart Money Concepts) Strategy

A strategy based on institutional trading concepts:
- Trade with the trend (Break of Structure)
- Enter at Order Blocks or Fair Value Gaps
- Target liquidity levels

Entry Rules:
- Bullish: Uptrend (BOS) + price at bullish OB or FVG
- Bearish: Downtrend (BOS) + price at bearish OB or FVG

Exit Rules:
- Take profit at liquidity levels (swing highs/lows)
- Stop loss below/above order block
"""

import backtrader as bt
from .base import BaseStrategy
from ..indicators.smc import SMCIndicator, OrderBlocks, FairValueGap, LiquidityLevels, BreakOfStructure


class SMCStrategy(BaseStrategy):
    """
    Smart Money Concepts Strategy
    
    Params (inherited from BaseStrategy):
        trade_direction: 'long', 'short', or 'both'
        use_bracket, tp_pct, sl_pct, leverage, etc.
        
    Params (strategy-specific):
        atr_period: ATR period for SMC calculations
        swing_lookback: Bars to confirm swing points
        ob_strength: Minimum impulse strength for order blocks
    """
    
    # TV Chart indicator configuration
    STRATEGY_INDICATORS = {
        'sma': 'swing_lookback'  # Use SMA for trend visualization
    }
    
    params = (
        ('atr_period', 14),
        ('swing_lookback', 5),
        ('ob_strength', 1.5),
        # trade_direction is inherited from BaseStrategy
    )
    
    def __init__(self):
        super().__init__()
        
        # SMC Indicators
        self.smc = SMCIndicator(
            self.data,
            atr_period=self.p.atr_period,
            swing_lookback=self.p.swing_lookback,
            ob_strength=self.p.ob_strength,
        )
        
        # Individual indicators for more control
        self.order_blocks = self.smc.order_blocks
        self.fvg = self.smc.fvg
        self.liquidity = self.smc.liquidity
        self.bos = self.smc.bos
        
        self.log(f'SMC Strategy initialized: swing_lookback={self.p.swing_lookback}')
    
    def next(self):
        import math
        
        if self.order:
            return
        
        # Handle NaN values for signal and trend
        raw_signal = self.smc.signal[0]
        raw_trend = self.smc.trend[0]
        
        if math.isnan(raw_signal) or math.isnan(raw_trend):
            return  # Skip if values are NaN
        
        signal = int(raw_signal)
        trend = int(raw_trend)
        price = self.data.close[0]
        
        if not self.position:
            # ======== LONG ENTRY ========
            if signal == 1 and self.should_trade_long():
                # Get stop loss from order block or swing low
                sl_price = self.order_blocks.bullish_ob[0]
                if sl_price != sl_price:  # NaN check
                    sl_price = self.liquidity.swing_low[0]
                if sl_price != sl_price:
                    sl_price = price * 0.98  # Default 2% below
                
                # Get take profit from swing high (liquidity target)
                tp_price = self.liquidity.swing_high[0]
                if tp_price != tp_price:
                    tp_price = price * 1.04  # Default 4% above
                
                self.log(f'SMC LONG SIGNAL - Price: {price:.2f}, SL: {sl_price:.2f}, TP: {tp_price:.2f}')
                self.buy_with_bracket(sl_price=sl_price, tp_price=tp_price)
            
            # ======== SHORT ENTRY ========
            elif signal == -1 and self.should_trade_short():
                # Get stop loss from order block or swing high
                sl_price = self.order_blocks.bearish_ob[0]
                if sl_price != sl_price:
                    sl_price = self.liquidity.swing_high[0]
                if sl_price != sl_price:
                    sl_price = price * 1.02
                
                # Get take profit from swing low
                tp_price = self.liquidity.swing_low[0]
                if tp_price != tp_price:
                    tp_price = price * 0.96
                
                self.log(f'SMC SHORT SIGNAL - Price: {price:.2f}, SL: {sl_price:.2f}, TP: {tp_price:.2f}')
                self.sell_with_bracket(sl_price=sl_price, tp_price=tp_price)
    
    def stop(self):
        super().stop()
        self.log(f'Final Value: {self.broker.getvalue():.2f}')
