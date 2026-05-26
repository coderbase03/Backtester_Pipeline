"""
Indicator Calculation Module for TV Charts

Provides standardized indicator calculations compatible with lightweight-charts.
All functions return DataFrames with 'time' and 'value' columns.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has required columns and proper format."""
    result = df.copy()
    
    # Ensure 'time' column exists
    if 'time' not in result.columns:
        if 'datetime' in result.columns:
            result['time'] = pd.to_datetime(result['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(result.index, pd.DatetimeIndex):
            result['time'] = result.index.strftime('%Y-%m-%d %H:%M:%S')
    
    return result


# =============================================================================
# TREND INDICATORS
# =============================================================================

def calculate_sma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Simple Moving Average
    
    Returns DataFrame with columns: time, value
    """
    df = prepare_dataframe(df)
    sma = df['close'].rolling(window=period).mean()
    
    result = pd.DataFrame({
        'time': df['time'],
        'value': sma
    }).dropna()
    
    return result


def calculate_ema(df: pd.DataFrame, period: int = 21) -> pd.DataFrame:
    """
    Exponential Moving Average
    
    Returns DataFrame with columns: time, value
    """
    df = prepare_dataframe(df)
    ema = df['close'].ewm(span=period, adjust=False).mean()
    
    result = pd.DataFrame({
        'time': df['time'],
        'value': ema
    }).dropna()
    
    return result


def calculate_supertrend(
    df: pd.DataFrame, 
    period: int = 10, 
    multiplier: float = 3.0
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Supertrend Indicator (TradingView style)
    
    Returns:
        - supertrend_df: DataFrame with time, value (supertrend line)
        - direction_df: DataFrame with time, value (1=bullish, -1=bearish)
    """
    df = prepare_dataframe(df)
    
    # ATR calculation
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
    tr[0] = high[0] - low[0]
    
    # ATR using RMA (same as TradingView)
    atr = np.zeros(len(df))
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(df)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    
    # HL2
    hl2 = (high + low) / 2
    
    # Basic bands
    upper_basic = hl2 + (multiplier * atr)
    lower_basic = hl2 - (multiplier * atr)
    
    # Final bands (with smoothing logic)
    upper_band = np.zeros(len(df))
    lower_band = np.zeros(len(df))
    supertrend = np.zeros(len(df))
    direction = np.zeros(len(df))
    
    upper_band[period-1] = upper_basic[period-1]
    lower_band[period-1] = lower_basic[period-1]
    
    for i in range(period, len(df)):
        # Upper band
        if lower_basic[i] > lower_band[i-1] or close[i-1] < lower_band[i-1]:
            lower_band[i] = lower_basic[i]
        else:
            lower_band[i] = lower_band[i-1]
        
        # Lower band
        if upper_basic[i] < upper_band[i-1] or close[i-1] > upper_band[i-1]:
            upper_band[i] = upper_basic[i]
        else:
            upper_band[i] = upper_band[i-1]
        
        # Supertrend and direction
        if i == period:
            direction[i] = 1 if close[i] > upper_band[i] else -1
        else:
            if direction[i-1] == -1 and close[i] > upper_band[i]:
                direction[i] = 1
            elif direction[i-1] == 1 and close[i] < lower_band[i]:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]
        
        supertrend[i] = lower_band[i] if direction[i] == 1 else upper_band[i]
    
    # Create DataFrames
    time_col = df['time'].values
    
    supertrend_df = pd.DataFrame({
        'time': time_col[period:],
        'value': supertrend[period:]
    })
    
    direction_df = pd.DataFrame({
        'time': time_col[period:],
        'value': direction[period:]
    })
    
    return supertrend_df, direction_df


# =============================================================================
# MOMENTUM INDICATORS
# =============================================================================

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Relative Strength Index
    
    Returns DataFrame with columns: time, value (0-100)
    """
    df = prepare_dataframe(df)
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    result = pd.DataFrame({
        'time': df['time'],
        'value': rsi
    }).dropna()
    
    return result


def calculate_macd(
    df: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Moving Average Convergence Divergence
    
    Returns:
        - macd_df: MACD line
        - signal_df: Signal line
        - histogram_df: MACD histogram
    """
    df = prepare_dataframe(df)
    
    fast_ema = df['close'].ewm(span=fast_period, adjust=False).mean()
    slow_ema = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    
    macd_df = pd.DataFrame({
        'time': df['time'],
        'value': macd_line
    }).dropna()
    
    signal_df = pd.DataFrame({
        'time': df['time'],
        'value': signal_line
    }).dropna()
    
    histogram_df = pd.DataFrame({
        'time': df['time'],
        'value': histogram
    }).dropna()
    
    return macd_df, signal_df, histogram_df


def calculate_stochastic(
    df: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Stochastic Oscillator
    
    Returns:
        - k_df: %K line
        - d_df: %D line (signal)
    """
    df = prepare_dataframe(df)
    
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    k = 100 * ((df['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()
    
    k_df = pd.DataFrame({
        'time': df['time'],
        'value': k
    }).dropna()
    
    d_df = pd.DataFrame({
        'time': df['time'],
        'value': d
    }).dropna()
    
    return k_df, d_df


# =============================================================================
# VOLATILITY INDICATORS
# =============================================================================

def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Bollinger Bands
    
    Returns:
        - upper_df: Upper band
        - middle_df: Middle band (SMA)
        - lower_df: Lower band
    """
    df = prepare_dataframe(df)
    
    middle = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    upper_df = pd.DataFrame({
        'time': df['time'],
        'value': upper
    }).dropna()
    
    middle_df = pd.DataFrame({
        'time': df['time'],
        'value': middle
    }).dropna()
    
    lower_df = pd.DataFrame({
        'time': df['time'],
        'value': lower
    }).dropna()
    
    return upper_df, middle_df, lower_df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Average True Range
    
    Returns DataFrame with columns: time, value
    """
    df = prepare_dataframe(df)
    
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=period).mean()
    
    result = pd.DataFrame({
        'time': df['time'],
        'value': atr
    }).dropna()
    
    return result


# =============================================================================
# INDICATOR DEFINITIONS (for chart_viewer compatibility)
# =============================================================================

INDICATOR_DEFINITIONS = {
    # === TREND ===
    'SMA 10': {
        'category': 'Trend',
        'type': 'line',
        'color': '#4CAF50',
        'width': 1.5,
        'params': {'period': 10},
        'calc_func': calculate_sma
    },
    'SMA 20': {
        'category': 'Trend',
        'type': 'line',
        'color': '#2962FF',
        'width': 2,
        'params': {'period': 20},
        'calc_func': calculate_sma
    },
    'SMA 50': {
        'category': 'Trend',
        'type': 'line',
        'color': '#FF6D00',
        'width': 2,
        'params': {'period': 50},
        'calc_func': calculate_sma
    },
    'SMA 200': {
        'category': 'Trend',
        'type': 'line',
        'color': '#F44336',
        'width': 2.5,
        'params': {'period': 200},
        'calc_func': calculate_sma
    },
    'EMA 9': {
        'category': 'Trend',
        'type': 'line',
        'color': '#00BCD4',
        'width': 1.5,
        'params': {'period': 9},
        'calc_func': calculate_ema
    },
    'EMA 21': {
        'category': 'Trend',
        'type': 'line',
        'color': '#FFC107',
        'width': 1.5,
        'params': {'period': 21},
        'calc_func': calculate_ema
    },
    'Supertrend': {
        'category': 'Trend',
        'type': 'supertrend',
        'color_bull': '#00d26a',
        'color_bear': '#ff4757',
        'width': 2,
        'params': {'period': 10, 'multiplier': 3.0},
        'calc_func': calculate_supertrend
    },
    
    # === MOMENTUM ===
    'RSI 14': {
        'category': 'Momentum',
        'type': 'subchart',
        'color': '#9C27B0',
        'width': 1.5,
        'params': {'period': 14},
        'calc_func': calculate_rsi,
        'levels': [70, 30]
    },
    'MACD': {
        'category': 'Momentum',
        'type': 'macd_subchart',
        'color_macd': '#2962FF',
        'color_signal': '#FF6D00',
        'color_histogram_pos': '#26a69a',
        'color_histogram_neg': '#ef5350',
        'params': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
        'calc_func': calculate_macd
    },
    'Stochastic': {
        'category': 'Momentum',
        'type': 'stochastic_subchart',
        'color_k': '#2962FF',
        'color_d': '#FF6D00',
        'params': {'k_period': 14, 'd_period': 3},
        'calc_func': calculate_stochastic,
        'levels': [80, 20]
    },
    
    # === VOLATILITY ===
    'Bollinger Bands': {
        'category': 'Volatility',
        'type': 'multi_line',
        'colors': ['#2196F3', '#9E9E9E', '#2196F3'],  # upper, middle, lower
        'width': 1.5,
        'params': {'period': 20, 'std_dev': 2.0},
        'calc_func': calculate_bollinger_bands
    },
    'ATR 14': {
        'category': 'Volatility',
        'type': 'subchart',
        'color': '#FF9800',
        'width': 1.5,
        'params': {'period': 14},
        'calc_func': calculate_atr
    },
}


def get_indicators_by_category() -> dict:
    """Group indicators by category for menu display."""
    categories = {}
    for name, definition in INDICATOR_DEFINITIONS.items():
        cat = definition['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)
    return categories
