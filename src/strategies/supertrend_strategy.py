"""
Supertrend Strategy

A trend-following strategy using the Supertrend indicator.

Entry Rules:
- Long: Price crosses above Supertrend (direction changes to bullish)
- Short: Price crosses below Supertrend (direction changes to bearish)

Exit Rules:
- Opposite signal OR take profit/stop loss hit

Features:
- ATR-based position sizing
- Bracket orders with TP/SL
- Optional trailing stop
"""

import backtrader as bt
from .base import BaseStrategy
from ..indicators.supertrend import SuperTrend


class SupertrendStrategy(BaseStrategy):
    """
    Supertrend Trend-Following Strategy
    
    Params (inherited from BaseStrategy):
        trade_direction: 'long', 'short', or 'both'
        risk_pct: Risk per trade (default: 2%)
        use_bracket: Use bracket orders for TP/SL
        tp_pct: Take profit percentage (default: 3.0%)
        sl_pct: Stop loss percentage (default: 1.5%)
        trail_pct: Trailing stop percentage
        
    Params (Supertrend specific):
        st_period: Supertrend ATR period (default: 10)
        st_multiplier: Supertrend ATR multiplier (default: 3.0)
    """
    
    # TV Chart indicator configuration
    STRATEGY_INDICATORS = {
        'supertrend': ['st_period', 'st_multiplier']
    }
    
    params = (
        # Supertrend parameters
        ('st_period', 10),
        ('st_multiplier', 3.0),
        # trade_direction is inherited from BaseStrategy
    )
    
    def __init__(self):
        """Initialize Supertrend strategy."""
        super().__init__()
        
        # Supertrend indicator
        self.supertrend = SuperTrend(
            self.datas[0],
            period=self.p.st_period,
            multiplier=self.p.st_multiplier
        )
        
        self.log(f'Supertrend Strategy initialized: '
                f'period={self.p.st_period}, mult={self.p.st_multiplier}')
    
    def next(self):
        """Process each bar."""
        import math
        
        # Skip if we have pending orders
        if self.order:
            return
        
        # Get current direction from indicator - handle NaN
        raw_direction = self.supertrend.direction[0]
        if math.isnan(raw_direction):
            return  # Skip if direction is NaN (warmup period)
        
        curr_direction = int(raw_direction)
        
        # Get previous direction - handle NaN
        if len(self.supertrend.direction) > 1:
            raw_prev = self.supertrend.direction[-1]
            prev_direction = int(raw_prev) if not math.isnan(raw_prev) else curr_direction
        else:
            prev_direction = curr_direction
        
        # Check for direction change (signal)
        direction_changed = curr_direction != prev_direction
        
        # Current price and supertrend value
        price = self.dataclose[0]
        st_value = self.supertrend.super_trend[0]
        
        # ======== ENTRY LOGIC ========
        if not self.position:
            # LONG ENTRY: Direction changed to bullish
            if direction_changed and curr_direction == 1:
                if self.should_trade_long():
                    self.log(f'LONG SIGNAL - Price: {price:.2f}, ST: {st_value:.2f}')
                    # Use supertrend as initial stop loss
                    self.buy_with_bracket(sl_price=st_value)
            
            # SHORT ENTRY: Direction changed to bearish
            elif direction_changed and curr_direction == -1:
                if self.should_trade_short():
                    self.log(f'SHORT SIGNAL - Price: {price:.2f}, ST: {st_value:.2f}')
                    self.sell_with_bracket(sl_price=st_value)
        
        # ======== EXIT LOGIC ========
        else:
            # Exit on opposite signal (bracket orders handle TP/SL)
            if not self.p.use_bracket:
                # Long position - exit on bearish signal
                if self.position.size > 0 and direction_changed and curr_direction == -1:
                    self.log(f'EXIT LONG - Direction reversed')
                    self.close_position()
                
                # Short position - exit on bullish signal
                elif self.position.size < 0 and direction_changed and curr_direction == 1:
                    self.log(f'EXIT SHORT - Direction reversed')
                    self.close_position()
    
    def stop(self):
        """Strategy finished - print summary."""
        super().stop()
        self.log(f'Final Portfolio Value: {self.broker.getvalue():.2f}')


class SupertrendPullbackStrategy(BaseStrategy):
    """
    Supertrend with Pullback Entry
    
    Instead of entering on the direction change, waits for a pullback
    to the Supertrend line before entering.
    
    Entry Rules:
    - Trend is bullish (direction = 1)
    - Price pulls back to touch Supertrend line
    - Enter long on bounce
    
    This tends to give better risk:reward than immediate breakout entries.
    """
    
    # TV Chart indicator configuration
    STRATEGY_INDICATORS = {
        'supertrend': ['st_period', 'st_multiplier']
    }
    
    params = (
        ('st_period', 10),
        ('st_multiplier', 3.0),
        ('pullback_pct', 0.5),  # Enter when within X% of supertrend
        # trade_direction is inherited from BaseStrategy
    )
    
    def __init__(self):
        super().__init__()
        
        self.supertrend = SuperTrend(
            self.datas[0],
            period=self.p.st_period,
            multiplier=self.p.st_multiplier
        )
        
        # Track if we're in trend-following mode
        self.in_trend = False
        self.trend_direction = 0
    
    def next(self):
        if self.order:
            return
        
        curr_direction = self.supertrend.direction[0]
        price = self.dataclose[0]
        st_value = self.supertrend.super_trend[0]
        
        # Calculate distance from supertrend
        distance_pct = abs(price - st_value) / price * 100
        
        if not self.position:
            # LONG: Bullish trend + pullback to supertrend
            if curr_direction == 1 and self.should_trade_long():
                if distance_pct <= self.p.pullback_pct:
                    self.log(f'PULLBACK LONG - Price: {price:.2f}, ST: {st_value:.2f}')
                    self.buy_with_bracket(sl_price=st_value * 0.99)
            
            # SHORT: Bearish trend + pullback to supertrend
            elif curr_direction == -1 and self.should_trade_short():
                if distance_pct <= self.p.pullback_pct:
                    self.log(f'PULLBACK SHORT - Price: {price:.2f}, ST: {st_value:.2f}')
                    self.sell_with_bracket(sl_price=st_value * 1.01)
