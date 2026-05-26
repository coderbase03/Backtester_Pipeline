"""
Standalone chart viewer - runs as separate process.
Called by dashboard to show charts independently.
Supports multiple indicators with dropdown menu.
"""
import sys
import json
import pandas as pd
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tv_charts.indicators import (
    INDICATOR_DEFINITIONS,
    get_indicators_by_category,
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_supertrend,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_stochastic
)


class ChartViewer:
    """Interactive chart viewer with TradingView Strategy Report style support."""
    
    def __init__(self, title: str = "Backtest Results", width: int = 1400, height: int = 800):
        from lightweight_charts import Chart
        
        self.chart = Chart(toolbox=True, width=width, height=height)
        self.chart.watermark(title)
        self.chart.legend(True)
        self.title = title
        self.width = width
        self.height = height
        
        self.df = None
        self.active_indicators = {}
        self.indicators = {}  # For custom indicators
        self.subcharts = {}
        self.metrics = {}
        
    def load_data(self, ohlcv_df: pd.DataFrame):
        """Load OHLCV data into chart."""
        self.df = ohlcv_df.copy()
        
        # Prepare time column
        if 'datetime' in self.df.columns:
            self.df['time'] = pd.to_datetime(self.df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        elif 'timestamp' in self.df.columns:
            self.df['time'] = pd.to_datetime(self.df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        elif 'time' not in self.df.columns:
            self.df['time'] = self.df.index.strftime('%Y-%m-%d %H:%M:%S')
        
        # Set main chart data
        chart_data = self.df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
        self.chart.set(chart_data)
    
    def add_strategy_report(self, metrics: dict, equity_data: list = None):
        """
        Add TradingView-style Strategy Report panel with metrics and equity curve.
        Shows: P&L, Max DD, Total Trades, Win Rate, Profit Factor
        """
        self.metrics = metrics
        
        # Format metric values
        total_return = metrics.get('total_return', 0) or 0
        max_dd = metrics.get('max_drawdown_pct', metrics.get('max_drawdown', 0)) or 0
        total_trades = int(metrics.get('total_trades', 0) or 0)
        win_rate = metrics.get('win_rate', 0) or 0
        won_trades = int(metrics.get('won_trades', total_trades * win_rate / 100 if win_rate else 0))
        profit_factor = metrics.get('profit_factor', 0) or 0
        
        # Add metrics to TOPBAR (always works)
        try:
            pnl_text = f"P&L: {total_return:+.2f}%"
            dd_text = f"Max DD: {max_dd:.2f}%"
            trades_text = f"İşlemler: {total_trades}"
            win_text = f"Karlı: {win_rate:.1f}% ({won_trades}/{total_trades})"
            pf_text = f"PF: {profit_factor:.2f}"
            
            self.chart.topbar.textbox('pnl', pnl_text)
            self.chart.topbar.textbox('maxdd', dd_text)
            self.chart.topbar.textbox('trades', trades_text)
            self.chart.topbar.textbox('winrate', win_text)
            self.chart.topbar.textbox('pf', pf_text)
            
            print("✓ Metrics added to topbar")
        except Exception as e:
            print(f"✗ Topbar error: {e}")
        
        # Try to add TABLE as well (may not work in all versions)
        try:
            table = self.chart.create_table(
                width=1.0,
                height=0.10,
                headings=['Toplam K/Z', 'Maksimum DD', 'Toplam İşlem', 'Karlı İşlemler', 'Kar Faktörü'],
                widths=[0.2, 0.2, 0.2, 0.2, 0.2]
            )
            
            table.new_row(
                f"{total_return:+.2f}%",
                f"{max_dd:.2f}%",
                f"{total_trades}",
                f"{win_rate:.1f}% ({won_trades}/{total_trades})",
                f"{profit_factor:.2f}"
            )
            print("✓ Metrics table added")
        except Exception as e:
            print(f"✗ Table not supported: {e}")
        
        # === EQUITY CURVE SUBCHART (bottom panel) ===
        if equity_data and len(equity_data) > 0:
            self._add_balance_chart(equity_data)
    
    def _add_balance_chart(self, equity_data: list):
        """Add balance/equity chart at bottom (like TradingView's Bakiye grafiği)."""
        try:
            # Create subchart for equity/balance
            equity_subchart = self.chart.create_subchart(
                position='bottom', 
                width=1.0,
                height=0.25  # 25% of chart height
            )
            equity_subchart.legend(True)
            
            # Convert equity data
            eq_df = pd.DataFrame(equity_data)
            
            # Ensure time column exists
            if 'time' not in eq_df.columns:
                if 'datetime' in eq_df.columns:
                    eq_df['time'] = eq_df['datetime']
                elif 'timestamp' in eq_df.columns:
                    eq_df['time'] = eq_df['timestamp']
            
            # Calculate P&L from equity
            if 'value' in eq_df.columns:
                initial = eq_df['value'].iloc[0] if len(eq_df) > 0 else 100000
                eq_df['PnL'] = eq_df['value'] - initial
                
                # Create colored histogram (green for profit, red for loss)
                data = eq_df[['time', 'PnL']].copy()
                data = data.rename(columns={'PnL': 'Bakiye'})
                
                # Create line with fill
                equity_line = equity_subchart.create_line(
                    'Bakiye', 
                    color='#2962FF', 
                    width=2
                )
                equity_line.set(data)
                
            self.subcharts['equity'] = equity_subchart
            print("✓ Balance chart added (Bakiye grafiği)")
        except Exception as e:
            print(f"✗ Error adding balance chart: {e}")
    
    
    def add_metrics_topbar(self, metrics: dict):
        """Add performance metrics to topbar."""
        try:
            # Add key metrics as text buttons in topbar
            if 'total_return' in metrics:
                val = metrics['total_return']
                color = '#00d26a' if val >= 0 else '#ff4757'
                self.chart.topbar.textbox('pnl', f"P&L: {val:+.2f}%")
            
            if 'win_rate' in metrics:
                self.chart.topbar.textbox('winrate', f"Win: {metrics['win_rate']:.1f}%")
            
            if 'max_drawdown_pct' in metrics or 'max_drawdown' in metrics:
                dd = metrics.get('max_drawdown_pct', metrics.get('max_drawdown', 0))
                self.chart.topbar.textbox('maxdd', f"DD: {dd:.2f}%")
            
            if 'profit_factor' in metrics:
                self.chart.topbar.textbox('pf', f"PF: {metrics['profit_factor']:.2f}")
            
            if 'sharpe_ratio' in metrics:
                self.chart.topbar.textbox('sharpe', f"Sharpe: {metrics['sharpe_ratio']:.2f}")
            
            if 'total_trades' in metrics:
                self.chart.topbar.textbox('trades', f"Trades: {metrics['total_trades']}")
                
            print("✓ Metrics added to topbar")
        except Exception as e:
            print(f"✗ Error adding metrics: {e}")
    
    def add_equity_curve(self, equity_data: list):
        """Add equity curve as bottom subchart."""
        try:
            if not equity_data:
                return
                
            # Create subchart for equity curve
            equity_subchart = self.chart.create_subchart(position='bottom', height=0.2)
            equity_subchart.legend(True)
            
            # Convert equity data
            eq_df = pd.DataFrame(equity_data)
            
            # Ensure time column exists
            if 'time' not in eq_df.columns and 'datetime' in eq_df.columns:
                eq_df['time'] = eq_df['datetime']
            elif 'time' not in eq_df.columns and 'timestamp' in eq_df.columns:
                eq_df['time'] = eq_df['timestamp']
            
            # Calculate cumulative return if value column exists
            if 'value' in eq_df.columns:
                initial = eq_df['value'].iloc[0] if len(eq_df) > 0 else 1
                eq_df['Return'] = ((eq_df['value'] / initial) - 1) * 100
                data = eq_df[['time', 'Return']].copy()
                data = data.rename(columns={'Return': 'Equity'})
            else:
                # Assume it's already return data
                data = eq_df.copy()
            
            # Create line
            equity_line = equity_subchart.create_line('Equity', color='#2962FF', width=2)
            equity_line.set(data)
            
            self.subcharts['equity'] = equity_subchart
            print("✓ Equity curve added")
        except Exception as e:
            print(f"✗ Error adding equity curve: {e}")
    
    def setup_indicator_menu(self):
        """Setup indicator dropdown menu (TviewData style)."""
        # Build menu items
        items = ['--- Indicators ---']
        
        categories = get_indicators_by_category()
        for category in ['Trend', 'Momentum', 'Volatility']:
            if category in categories:
                items.append(f'--- {category} ---')
                for name in sorted(categories[category]):
                    status = '✓ ' if name in self.active_indicators else ''
                    items.append(f'{status}{name}')
        
        # Add menu to topbar
        self.chart.topbar.menu(
            'indicators_menu',
            tuple(items),
            default='--- Indicators ---',
            func=self.on_indicator_select
        )
        
    def on_indicator_select(self, chart_obj):
        """Handle indicator selection from menu."""
        selected = chart_obj.topbar['indicators_menu'].value
        
        # Skip category headers
        if selected.startswith('---') or not selected.strip():
            return
        
        # Parse selection (remove ✓ marker)
        indicator_name = selected.replace('✓ ', '').strip()
        
        if indicator_name in self.active_indicators:
            self.remove_indicator(indicator_name)
        else:
            self.add_indicator(indicator_name)
        
        # Update menu to show current state
        self.update_indicator_menu()
        
    def update_indicator_menu(self):
        """Refresh indicator menu to show active indicators."""
        items = ['--- Indicators ---']
        
        categories = get_indicators_by_category()
        for category in ['Trend', 'Momentum', 'Volatility']:
            if category in categories:
                items.append(f'--- {category} ---')
                for name in sorted(categories[category]):
                    status = '✓ ' if name in self.active_indicators else ''
                    items.append(f'{status}{name}')
        
        self.chart.topbar['indicators_menu'].update_items(*items)
        
    def add_indicator(self, name: str):
        """Add an indicator to the chart."""
        if name not in INDICATOR_DEFINITIONS or self.df is None:
            return
            
        definition = INDICATOR_DEFINITIONS[name]
        ind_type = definition['type']
        
        try:
            if ind_type == 'line':
                # Simple line on main chart
                data = definition['calc_func'](self.df, **definition['params'])
                # Rename 'value' column to match line name for lightweight-charts
                data = data.rename(columns={'value': name})
                line = self.chart.create_line(name, color=definition['color'], width=definition['width'])
                line.set(data)
                self.active_indicators[name] = {'type': 'line', 'object': line}
                
            elif ind_type == 'supertrend':
                # Supertrend with direction-based coloring (green=bullish, red=bearish)
                st_data, dir_data = definition['calc_func'](self.df, **definition['params'])
                
                # Merge supertrend value with direction
                merged = st_data.copy()
                merged['direction'] = dir_data['value'].values
                
                # Create bullish (green) data - where direction = 1
                bull_data = merged[merged['direction'] == 1].copy()
                bull_data = bull_data.rename(columns={'value': 'ST_Bull'})
                bull_data = bull_data[['time', 'ST_Bull']]
                
                # Create bearish (red) data - where direction = -1
                bear_data = merged[merged['direction'] == -1].copy()
                bear_data = bear_data.rename(columns={'value': 'ST_Bear'})
                bear_data = bear_data[['time', 'ST_Bear']]
                
                lines = []
                
                # Bullish line (green)
                if len(bull_data) > 0:
                    bull_line = self.chart.create_line('ST_Bull', color='#00d26a', width=definition['width'])
                    bull_line.set(bull_data)
                    lines.append(bull_line)
                
                # Bearish line (red)
                if len(bear_data) > 0:
                    bear_line = self.chart.create_line('ST_Bear', color='#ff4757', width=definition['width'])
                    bear_line.set(bear_data)
                    lines.append(bear_line)
                
                self.active_indicators[name] = {'type': 'multi_line', 'objects': lines}
                
            elif ind_type == 'multi_line':
                # Multiple lines (e.g., Bollinger Bands)
                data_tuple = definition['calc_func'](self.df, **definition['params'])
                colors = definition.get('colors', ['#2196F3', '#9E9E9E', '#2196F3'])
                lines = []
                for i, (data, color) in enumerate(zip(data_tuple, colors)):
                    line_name = f"{name}_{i}"
                    data = data.rename(columns={'value': line_name})
                    line = self.chart.create_line(line_name, color=color, width=definition['width'])
                    line.set(data)
                    lines.append(line)
                self.active_indicators[name] = {'type': 'multi_line', 'objects': lines}
                
            elif ind_type == 'subchart':
                # Subchart indicator (RSI, ATR)
                data = definition['calc_func'](self.df, **definition['params'])
                data = data.rename(columns={'value': name})
                subchart = self.chart.create_subchart(position='bottom', height=0.15)
                subchart.legend(True)
                line = subchart.create_line(name, color=definition['color'], width=definition['width'])
                line.set(data)
                self.active_indicators[name] = {'type': 'subchart', 'line': line, 'subchart': subchart}
                self.subcharts[name] = subchart
                
            elif ind_type == 'macd_subchart':
                # MACD subchart
                macd_data, signal_data, hist_data = definition['calc_func'](self.df, **definition['params'])
                macd_data = macd_data.rename(columns={'value': 'MACD'})
                signal_data = signal_data.rename(columns={'value': 'Signal'})
                hist_data = hist_data.rename(columns={'value': 'Histogram'})
                
                subchart = self.chart.create_subchart(position='bottom', height=0.15)
                subchart.legend(True)
                
                macd_line = subchart.create_line('MACD', color=definition['color_macd'])
                macd_line.set(macd_data)
                
                signal_line = subchart.create_line('Signal', color=definition['color_signal'])
                signal_line.set(signal_data)
                
                # Histogram as line (simplified)
                hist_line = subchart.create_line('Histogram', color=definition['color_histogram_pos'])
                hist_line.set(hist_data)
                
                self.active_indicators[name] = {
                    'type': 'macd_subchart',
                    'macd': macd_line,
                    'signal': signal_line,
                    'histogram': hist_line,
                    'subchart': subchart
                }
                self.subcharts[name] = subchart
                
            elif ind_type == 'stochastic_subchart':
                # Stochastic subchart
                k_data, d_data = definition['calc_func'](self.df, **definition['params'])
                k_data = k_data.rename(columns={'value': '%K'})
                d_data = d_data.rename(columns={'value': '%D'})
                
                subchart = self.chart.create_subchart(position='bottom', height=0.15)
                subchart.legend(True)
                
                k_line = subchart.create_line('%K', color=definition['color_k'])
                k_line.set(k_data)
                
                d_line = subchart.create_line('%D', color=definition['color_d'])
                d_line.set(d_data)
                
                self.active_indicators[name] = {
                    'type': 'stochastic_subchart',
                    'k': k_line,
                    'd': d_line,
                    'subchart': subchart
                }
                self.subcharts[name] = subchart
                
            print(f'✓ Added: {name}')
            
        except Exception as e:
            print(f'✗ Error adding {name}: {e}')
            import traceback
            traceback.print_exc()
            
    def remove_indicator(self, name: str):
        """Remove an indicator from the chart."""
        if name not in self.active_indicators:
            return
            
        try:
            indicator_data = self.active_indicators[name]
            ind_type = indicator_data['type']
            
            if ind_type == 'line':
                indicator_data['object'].delete()
                
            elif ind_type == 'multi_line':
                for line in indicator_data['objects']:
                    line.delete()
                    
            elif ind_type in ['subchart', 'macd_subchart', 'stochastic_subchart']:
                if name in self.subcharts:
                    del self.subcharts[name]
                # Note: lightweight-charts may not have subchart.delete()
                
            del self.active_indicators[name]
            print(f'✓ Removed: {name}')
            
        except Exception as e:
            print(f'✗ Error removing {name}: {e}')
            
    def add_trade_markers(self, trades: list):
        """Add trade entry/exit markers to chart."""
        for trade in trades:
            entry_time = trade.get('entry_time')
            entry_price = trade.get('entry_price')
            direction = trade.get('direction', 'long')
            pnl = trade.get('pnl', 0)
            
            if entry_time and entry_price:
                color = '#00d26a' if pnl > 0 else '#ff4757' if pnl < 0 else '#888888'
                self.chart.marker(
                    time=str(entry_time),
                    position='below' if direction == 'long' else 'above',
                    shape='arrow_up' if direction == 'long' else 'arrow_down',
                    color=color,
                    text=f"{direction.upper()} @ {entry_price:.2f}"
                )
            
            exit_time = trade.get('exit_time')
            exit_price = trade.get('exit_price')
            
            if exit_time and exit_price:
                pnl_text = f" (${pnl:+.2f})" if pnl else ""
                self.chart.marker(
                    time=str(exit_time),
                    position='above' if direction == 'long' else 'below',
                    shape='circle',
                    color='#888888',
                    text=f"Exit @ {exit_price:.2f}{pnl_text}"
                )
                
    def add_default_indicators(self, indicator_names: list, indicator_params: dict = None):
        """Add a list of indicators by name with custom parameters."""
        indicator_params = indicator_params or {}
        
        for name in indicator_names:
            name_lower = name.lower()
            params = indicator_params.get(name_lower, {})
            
            # Handle indicator with custom parameters
            if name_lower == 'supertrend':
                period = params.get('period', 10)
                multiplier = params.get('multiplier', 3.0)
                self._add_custom_supertrend(period, multiplier)
                
            elif name_lower in ['sma_fast', 'sma', 'sma_slow']:
                period = params.get('period', 20 if name_lower == 'sma' else (10 if name_lower == 'sma_fast' else 50))
                color = '#2196F3' if 'fast' in name_lower else '#FF9800'  # Blue for fast, orange for slow
                self._add_custom_sma(period, color, f"SMA {period}")
                
            elif name_lower == 'rsi':
                period = params.get('period', 14)
                oversold = params.get('oversold', 30)
                overbought = params.get('overbought', 70)
                self._add_custom_rsi(period, oversold, overbought)
                
            elif name_lower == 'ema':
                period = params.get('period', 21)
                self._add_custom_ema(period)
                
            # Fallback to standard indicators
            elif name in INDICATOR_DEFINITIONS:
                self.add_indicator(name)
            else:
                # Try case-insensitive match
                for key in INDICATOR_DEFINITIONS:
                    if name_lower in key.lower():
                        self.add_indicator(key)
                        break
    
    def _add_custom_supertrend(self, period: int, multiplier: float):
        """Add Supertrend with custom parameters."""
        try:
            # calculate_supertrend returns (supertrend_df, direction_df)
            st_result = calculate_supertrend(self.df, period=period, multiplier=multiplier)
            
            # It returns a tuple: (supertrend_df, direction_df)
            supertrend_df = st_result[0]  # time, value (supertrend line)
            direction_df = st_result[1]   # time, value (1=bullish, -1=bearish)
            
            # Create bullish and bearish data based on direction
            bull_data = []
            bear_data = []
            
            for i in range(len(supertrend_df)):
                time_val = supertrend_df.iloc[i]['time']
                st_val = supertrend_df.iloc[i]['value']
                direction = direction_df.iloc[i]['value'] if i < len(direction_df) else 0
                
                if direction == 1:  # Bullish
                    bull_data.append({'time': time_val, 'value': st_val})
                else:  # Bearish
                    bear_data.append({'time': time_val, 'value': st_val})
            
            # Bullish line (green)
            if bull_data:
                bull_df = pd.DataFrame(bull_data)
                bull_df = bull_df.rename(columns={'value': 'ST_Bull'})  # Column name must match line name
                bull_line = self.chart.create_line(
                    'ST_Bull', 
                    color='#00d26a', 
                    width=2
                )
                bull_line.set(bull_df)
                self.indicators['ST_Bull'] = bull_line
            
            # Bearish line (red)
            if bear_data:
                bear_df = pd.DataFrame(bear_data)
                bear_df = bear_df.rename(columns={'value': 'ST_Bear'})  # Column name must match line name
                bear_line = self.chart.create_line(
                    'ST_Bear', 
                    color='#ff4757', 
                    width=2
                )
                bear_line.set(bear_df)
                self.indicators['ST_Bear'] = bear_line
            
            print(f"✓ Added Supertrend (period={period}, mult={multiplier})")
        except Exception as e:
            print(f"✗ Supertrend error: {e}")
            import traceback
            traceback.print_exc()
    
    def _add_custom_sma(self, period: int, color: str, name: str = None):
        """Add SMA with custom period."""
        try:
            sma_data = calculate_sma(self.df, period=period)
            line_name = name or f'SMA {period}'
            
            # Rename 'value' column to match line_name (lightweight-charts requirement)
            sma_data = sma_data.rename(columns={'value': line_name})
            
            sma_line = self.chart.create_line(
                line_name,
                color=color,
                width=1.5
            )
            sma_line.set(sma_data)
            
            self.indicators[line_name] = sma_line
            print(f"✓ Added {line_name}")
        except Exception as e:
            print(f"✗ SMA error: {e}")
            import traceback
            traceback.print_exc()
    
    def _add_custom_ema(self, period: int):
        """Add EMA with custom period."""
        try:
            ema_data = calculate_ema(self.df, period=period)
            
            ema_line = self.chart.create_line(
                f'EMA {period}',
                color='#FFC107',
                width=1.5
            )
            ema_line.set(ema_data)
            
            self.indicators[f'EMA {period}'] = ema_line
            print(f"✓ Added EMA {period}")
        except Exception as e:
            print(f"✗ EMA error: {e}")
    
    def _add_custom_rsi(self, period: int, oversold: int, overbought: int):
        """Add RSI with custom parameters."""
        try:
            rsi_data = calculate_rsi(self.df, period=period)
            
            # Create subchart for RSI
            rsi_chart = self.chart.create_subchart(position='bottom', width=1.0, height=0.15)
            rsi_chart.legend(True)
            
            # RSI line
            rsi_line = rsi_chart.create_line(f'RSI {period}', color='#9C27B0', width=1.5)
            rsi_line.set(rsi_data)
            
            # Horizontal levels
            rsi_chart.horizontal_line(overbought, color='#ff4757', line_style='dashed')
            rsi_chart.horizontal_line(oversold, color='#00d26a', line_style='dashed')
            
            self.subcharts[f'RSI {period}'] = rsi_chart
            print(f"✓ Added RSI (period={period}, OS={oversold}, OB={overbought})")
        except Exception as e:
            print(f"✗ RSI error: {e}")
                
    def show(self):
        """Display the chart."""
        self.chart.show(block=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python chart_viewer.py <data_file.json>")
        sys.exit(1)
    
    data_file = sys.argv[1]
    
    # Load data from JSON file
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # Convert to DataFrame
    ohlcv_df = pd.DataFrame(data['ohlcv'])
    trades = data.get('trades', [])
    title = data.get('title', 'Backtest Chart')
    default_indicators = data.get('indicators', [])
    indicator_params = data.get('indicator_params', {})  # Custom parameters
    metrics = data.get('metrics', {})
    equity_curve = data.get('equity_curve', [])
    
    # Get window size preferences (default: 1400x900)
    width = data.get('width', 1400)
    height = data.get('height', 900)
    
    print(f"Opening chart: {title}")
    print(f"Window size: {width}x{height}")
    print(f"Bars: {len(ohlcv_df)}")
    print(f"Trades: {len(trades)}")
    print(f"Default indicators: {default_indicators}")
    print(f"Indicator params: {indicator_params}")
    print(f"Has metrics: {bool(metrics)}")
    print(f"Has equity curve: {len(equity_curve)} points")
    
    # Create chart with specified dimensions
    viewer = ChartViewer(title=title, width=width, height=height)
    viewer.load_data(ohlcv_df)
    
    # Add Strategy Report panel (TradingView style) - metrics table + equity curve
    if metrics:
        viewer.add_strategy_report(metrics, equity_curve)
    
    # Setup indicator menu
    viewer.setup_indicator_menu()
    
    # Add default indicators with custom parameters
    if default_indicators:
        viewer.add_default_indicators(default_indicators, indicator_params)
    
    # Add trade markers
    if trades:
        viewer.add_trade_markers(trades)
    
    print("Chart window opened. Use the dropdown menu to add indicators.")
    viewer.show()
    print("Chart closed.")


if __name__ == '__main__':
    main()
