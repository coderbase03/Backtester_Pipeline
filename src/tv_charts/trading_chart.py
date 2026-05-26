"""
TradingView Style Charts - Main Module

Uses lightweight-charts-python to display professional trading charts
with trade markers, indicators, and drawing tools.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

try:
    from lightweight_charts import Chart
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    print("Warning: lightweight-charts not installed. Run: pip install lightweight-charts")


class TradingViewChart:
    """
    TradingView-style chart with trade markers and indicators.
    
    Usage:
        chart = TradingViewChart()
        chart.load_data(df)  # OHLCV DataFrame
        chart.add_trades(trades)  # List of trade dicts
        chart.add_supertrend(period=10, multiplier=3)
        chart.show()
    """
    
    def __init__(self, title: str = "Opus Backtrader", width: int = 1400, height: int = 800):
        """Initialize chart with settings."""
        if not CHARTS_AVAILABLE:
            raise ImportError("lightweight-charts not installed. Run: pip install lightweight-charts")
        
        self.title = title
        self.width = width
        self.height = height
        self.chart = None
        self.df = None
        self.subcharts = {}
        self.indicators = {}
        
    def load_data(self, df: pd.DataFrame):
        """
        Load OHLCV data into chart.
        
        Args:
            df: DataFrame with columns: datetime/date, open, high, low, close, volume
        """
        self.df = df.copy()
        
        # Ensure datetime column
        if 'datetime' not in self.df.columns and 'date' in self.df.columns:
            self.df['datetime'] = self.df['date']
        elif self.df.index.name == 'datetime' or isinstance(self.df.index, pd.DatetimeIndex):
            self.df = self.df.reset_index()
            if 'index' in self.df.columns:
                self.df.rename(columns={'index': 'datetime'}, inplace=True)
        
        # Ensure lowercase columns
        self.df.columns = [c.lower() for c in self.df.columns]
        
        # Convert datetime to string format for lightweight-charts
        if 'datetime' in self.df.columns:
            self.df['time'] = pd.to_datetime(self.df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return self
    
    def add_trades(self, trades: List[Dict]):
        """
        Add trade entry/exit markers to chart.
        
        Args:
            trades: List of trade dictionaries with keys:
                - direction: 'long' or 'short'
                - entry_time: datetime string
                - entry_price: float
                - exit_time: datetime string (optional)
                - exit_price: float (optional)
                - pnl: float (optional)
        """
        self.trades = trades
        return self
    
    def add_sma(self, period: int = 20, color: str = '#2962FF', name: str = None):
        """Add Simple Moving Average line."""
        if self.df is None:
            return self
        
        name = name or f'SMA {period}'
        self.df[name] = self.df['close'].rolling(window=period).mean()
        self.indicators[name] = {'type': 'line', 'color': color, 'data': name}
        return self
    
    def add_ema(self, period: int = 20, color: str = '#FF6D00', name: str = None):
        """Add Exponential Moving Average line."""
        if self.df is None:
            return self
        
        name = name or f'EMA {period}'
        self.df[name] = self.df['close'].ewm(span=period, adjust=False).mean()
        self.indicators[name] = {'type': 'line', 'color': color, 'data': name}
        return self
    
    def add_supertrend(self, period: int = 10, multiplier: float = 3.0):
        """Add Supertrend indicator."""
        if self.df is None:
            return self
        
        # Calculate ATR
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Calculate Supertrend
        hl2 = (high + low) / 2
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=self.df.index, dtype=float)
        direction = pd.Series(index=self.df.index, dtype=int)
        
        for i in range(period, len(self.df)):
            if close.iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]
            
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]
        
        self.df['supertrend'] = supertrend
        self.df['supertrend_direction'] = direction
        
        self.indicators['Supertrend'] = {'type': 'supertrend', 'data': 'supertrend'}
        return self
    
    def add_rsi(self, period: int = 14):
        """Add RSI as subchart."""
        if self.df is None:
            return self
        
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        self.df['rsi'] = 100 - (100 / (1 + rs))
        
        self.subcharts['RSI'] = {'type': 'rsi', 'data': 'rsi', 'period': period}
        return self
    
    def show(self):
        """Display the chart in a new window."""
        if self.df is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Create main chart
        self.chart = Chart(toolbox=True, width=self.width, height=self.height)
        self.chart.watermark(self.title)
        self.chart.legend(True)
        
        # Set OHLCV data
        chart_data = self.df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
        self.chart.set(chart_data)
        
        # Add indicators
        for name, indicator in self.indicators.items():
            if indicator['type'] == 'line':
                line = self.chart.create_line(name, color=indicator['color'])
                line_data = self.df[['time', indicator['data']]].copy()
                line_data.columns = ['time', 'value']
                line_data = line_data.dropna()
                line.set(line_data)
            
            elif indicator['type'] == 'supertrend':
                try:
                    # Supertrend as single line (simplified approach)
                    st_data = self.df[['time', 'supertrend']].dropna().copy()
                    st_data.columns = ['time', 'value']
                    
                    if len(st_data) > 0:
                        st_line = self.chart.create_line('Supertrend', color='#FF9800')
                        st_line.set(st_data)
                except Exception as e:
                    print(f"Supertrend line error: {e}")
        
        # Add subcharts
        for name, subchart_config in self.subcharts.items():
            if subchart_config['type'] == 'rsi':
                try:
                    subchart = self.chart.create_subchart(position='bottom', height=0.15)
                    subchart.legend(True)
                
                    rsi_line = subchart.create_line(f'RSI({subchart_config["period"]})', color='#9C27B0')
                    rsi_data = self.df[['time', 'rsi']].dropna().copy()
                    rsi_data.columns = ['time', 'value']
                    rsi_line.set(rsi_data)
                except Exception as e:
                    print(f"RSI subchart error: {e}")
        
        # Add trade markers
        if hasattr(self, 'trades') and self.trades:
            for trade in self.trades:
                # Entry marker
                entry_time = trade.get('entry_time')
                entry_price = trade.get('entry_price')
                direction = trade.get('direction', 'long')
                pnl = trade.get('pnl', 0)
                
                if entry_time and entry_price:
                    # Convert datetime to string if needed
                    if isinstance(entry_time, datetime):
                        entry_time = entry_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Determine marker color based on PnL
                    is_winner = pnl > 0 if pnl else True
                    color = '#00d26a' if is_winner else '#ff4757'
                    
                    # Entry marker
                    self.chart.marker(
                        time=entry_time,
                        position='below' if direction == 'long' else 'above',
                        shape='arrow_up' if direction == 'long' else 'arrow_down',
                        color=color,
                        text=f"{direction.upper()} @ {entry_price:.2f}"
                    )
                
                # Exit marker
                exit_time = trade.get('exit_time')
                exit_price = trade.get('exit_price')
                
                if exit_time and exit_price:
                    if isinstance(exit_time, datetime):
                        exit_time = exit_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    pnl_text = f" (PnL: ${pnl:.2f})" if pnl else ""
                    self.chart.marker(
                        time=exit_time,
                        position='above' if direction == 'long' else 'below',
                        shape='circle',
                        color='#888888',
                        text=f"Exit @ {exit_price:.2f}{pnl_text}"
                    )
        
        # Show the chart
        self.chart.show(block=True)


def show_backtest_chart(
    ohlcv_df: pd.DataFrame,
    trades: List[Dict] = None,
    strategy_name: str = "Strategy",
    symbol: str = "",
    show_supertrend: bool = True,
    show_sma: bool = False,
    show_rsi: bool = True,
    indicators: List[str] = None,
    indicator_params: Dict = None,  # Indicator parameters (period, multiplier, etc.)
    metrics: Dict = None,  # P&L, Max DD, Win Rate etc.
    equity_curve: List = None,  # Equity curve data for bottom panel
    width: int = 1400,  # Window width (adjustable)
    height: int = 900   # Window height (adjustable)
):
    """
    Convenience function to show backtest results on TradingView-style chart.
    Uses subprocess to run independently of Streamlit.
    """
    import subprocess
    import json
    import tempfile
    import os
    from pathlib import Path
    
    # Prepare data for JSON
    title = f"{strategy_name} - {symbol}" if symbol else strategy_name
    
    # Convert DataFrame to dict - ensure all values are JSON serializable
    ohlcv_data = ohlcv_df.copy()
    
    # Convert all datetime columns to string
    for col in ohlcv_data.columns:
        if ohlcv_data[col].dtype == 'datetime64[ns]' or 'datetime' in col.lower():
            ohlcv_data[col] = ohlcv_data[col].astype(str)
    
    # Also check index if datetime
    if hasattr(ohlcv_data.index, 'strftime'):
        ohlcv_data = ohlcv_data.reset_index()
        if 'index' in ohlcv_data.columns:
            ohlcv_data = ohlcv_data.rename(columns={'index': 'datetime'})
        elif 'timestamp' in ohlcv_data.columns:
            ohlcv_data = ohlcv_data.rename(columns={'timestamp': 'datetime'})
        if 'datetime' in ohlcv_data.columns:
            ohlcv_data['datetime'] = ohlcv_data['datetime'].astype(str)
    
    # Format trades - ensure all values are JSON serializable
    formatted_trades = []
    for trade in (trades or []):
        t = {}
        for key, val in trade.items():
            if hasattr(val, 'isoformat'):  # Timestamp
                t[key] = val.isoformat()
            elif hasattr(val, 'strftime'):  # datetime
                t[key] = str(val)
            else:
                t[key] = val
        formatted_trades.append(t)
    
    # ONLY use indicators from the list - no automatic additions based on flags
    # Each strategy should explicitly define its own indicators
    strategy_indicators = indicators if indicators else []
    
    # Create data package
    data = {
        'ohlcv': ohlcv_data.to_dict('records'),
        'trades': formatted_trades,
        'title': title,
        'indicators': strategy_indicators,  # Only strategy-specific indicators
        'indicator_params': indicator_params or {},  # Custom indicator parameters
        'metrics': metrics or {},  # Performance metrics
        'equity_curve': equity_curve or [],  # Equity curve for bottom panel
        'width': width,  # Window width
        'height': height  # Window height
    }
    
    # Save to temp file
    temp_dir = Path(tempfile.gettempdir())
    data_file = temp_dir / f"chart_data_{os.getpid()}.json"
    
    with open(data_file, 'w') as f:
        json.dump(data, f, default=str)  # Use default=str as safety net
    
    # Get Python executable and chart viewer path
    python_exe = Path(__file__).parent.parent.parent / 'venv' / 'Scripts' / 'python.exe'
    if not python_exe.exists():
        python_exe = 'python'  # Fallback
    
    chart_viewer = Path(__file__).parent / 'chart_viewer.py'
    
    # Launch subprocess
    try:
        subprocess.Popen(
            [str(python_exe), str(chart_viewer), str(data_file)],
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        print(f"Chart viewer launched: {data_file}")
    except Exception as e:
        print(f"Failed to launch chart viewer: {e}")


# Export functions
__all__ = ['TradingViewChart', 'show_backtest_chart', 'CHARTS_AVAILABLE']
