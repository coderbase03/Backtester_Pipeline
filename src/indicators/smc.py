"""
Smart Money Concepts (SMC) Indicators for Backtrader

Implements key SMC concepts used by institutional traders:
- Order Blocks (OB): Areas of accumulation/distribution
- Fair Value Gaps (FVG): Imbalance zones in price
- Liquidity Levels: Swing highs/lows where stop losses cluster
- Break of Structure (BOS): Trend confirmation signals
"""

import backtrader as bt
import numpy as np


class OrderBlocks(bt.Indicator):
    """
    Order Block Indicator
    
    Detects bullish and bearish order blocks based on:
    - Strong move away from a zone
    - The candle before the impulse move is the order block
    
    Lines:
        bullish_ob: Price level of bullish order block (demand zone)
        bearish_ob: Price level of bearish order block (supply zone)
        ob_signal: 1 for bullish OB, -1 for bearish OB, 0 for none
    """
    
    lines = ('bullish_ob', 'bearish_ob', 'ob_signal')
    
    params = (
        ('strength', 2.0),      # Minimum ATR multiplier for impulse move
        ('lookback', 10),       # Bars to look back for OB identification
        ('atr_period', 14),
    )
    
    plotinfo = dict(subplot=False)
    
    plotlines = dict(
        bullish_ob=dict(color='green', linestyle='--', linewidth=1),
        bearish_ob=dict(color='red', linestyle='--', linewidth=1),
        ob_signal=dict(_plotskip=True),
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.addminperiod(self.p.atr_period + self.p.lookback)
        
        # Track active order blocks
        self._active_bullish_ob = None
        self._active_bearish_ob = None
    
    def next(self):
        # Default values
        self.lines.bullish_ob[0] = self._active_bullish_ob or float('nan')
        self.lines.bearish_ob[0] = self._active_bearish_ob or float('nan')
        self.lines.ob_signal[0] = 0
        
        atr = self.atr[0]
        if atr <= 0:
            return
        
        # Look for bullish order block (down candle before strong up move)
        # Bullish OB: bearish candle followed by strong bullish impulse
        if len(self) >= 3:
            # Check if current bar is a strong bullish impulse
            impulse_size = self.data.close[0] - self.data.open[0]
            
            if impulse_size > self.p.strength * atr:
                # Strong bullish move - look for bearish candle before
                for i in range(-1, -4, -1):
                    if self.data.close[i] < self.data.open[i]:
                        # Found bearish candle = bullish order block
                        self._active_bullish_ob = self.data.low[i]
                        self.lines.bullish_ob[0] = self._active_bullish_ob
                        self.lines.ob_signal[0] = 1
                        break
            
            # Check for bearish order block (up candle before strong down move)
            elif impulse_size < -self.p.strength * atr:
                # Strong bearish move - look for bullish candle before
                for i in range(-1, -4, -1):
                    if self.data.close[i] > self.data.open[i]:
                        # Found bullish candle = bearish order block
                        self._active_bearish_ob = self.data.high[i]
                        self.lines.bearish_ob[0] = self._active_bearish_ob
                        self.lines.ob_signal[0] = -1
                        break
        
        # Invalidate order blocks if price breaks through
        if self._active_bullish_ob and self.data.close[0] < self._active_bullish_ob:
            self._active_bullish_ob = None
        
        if self._active_bearish_ob and self.data.close[0] > self._active_bearish_ob:
            self._active_bearish_ob = None


class FairValueGap(bt.Indicator):
    """
    Fair Value Gap (FVG) / Imbalance Indicator
    
    Detects gaps between candles that indicate institutional activity:
    - Bullish FVG: Gap up (candle 1 high < candle 3 low)
    - Bearish FVG: Gap down (candle 1 low > candle 3 high)
    
    Lines:
        bullish_fvg_top: Top of bullish FVG zone
        bullish_fvg_bot: Bottom of bullish FVG zone
        bearish_fvg_top: Top of bearish FVG zone  
        bearish_fvg_bot: Bottom of bearish FVG zone
        fvg_signal: 1 for bullish, -1 for bearish, 0 for none
    """
    
    lines = ('bullish_fvg_top', 'bullish_fvg_bot', 
             'bearish_fvg_top', 'bearish_fvg_bot', 'fvg_signal')
    
    params = (
        ('min_gap_atr', 0.5),  # Minimum gap size as ATR multiple
        ('atr_period', 14),
    )
    
    plotinfo = dict(subplot=False)
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.addminperiod(self.p.atr_period + 3)
        
        # Track active FVGs
        self._bullish_fvgs = []  # List of (top, bottom)
        self._bearish_fvgs = []
    
    def next(self):
        # Default values
        self.lines.fvg_signal[0] = 0
        self.lines.bullish_fvg_top[0] = float('nan')
        self.lines.bullish_fvg_bot[0] = float('nan')
        self.lines.bearish_fvg_top[0] = float('nan')
        self.lines.bearish_fvg_bot[0] = float('nan')
        
        atr = self.atr[0]
        if atr <= 0 or len(self) < 3:
            return
        
        # Check for bullish FVG: candle[-2].high < candle[0].low
        # This means there's a gap that price jumped over
        candle_1_high = self.data.high[-2]
        candle_3_low = self.data.low[0]
        
        if candle_3_low > candle_1_high:
            gap_size = candle_3_low - candle_1_high
            if gap_size >= self.p.min_gap_atr * atr:
                # Bullish FVG detected
                self._bullish_fvgs.append((candle_3_low, candle_1_high))
                self.lines.bullish_fvg_top[0] = candle_3_low
                self.lines.bullish_fvg_bot[0] = candle_1_high
                self.lines.fvg_signal[0] = 1
        
        # Check for bearish FVG: candle[-2].low > candle[0].high
        candle_1_low = self.data.low[-2]
        candle_3_high = self.data.high[0]
        
        if candle_1_low > candle_3_high:
            gap_size = candle_1_low - candle_3_high
            if gap_size >= self.p.min_gap_atr * atr:
                # Bearish FVG detected
                self._bearish_fvgs.append((candle_1_low, candle_3_high))
                self.lines.bearish_fvg_top[0] = candle_1_low
                self.lines.bearish_fvg_bot[0] = candle_3_high
                self.lines.fvg_signal[0] = -1
        
        # Fill in most recent unfilled FVGs
        if self._bullish_fvgs and self.lines.fvg_signal[0] == 0:
            top, bot = self._bullish_fvgs[-1]
            # Check if FVG is filled
            if self.data.low[0] <= bot:
                self._bullish_fvgs.pop()
            else:
                self.lines.bullish_fvg_top[0] = top
                self.lines.bullish_fvg_bot[0] = bot
        
        if self._bearish_fvgs and self.lines.fvg_signal[0] == 0:
            top, bot = self._bearish_fvgs[-1]
            # Check if FVG is filled
            if self.data.high[0] >= top:
                self._bearish_fvgs.pop()
            else:
                self.lines.bearish_fvg_top[0] = top
                self.lines.bearish_fvg_bot[0] = bot


class LiquidityLevels(bt.Indicator):
    """
    Liquidity Levels Indicator
    
    Detects swing highs and lows where liquidity (stop losses) accumulates:
    - Swing highs: Areas where shorts have stops (buy-side liquidity)
    - Swing lows: Areas where longs have stops (sell-side liquidity)
    
    Lines:
        swing_high: Recent swing high level
        swing_low: Recent swing low level
        liquidity_swept: 1 when high swept, -1 when low swept, 0 otherwise
    """
    
    lines = ('swing_high', 'swing_low', 'liquidity_swept')
    
    params = (
        ('swing_lookback', 5),  # Bars on each side to confirm swing
    )
    
    plotinfo = dict(subplot=False)
    
    plotlines = dict(
        swing_high=dict(color='red', linestyle=':', linewidth=1),
        swing_low=dict(color='green', linestyle=':', linewidth=1),
        liquidity_swept=dict(_plotskip=True),
    )
    
    def __init__(self):
        self.addminperiod(self.p.swing_lookback * 2 + 1)
        
        self._recent_swing_highs = []
        self._recent_swing_lows = []
    
    def next(self):
        lb = self.p.swing_lookback
        self.lines.liquidity_swept[0] = 0
        
        # Check for swing high at position -lb (middle of lookback window)
        if len(self) >= lb * 2 + 1:
            middle_high = self.data.high[-lb]
            is_swing_high = True
            
            for i in range(-lb * 2, 1):
                if i == -lb:
                    continue
                if self.data.high[i] >= middle_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                self._recent_swing_highs.append(middle_high)
                # Keep only last 10 swing points
                if len(self._recent_swing_highs) > 10:
                    self._recent_swing_highs.pop(0)
        
        # Check for swing low
        if len(self) >= lb * 2 + 1:
            middle_low = self.data.low[-lb]
            is_swing_low = True
            
            for i in range(-lb * 2, 1):
                if i == -lb:
                    continue
                if self.data.low[i] <= middle_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                self._recent_swing_lows.append(middle_low)
                if len(self._recent_swing_lows) > 10:
                    self._recent_swing_lows.pop(0)
        
        # Output most recent levels
        if self._recent_swing_highs:
            self.lines.swing_high[0] = self._recent_swing_highs[-1]
            # Check if liquidity was swept (price broke above swing high)
            if self.data.high[0] > self._recent_swing_highs[-1]:
                self.lines.liquidity_swept[0] = 1
                self._recent_swing_highs.pop()
        else:
            self.lines.swing_high[0] = float('nan')
        
        if self._recent_swing_lows:
            self.lines.swing_low[0] = self._recent_swing_lows[-1]
            # Check if liquidity was swept (price broke below swing low)
            if self.data.low[0] < self._recent_swing_lows[-1]:
                self.lines.liquidity_swept[0] = -1
                self._recent_swing_lows.pop()
        else:
            self.lines.swing_low[0] = float('nan')


class BreakOfStructure(bt.Indicator):
    """
    Break of Structure (BOS) Indicator
    
    Detects when market structure changes:
    - Bullish BOS: Higher high made (confirms uptrend)
    - Bearish BOS: Lower low made (confirms downtrend)
    
    Lines:
        bos_signal: 1 for bullish BOS, -1 for bearish BOS
        trend: Current trend (1 = up, -1 = down)
    """
    
    lines = ('bos_signal', 'trend')
    
    params = (
        ('swing_lookback', 5),
    )
    
    plotinfo = dict(subplot=True)
    
    def __init__(self):
        self.liquidity = LiquidityLevels(self.data, swing_lookback=self.p.swing_lookback)
        
        self._last_swing_high = None
        self._last_swing_low = None
        self._trend = 0
    
    def next(self):
        self.lines.bos_signal[0] = 0
        
        current_high = self.data.high[0]
        current_low = self.data.low[0]
        
        swing_high = self.liquidity.swing_high[0]
        swing_low = self.liquidity.swing_low[0]
        
        # Update tracked swing points
        if swing_high == swing_high:  # Not NaN
            if self._last_swing_high is None or swing_high != self._last_swing_high:
                self._last_swing_high = swing_high
        
        if swing_low == swing_low:  # Not NaN
            if self._last_swing_low is None or swing_low != self._last_swing_low:
                self._last_swing_low = swing_low
        
        # Check for Break of Structure
        if self._last_swing_high is not None and current_high > self._last_swing_high:
            # Bullish BOS - higher high made
            self.lines.bos_signal[0] = 1
            self._trend = 1
        
        if self._last_swing_low is not None and current_low < self._last_swing_low:
            # Bearish BOS - lower low made
            self.lines.bos_signal[0] = -1
            self._trend = -1
        
        self.lines.trend[0] = self._trend


class SMCIndicator(bt.Indicator):
    """
    Combined SMC Indicator
    
    Combines all SMC concepts into one indicator for easy strategy use.
    
    Lines:
        signal: Trade signal (1=buy, -1=sell, 0=none)
        trend: Overall trend
        ob_level: Order block level to watch
        fvg_level: FVG level to watch
        liquidity_level: Liquidity level to watch
    """
    
    lines = ('signal', 'trend', 'ob_level', 'fvg_level', 'liquidity_level')
    
    params = (
        ('atr_period', 14),
        ('swing_lookback', 5),
        ('ob_strength', 2.0),
    )
    
    plotinfo = dict(subplot=True)
    
    def __init__(self):
        # Sub-indicators
        self.order_blocks = OrderBlocks(
            self.data,
            atr_period=self.p.atr_period,
            strength=self.p.ob_strength
        )
        
        self.fvg = FairValueGap(
            self.data,
            atr_period=self.p.atr_period
        )
        
        self.liquidity = LiquidityLevels(
            self.data,
            swing_lookback=self.p.swing_lookback
        )
        
        self.bos = BreakOfStructure(
            self.data,
            swing_lookback=self.p.swing_lookback
        )
    
    def next(self):
        # Combine signals
        self.lines.trend[0] = self.bos.trend[0]
        
        # Output key levels
        if self.order_blocks.bullish_ob[0] == self.order_blocks.bullish_ob[0]:
            self.lines.ob_level[0] = self.order_blocks.bullish_ob[0]
        elif self.order_blocks.bearish_ob[0] == self.order_blocks.bearish_ob[0]:
            self.lines.ob_level[0] = self.order_blocks.bearish_ob[0]
        else:
            self.lines.ob_level[0] = float('nan')
        
        if self.fvg.bullish_fvg_bot[0] == self.fvg.bullish_fvg_bot[0]:
            self.lines.fvg_level[0] = self.fvg.bullish_fvg_bot[0]
        elif self.fvg.bearish_fvg_top[0] == self.fvg.bearish_fvg_top[0]:
            self.lines.fvg_level[0] = self.fvg.bearish_fvg_top[0]
        else:
            self.lines.fvg_level[0] = float('nan')
        
        # Liquidity level
        if self.liquidity.swing_low[0] == self.liquidity.swing_low[0]:
            self.lines.liquidity_level[0] = self.liquidity.swing_low[0]
        else:
            self.lines.liquidity_level[0] = float('nan')
        
        # Generate signal based on confluence
        signal = 0
        
        # Bullish setup: uptrend + price at bullish OB or FVG
        if self.bos.trend[0] == 1:
            price = self.data.close[0]
            ob = self.order_blocks.bullish_ob[0]
            fvg_bot = self.fvg.bullish_fvg_bot[0]
            
            # Price touching bullish OB
            if ob == ob and price <= ob * 1.01:
                signal = 1
            # Price in bullish FVG
            elif fvg_bot == fvg_bot:
                fvg_top = self.fvg.bullish_fvg_top[0]
                if fvg_bot <= price <= fvg_top:
                    signal = 1
        
        # Bearish setup: downtrend + price at bearish OB or FVG
        elif self.bos.trend[0] == -1:
            price = self.data.close[0]
            ob = self.order_blocks.bearish_ob[0]
            fvg_top = self.fvg.bearish_fvg_top[0]
            
            # Price touching bearish OB
            if ob == ob and price >= ob * 0.99:
                signal = -1
            # Price in bearish FVG
            elif fvg_top == fvg_top:
                fvg_bot = self.fvg.bearish_fvg_bot[0]
                if fvg_bot <= price <= fvg_top:
                    signal = -1
        
        self.lines.signal[0] = signal
