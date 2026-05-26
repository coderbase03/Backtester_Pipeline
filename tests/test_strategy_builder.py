"""
Test - Strategy Builder Agent

Bu test dosyası:
1. StrategyBuilder ile dinamik strateji oluşturur
2. Backtest ile doğrular
3. Sonuçları raporlar
"""

import sys
import os
import pytest

pytest.skip("Legacy test suite: src.agents removed in May 2026 cleanup.", allow_module_level=True)

# Proje kök dizinini ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from src.agents import StrategyBuilder, StrategyConfig
from src.backtest import BacktestEngine


def test_strategy_builder():
    """Strategy Builder temel test"""
    print("=" * 60)
    print("TEST 1: Strategy Builder - Temel Fonksiyonellik")
    print("=" * 60)
    
    builder = StrategyBuilder()
    
    # Test config - SMA + RSI stratejisi
    config = StrategyConfig(
        name="Test_SMA_RSI_Strategy",
        indicators={
            'sma': {'period': 20},
            'rsi': {'period': 14},
        },
        entry_long="close > sma and rsi < 35",
        exit_long="rsi > 70",
        tp_levels=[2.0, 4.0, 6.0],  # %2, %4, %6
        tp_sizes=[0.4, 0.3, 0.3],   # %40, %30, %30
        sl_pct=2.0,
        instant_execution=True,
    )
    
    # Strateji oluştur
    print("\n1. Strateji oluşturuluyor...")
    strategy_class = builder.build(config)
    print(f"   ✓ Strateji sınıfı oluşturuldu: {strategy_class.__name__}")
    
    # Doğrula
    print("\n2. Strateji doğrulanıyor (backtest)...")
    validation = builder.validate(
        strategy_class,
        symbol="AAPL",
        source="yahoo",
        n_bars=300,
        instant_execution=True
    )
    
    print(f"\n   Doğrulama Sonuçları:")
    print(f"   - Valid: {validation['valid']}")
    print(f"   - Data OK: {validation['data_ok']}")
    print(f"   - Backtest OK: {validation['backtest_ok']}")
    print(f"   - Results OK: {validation['results_ok']}")
    
    if validation['error']:
        print(f"   - Error: {validation['error']}")
    
    if validation['result']:
        r = validation['result']
        print(f"\n   Backtest Sonuçları:")
        print(f"   - Final Value: ${r['final_value']:,.2f}")
        print(f"   - Total Return: {r['total_return']:.2f}%")
        print(f"   - Total Trades: {r['total_trades']}")
        print(f"   - Win Rate: {r['win_rate']:.1f}%")
        print(f"   - Sharpe Ratio: {r['sharpe_ratio']:.2f}")
        print(f"   - Max Drawdown: {r['max_drawdown_pct']:.2f}%")
    
    return validation['valid']


def test_instant_execution():
    """Instant Execution (Cheat-on-Close) testi"""
    print("\n" + "=" * 60)
    print("TEST 2: Instant Execution (Cheat-on-Close)")
    print("=" * 60)
    
    from src.strategies import SupertrendStrategy
    
    engine = BacktestEngine()
    
    # Instant execution = True (varsayılan)
    print("\n1. instant_execution=True ile backtest...")
    result1 = engine.run(
        strategy=SupertrendStrategy,
        symbol="AAPL",
        source="yahoo",
        n_bars=300,
        instant_execution=True
    )
    print(f"   Return: {result1['total_return']:.2f}%, Trades: {result1['total_trades']}")
    
    # Instant execution = False
    print("\n2. instant_execution=False ile backtest...")
    engine2 = BacktestEngine()
    result2 = engine2.run(
        strategy=SupertrendStrategy,
        symbol="AAPL",
        source="yahoo",
        n_bars=300,
        instant_execution=False
    )
    print(f"   Return: {result2['total_return']:.2f}%, Trades: {result2['total_trades']}")
    
    print(f"\n   Fark: {result1['total_return'] - result2['total_return']:.2f}% (instant vs normal)")
    
    return True


def test_multiple_tp_sl():
    """Multiple TP/SL testi"""
    print("\n" + "=" * 60)
    print("TEST 3: Multiple TP/SL Sistemi")
    print("=" * 60)
    
    builder = StrategyBuilder()
    
    # 3 kademeli TP config
    config = StrategyConfig(
        name="MultipleTP_Strategy",
        indicators={
            'sma': {'period': 20},
            'rsi': {'period': 14},
        },
        entry_long="close > sma and rsi < 40",
        tp_levels=[1.0, 2.0, 3.0],  # %1, %2, %3
        tp_sizes=[0.5, 0.3, 0.2],   # İlk %50, sonra %30, son %20
        sl_pct=1.5,
    )
    
    print("\n1. 3 kademeli TP stratejisi oluşturuluyor...")
    strategy = builder.build(config)
    
    print("\n2. Backtest çalıştırılıyor...")
    validation = builder.validate(strategy, symbol="AAPL", n_bars=300)
    
    if validation['result']:
        r = validation['result']
        print(f"\n   Sonuçlar:")
        print(f"   - Total Trades: {r['total_trades']}")
        print(f"   - Win Rate: {r['win_rate']:.1f}%")
        print(f"   - Return: {r['total_return']:.2f}%")
    
    return validation['valid']


def test_full_workflow():
    """Tam iş akışı testi - görselleştirme dahil"""
    print("\n" + "=" * 60)
    print("TEST 4: Tam İş Akışı (Görselleştirme Dahil)")
    print("=" * 60)
    
    from src.strategies import SupertrendStrategy
    from src.visualization.charts import BacktestChart
    import pandas as pd
    
    # Backtest çalıştır
    engine = BacktestEngine()
    result = engine.run(
        strategy=SupertrendStrategy,
        symbol="AAPL",
        source="yahoo",
        interval="1d",
        n_bars=200,
        instant_execution=True
    )
    
    print(f"\n1. Backtest tamamlandı:")
    print(f"   Return: {result['total_return']:.2f}%")
    print(f"   Trades: {result['total_trades']}")
    
    # Trade verileri al
    trades_df = engine.get_trades_df()
    print(f"\n2. Trade verisi alındı: {len(trades_df)} işlem")
    
    # Grafik oluştur
    if not trades_df.empty:
        # OHLCV verisi al (DataManager üzerinden)
        dm = engine.data_manager
        df = dm.get_data("AAPL", source="yahoo", interval="1d", n_bars=200)
        
        # Trade'leri dict listesine çevir
        trades_list = trades_df.to_dict('records') if not trades_df.empty else []
        
        chart = BacktestChart(
            ohlcv_df=df,
            trades=trades_list,
        )
        
        # HTML kaydet
        output_path = os.path.join(project_root, "reports", "test_chart.html")
        chart.save_html(output_path)
        print(f"\n3. Grafik kaydedildi: {output_path}")
    
    return True


def main():
    """Tüm testleri çalıştır"""
    print("\n" + "=" * 70)
    print("   STRATEGY BUILDER AGENT - TEST SUITE")
    print("=" * 70)
    
    results = {}
    
    try:
        results['strategy_builder'] = test_strategy_builder()
    except Exception as e:
        print(f"\n   ✗ TEST 1 FAILED: {e}")
        results['strategy_builder'] = False
    
    try:
        results['instant_execution'] = test_instant_execution()
    except Exception as e:
        print(f"\n   ✗ TEST 2 FAILED: {e}")
        results['instant_execution'] = False
    
    try:
        results['multiple_tp_sl'] = test_multiple_tp_sl()
    except Exception as e:
        print(f"\n   ✗ TEST 3 FAILED: {e}")
        results['multiple_tp_sl'] = False
    
    try:
        results['full_workflow'] = test_full_workflow()
    except Exception as e:
        print(f"\n   ✗ TEST 4 FAILED: {e}")
        results['full_workflow'] = False
    
    # Özet
    print("\n" + "=" * 70)
    print("   TEST SONUÇLARI")
    print("=" * 70)
    
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"   {name}: {status}")
    
    all_passed = all(results.values())
    print("\n" + "=" * 70)
    if all_passed:
        print("   TÜM TESTLER BAŞARILI! ✓")
    else:
        print("   BAZI TESTLER BAŞARISIZ! ✗")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
