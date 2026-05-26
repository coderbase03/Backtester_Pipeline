"""
Custom Technical Indicators for Backtrader

Common indicators with enhanced functionality.
"""

import backtrader as bt
import numpy as np


class ATR(bt.Indicator):
    """
    Average True Range with optional smoothing methods.
    
    Params:
        period: Lookback period
        movav: Moving average type (bt.indicators.SmoothedMovingAverage by default)
    """
    
    lines = ('atr',)
    params = (
        ('period', 14),
        ('movav', bt.indicators.SmoothedMovingAverage),
    )
    
    def __init__(self):
        tr = bt.indicators.TrueRange(self.data)
        self.lines.atr = self.p.movav(tr, period=self.p.period)


class EMA(bt.Indicator):
    """Exponential Moving Average."""
    
    lines = ('ema',)
    params = (('period', 20),)
    
    def __init__(self):
        self.lines.ema = bt.indicators.EMA(self.data.close, period=self.p.period)


class SMA(bt.Indicator):
    """Simple Moving Average."""
    
    lines = ('sma',)
    params = (('period', 20),)
    
    def __init__(self):
        self.lines.sma = bt.indicators.SMA(self.data.close, period=self.p.period)


class RSI(bt.Indicator):
    """
    Relative Strength Index with overbought/oversold levels.
    
    Lines:
        rsi: RSI value
        overbought: Overbought level (default 70)
        oversold: Oversold level (default 30)
    """
    
    lines = ('rsi', 'overbought', 'oversold')
    params = (
        ('period', 14),
        ('upperband', 70),
        ('lowerband', 30),
    )
    
    def __init__(self):
        self.lines.rsi = bt.indicators.RSI(self.data.close, period=self.p.period)
        self.lines.overbought = bt.LineNum(self.p.upperband)
        self.lines.oversold = bt.LineNum(self.p.lowerband)


class MACD(bt.Indicator):
    """
    MACD with histogram.
    
    Lines:
        macd: MACD line
        signal: Signal line
        histogram: MACD histogram
    """
    
    lines = ('macd', 'signal', 'histogram')
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
    )
    
    def __init__(self):
        fast_ema = bt.indicators.EMA(self.data.close, period=self.p.fast_period)
        slow_ema = bt.indicators.EMA(self.data.close, period=self.p.slow_period)
        
        self.lines.macd = fast_ema - slow_ema
        self.lines.signal = bt.indicators.EMA(self.lines.macd, period=self.p.signal_period)
        self.lines.histogram = self.lines.macd - self.lines.signal


class BollingerBands(bt.Indicator):
    """
    Bollinger Bands with customizable standard deviation.
    
    Lines:
        mid: Middle band (SMA)
        top: Upper band
        bot: Lower band
        pctb: Percent B (where price is relative to bands)
    """
    
    lines = ('mid', 'top', 'bot', 'pctb')
    params = (
        ('period', 20),
        ('devfactor', 2.0),
    )
    
    def __init__(self):
        self.lines.mid = bt.indicators.SMA(self.data.close, period=self.p.period)
        stddev = bt.indicators.StdDev(self.data.close, period=self.p.period)
        
        self.lines.top = self.lines.mid + (self.p.devfactor * stddev)
        self.lines.bot = self.lines.mid - (self.p.devfactor * stddev)
        
        # Percent B: (Price - Lower) / (Upper - Lower)
        self.lines.pctb = (self.data.close - self.lines.bot) / (self.lines.top - self.lines.bot)


class VWAP(bt.Indicator):
    """
    Volume Weighted Average Price (intraday reset).
    
    Note: For proper VWAP, data should include session markers
    or be daily data where each bar represents a new session.
    """
    
    lines = ('vwap',)
    
    def __init__(self):
        # Typical price
        self.tp = (self.data.high + self.data.low + self.data.close) / 3
        
        # Cumulative TP * Volume and Volume
        self.cum_tp_vol = bt.indicators.CumSum(self.tp * self.data.volume)
        self.cum_vol = bt.indicators.CumSum(self.data.volume)
    
    def next(self):
        if self.cum_vol[0] != 0:
            self.lines.vwap[0] = self.cum_tp_vol[0] / self.cum_vol[0]
        else:
            self.lines.vwap[0] = self.tp[0]


class Stochastic(bt.Indicator):
    """
    Stochastic Oscillator with %K and %D lines.
    """
    
    lines = ('percK', 'percD')
    params = (
        ('period', 14),
        ('period_dfast', 3),
    )
    
    def __init__(self):
        stoch = bt.indicators.Stochastic(
            self.data,
            period=self.p.period,
            period_dfast=self.p.period_dfast
        )
        self.lines.percK = stoch.percK
        self.lines.percD = stoch.percD
