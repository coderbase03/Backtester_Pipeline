"""
Supertrend Indicator for Backtrader

The Supertrend indicator combines ATR (Average True Range) with a 
multiplier to create dynamic support/resistance levels that flip
based on price action.
"""

import backtrader as bt


class SuperTrend(bt.Indicator):
    """
    Supertrend Indicator
    
    Params:
        period (int): ATR period (default: 10)
        multiplier (float): ATR multiplier (default: 3.0)
    
    Lines:
        super_trend: The supertrend line
        direction: 1 for bullish, -1 for bearish
    """
    
    lines = ('super_trend', 'direction')
    
    params = (
        ('period', 10),
        ('multiplier', 3.0),
    )
    
    plotinfo = dict(
        subplot=False,
        plotlinelabels=True,
    )
    
    plotlines = dict(
        super_trend=dict(color='blue', linewidth=2),
        direction=dict(_plotskip=True),
    )
    
    def __init__(self):
        # ATR calculation
        self.atr = bt.indicators.ATR(self.data, period=self.p.period)
        
        # HL2 (High + Low) / 2
        self.hl2 = (self.data.high + self.data.low) / 2
        
        # We need to wait for ATR to warm up
        self.addminperiod(self.p.period)
    
    def next(self):
        """Calculate Supertrend for current bar."""
        # Get ATR value
        atr = self.atr[0]
        
        # Skip if ATR is not available
        if atr != atr:  # NaN check
            self.lines.super_trend[0] = self.data.close[0]
            self.lines.direction[0] = 1
            return
        
        # Calculate basic bands
        hl2 = (self.data.high[0] + self.data.low[0]) / 2
        basic_upper = hl2 + (self.p.multiplier * atr)
        basic_lower = hl2 - (self.p.multiplier * atr)
        
        # Get previous values (with defaults for first bar)
        if len(self) <= 1:
            # First bar - initialize
            if self.data.close[0] > hl2:
                self.lines.super_trend[0] = basic_lower
                self.lines.direction[0] = 1
            else:
                self.lines.super_trend[0] = basic_upper
                self.lines.direction[0] = -1
            return
        
        prev_st = self.lines.super_trend[-1]
        prev_dir = self.lines.direction[-1]
        prev_close = self.data.close[-1]
        curr_close = self.data.close[0]
        
        # Calculate final bands based on previous values
        # Final Upper Band
        if basic_upper < prev_st or prev_close > prev_st:
            final_upper = basic_upper
        else:
            final_upper = prev_st if prev_dir == -1 else basic_upper
        
        # Final Lower Band  
        if basic_lower > prev_st or prev_close < prev_st:
            final_lower = basic_lower
        else:
            final_lower = prev_st if prev_dir == 1 else basic_lower
        
        # Determine direction and supertrend value
        if prev_dir == 1:
            # Was bullish
            if curr_close < final_lower:
                # Switch to bearish
                self.lines.super_trend[0] = final_upper
                self.lines.direction[0] = -1
            else:
                # Stay bullish
                self.lines.super_trend[0] = final_lower
                self.lines.direction[0] = 1
        else:
            # Was bearish
            if curr_close > final_upper:
                # Switch to bullish
                self.lines.super_trend[0] = final_lower
                self.lines.direction[0] = 1
            else:
                # Stay bearish
                self.lines.super_trend[0] = final_upper
                self.lines.direction[0] = -1


class SuperTrendBands(bt.Indicator):
    """
    Simplified Supertrend that only outputs direction for strategy use.
    """
    
    lines = ('direction',)
    
    params = (
        ('period', 10),
        ('multiplier', 3.0),
    )
    
    def __init__(self):
        self.st = SuperTrend(
            self.data,
            period=self.p.period,
            multiplier=self.p.multiplier
        )
        self.lines.direction = self.st.direction
