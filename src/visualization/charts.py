"""
Interactive Charts with Plotly

Provides candlestick charts, equity curves, and trade visualizations.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List, Any, Optional
import json


class BacktestChart:
    """
    Interactive charts for backtest visualization.
    
    Usage:
        chart = BacktestChart(df, trades_df, equity_df)
        chart.show()
        chart.save_html('report.html')
    """
    
    def __init__(
        self,
        ohlcv_df: pd.DataFrame,
        trades: List[Dict] = None,
        equity_curve: List[Dict] = None,
        indicators: Dict[str, pd.Series] = None
    ):
        """
        Initialize chart with data.
        
        Args:
            ohlcv_df: OHLCV DataFrame with datetime index
            trades: List of trade dicts with entry/exit info
            equity_curve: List of equity snapshots
            indicators: Dict of indicator name -> series
        """
        self.df = ohlcv_df.copy()
        self.trades = trades or []
        self.equity_curve = equity_curve or []
        self.indicators = indicators or {}
        
    def create_candlestick_chart(
        self,
        show_volume: bool = True,
        show_trades: bool = True,
        show_tp_sl: bool = True,
        height: int = 800,
        title: str = "Backtest Results"
    ) -> go.Figure:
        """
        Create interactive candlestick chart.
        
        Args:
            show_volume: Include volume subplot
            show_trades: Show trade entry/exit markers
            height: Chart height in pixels
            title: Chart title
            
        Returns:
            Plotly Figure object
        """
        # Determine subplot layout
        rows = 2 if show_volume else 1
        row_heights = [0.7, 0.3] if show_volume else [1.0]
        
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
            subplot_titles=[title, 'Volume'] if show_volume else [title]
        )
        
        # ======== CANDLESTICK ========
        fig.add_trace(
            go.Candlestick(
                x=self.df.index,
                open=self.df['open'],
                high=self.df['high'],
                low=self.df['low'],
                close=self.df['close'],
                name='Price',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350',
            ),
            row=1, col=1
        )
        
        # ======== INDICATORS ========
        colors = ['#2196F3', '#FF9800', '#9C27B0', '#00BCD4', '#795548']
        for i, (name, series) in enumerate(self.indicators.items()):
            fig.add_trace(
                go.Scatter(
                    x=series.index,
                    y=series,
                    name=name,
                    line=dict(color=colors[i % len(colors)], width=1.5),
                ),
                row=1, col=1
            )
        
        # ======== TRADE MARKERS ========
        if show_trades and self.trades:
            # Entry markers
            entries_long = [t for t in self.trades if t.get('direction') == 'LONG']
            entries_short = [t for t in self.trades if t.get('direction') == 'SHORT']
            
            if entries_long:
                fig.add_trace(
                    go.Scatter(
                        x=[pd.to_datetime(t['entry_time']) for t in entries_long],
                        y=[t['entry_price'] for t in entries_long],
                        mode='markers',
                        name='Long Entry',
                        marker=dict(
                            symbol='triangle-up',
                            size=12,
                            color='#26a69a',
                            line=dict(color='white', width=1)
                        ),
                    ),
                    row=1, col=1
                )
            
            if entries_short:
                fig.add_trace(
                    go.Scatter(
                        x=[pd.to_datetime(t['entry_time']) for t in entries_short],
                        y=[t['entry_price'] for t in entries_short],
                        mode='markers',
                        name='Short Entry',
                        marker=dict(
                            symbol='triangle-down',
                            size=12,
                            color='#ef5350',
                            line=dict(color='white', width=1)
                        ),
                    ),
                    row=1, col=1
                )
            
            # Exit markers (all trades)
            fig.add_trace(
                go.Scatter(
                    x=[pd.to_datetime(t['exit_time']) for t in self.trades],
                    y=[t['exit_price'] for t in self.trades],
                    mode='markers',
                    name='Exit',
                    marker=dict(
                        symbol='x',
                        size=10,
                        color='#FFC107',
                        line=dict(width=2)
                    ),
                ),
                row=1, col=1
            )
            
            # ======== TP/SL LEVELS ========
            if show_tp_sl:
                for trade in self.trades:
                    entry_time = pd.to_datetime(trade.get('entry_time'))
                    exit_time = pd.to_datetime(trade.get('exit_time'))
                    entry_price = trade.get('entry_price', 0)
                    
                    # SL line (kırmızı)
                    sl_price = trade.get('sl_price')
                    if sl_price:
                        fig.add_shape(
                            type='line',
                            x0=entry_time, x1=exit_time,
                            y0=sl_price, y1=sl_price,
                            line=dict(color='#ef5350', width=1, dash='dash'),
                            row=1, col=1
                        )
                    
                    # TP lines (yeşil tonları)
                    tp_prices = trade.get('tp_prices', [])
                    if isinstance(tp_prices, (list, tuple)):
                        tp_colors = ['#26a69a', '#66bb6a', '#a5d6a7']
                        for i, tp_price in enumerate(tp_prices[:3]):
                            fig.add_shape(
                                type='line',
                                x0=entry_time, x1=exit_time,
                                y0=tp_price, y1=tp_price,
                                line=dict(color=tp_colors[i % len(tp_colors)], width=1, dash='dot'),
                                row=1, col=1
                            )
        
        # ======== VOLUME ========
        if show_volume:
            colors = ['#26a69a' if c >= o else '#ef5350' 
                     for o, c in zip(self.df['open'], self.df['close'])]
            
            fig.add_trace(
                go.Bar(
                    x=self.df.index,
                    y=self.df['volume'],
                    name='Volume',
                    marker_color=colors,
                    opacity=0.7,
                ),
                row=2, col=1
            )
        
        # ======== LAYOUT ========
        fig.update_layout(
            height=height,
            template='plotly_dark',
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
        
        return fig
    
    def create_equity_chart(
        self,
        height: int = 400,
        show_drawdown: bool = True
    ) -> go.Figure:
        """
        Create equity curve chart with optional drawdown.
        
        Args:
            height: Chart height
            show_drawdown: Show drawdown as fill area
            
        Returns:
            Plotly Figure object
        """
        if not self.equity_curve:
            return go.Figure()
        
        eq_df = pd.DataFrame(self.equity_curve)
        eq_df['datetime'] = pd.to_datetime(eq_df['datetime'])
        eq_df.set_index('datetime', inplace=True)
        
        rows = 2 if show_drawdown else 1
        row_heights = [0.7, 0.3] if show_drawdown else [1.0]
        
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=row_heights,
            subplot_titles=['Equity Curve', 'Drawdown (%)'] if show_drawdown else ['Equity Curve']
        )
        
        # Equity curve
        fig.add_trace(
            go.Scatter(
                x=eq_df.index,
                y=eq_df['equity'],
                name='Equity',
                line=dict(color='#2196F3', width=2),
                fill='tozeroy',
                fillcolor='rgba(33, 150, 243, 0.1)',
            ),
            row=1, col=1
        )
        
        # Drawdown
        if show_drawdown:
            peak = eq_df['equity'].cummax()
            drawdown = (eq_df['equity'] - peak) / peak * 100
            
            fig.add_trace(
                go.Scatter(
                    x=eq_df.index,
                    y=drawdown,
                    name='Drawdown',
                    line=dict(color='#ef5350', width=1),
                    fill='tozeroy',
                    fillcolor='rgba(239, 83, 80, 0.3)',
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            height=height,
            template='plotly_dark',
            showlegend=True,
            hovermode='x unified',
        )
        
        return fig
    
    def create_trade_analysis(self) -> go.Figure:
        """Create trade PnL distribution chart."""
        if not self.trades:
            return go.Figure()
        
        pnls = [t['pnl'] for t in self.trades]
        colors = ['#26a69a' if p > 0 else '#ef5350' for p in pnls]
        
        fig = go.Figure()
        
        fig.add_trace(
            go.Bar(
                x=list(range(1, len(pnls) + 1)),
                y=pnls,
                marker_color=colors,
                name='Trade PnL',
            )
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
        
        fig.update_layout(
            title='Trade PnL Distribution',
            xaxis_title='Trade #',
            yaxis_title='PnL ($)',
            height=400,
            template='plotly_dark',
        )
        
        return fig
    
    def show(self, chart_type: str = 'candlestick'):
        """Display chart in browser."""
        if chart_type == 'candlestick':
            fig = self.create_candlestick_chart()
        elif chart_type == 'equity':
            fig = self.create_equity_chart()
        elif chart_type == 'trades':
            fig = self.create_trade_analysis()
        else:
            raise ValueError(f"Unknown chart type: {chart_type}")
        
        fig.show()
    
    def save_html(self, filepath: str, include_all: bool = True):
        """
        Save charts to HTML file.
        
        Args:
            filepath: Output file path
            include_all: Include all chart types in one file
        """
        if include_all:
            from plotly.subplots import make_subplots
            
            fig1 = self.create_candlestick_chart()
            fig2 = self.create_equity_chart()
            fig3 = self.create_trade_analysis()
            
            # Combine figures
            with open(filepath, 'w') as f:
                f.write('<html><head><title>Backtest Report</title></head><body>')
                f.write(fig1.to_html(full_html=False, include_plotlyjs='cdn'))
                f.write(fig2.to_html(full_html=False, include_plotlyjs=False))
                f.write(fig3.to_html(full_html=False, include_plotlyjs=False))
                f.write('</body></html>')
        else:
            fig = self.create_candlestick_chart()
            fig.write_html(filepath)
