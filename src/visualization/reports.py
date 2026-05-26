"""
Report Generation

Generate PDF and Excel reports from backtest results.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import json


def generate_report(
    results: Dict[str, Any],
    trades: List[Dict] = None,
    equity_curve: List[Dict] = None,
    output_path: str = None,
    format: str = 'excel'
) -> str:
    """
    Generate backtest report.
    
    Args:
        results: Backtest results dict from engine
        trades: List of trade dicts
        equity_curve: Equity snapshots
        output_path: Output file path (auto-generated if None)
        format: 'excel' or 'json'
        
    Returns:
        Path to generated report
    """
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        strategy = results.get('strategy', 'unknown')
        symbol = results.get('symbol', 'unknown')
        
        Path('reports').mkdir(exist_ok=True)
        
        if format == 'excel':
            output_path = f"reports/{strategy}_{symbol}_{timestamp}.xlsx"
        else:
            output_path = f"reports/{strategy}_{symbol}_{timestamp}.json"
    
    if format == 'excel':
        return _generate_excel_report(results, trades, equity_curve, output_path)
    else:
        return _generate_json_report(results, trades, equity_curve, output_path)


def _generate_excel_report(
    results: Dict[str, Any],
    trades: List[Dict],
    equity_curve: List[Dict],
    output_path: str
) -> str:
    """Generate Excel report with multiple sheets."""
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = {
            'Metric': [
                'Strategy',
                'Symbol',
                'Period',
                'Initial Capital',
                'Final Value',
                'Total Return (%)',
                'Sharpe Ratio',
                'Max Drawdown (%)',
                'Total Trades',
                'Win Rate (%)',
                'Profit Factor',
                'SQN',
            ],
            'Value': [
                results.get('strategy', ''),
                results.get('symbol', ''),
                f"{results.get('start_date', '')} to {results.get('end_date', '')}",
                f"${results.get('initial_cash', 0):,.2f}",
                f"${results.get('final_value', 0):,.2f}",
                f"{results.get('total_return', 0):.2f}%",
                f"{results.get('sharpe_ratio', 0):.2f}",
                f"{results.get('max_drawdown_pct', 0):.2f}%",
                results.get('total_trades', 0),
                f"{results.get('win_rate', 0):.1f}%",
                f"{results.get('profit_factor', 0):.2f}",
                f"{results.get('sqn', 0):.2f}",
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
        
        # Trades sheet
        if trades:
            trades_df = pd.DataFrame(trades)
            trades_df.to_excel(writer, sheet_name='Trades', index=False)
        
        # Equity curve sheet
        if equity_curve:
            equity_df = pd.DataFrame(equity_curve)
            equity_df.to_excel(writer, sheet_name='Equity', index=False)
        
        # Parameters sheet
        if results.get('parameters'):
            params_df = pd.DataFrame([
                {'Parameter': k, 'Value': v}
                for k, v in results['parameters'].items()
            ])
            params_df.to_excel(writer, sheet_name='Parameters', index=False)
    
    return output_path


def _generate_json_report(
    results: Dict[str, Any],
    trades: List[Dict],
    equity_curve: List[Dict],
    output_path: str
) -> str:
    """Generate JSON report."""
    
    report = {
        'summary': results,
        'trades': trades or [],
        'equity_curve': equity_curve or [],
        'generated_at': datetime.now().isoformat(),
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    return output_path


def print_summary(results: Dict[str, Any]):
    """Print formatted summary to console."""
    
    print("\n" + "="*60)
    print(f"  BACKTEST RESULTS: {results.get('strategy', 'Unknown')}")
    print("="*60)
    print(f"  Symbol:           {results.get('symbol', '')}")
    print(f"  Period:           {results.get('start_date', '')} to {results.get('end_date', '')}")
    print("-"*60)
    print(f"  Initial Capital:  ${results.get('initial_cash', 0):,.2f}")
    print(f"  Final Value:      ${results.get('final_value', 0):,.2f}")
    print(f"  Total Return:     {results.get('total_return', 0):+.2f}%")
    print("-"*60)
    print(f"  Sharpe Ratio:     {results.get('sharpe_ratio', 0):.2f}")
    print(f"  Max Drawdown:     {results.get('max_drawdown_pct', 0):.2f}%")
    print(f"  SQN:              {results.get('sqn', 0):.2f}")
    print("-"*60)
    print(f"  Total Trades:     {results.get('total_trades', 0)}")
    print(f"  Win Rate:         {results.get('win_rate', 0):.1f}%")
    print(f"  Profit Factor:    {results.get('profit_factor', 0):.2f}")
    print(f"  Avg Trade:        ${results.get('avg_trade', 0):.2f}")
    print("="*60 + "\n")
