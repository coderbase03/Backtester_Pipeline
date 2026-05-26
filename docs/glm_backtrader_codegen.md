# GLM 4.7 Backtrader Strategy Codegen Guide

Bu dosya, strategy fikirlerinin GLM-4.7 ile Backtrader koduna dönüştürülmesi için referans kuralları içerir.

## Amaç
- Reddit/GitHub gibi kaynaklardan çıkan strategy fikirlerini
- çalıştırılabilir `BaseStrategy` türevi Python koduna çevirmek.

## Zorunlu Kod Kuralları
1. `import backtrader as bt`
2. `from src.strategies.base import BaseStrategy`
3. Sınıf `BaseStrategy`'den türemeli
4. `params` içinde en az:
   - `tp_pct`
   - `sl_pct`
   - `risk_pct`
   - `use_bracket`
5. `__init__` ve `next` metodları zorunlu
6. Belirsiz rule varsa fail-safe mantık kullanılmalı (`entry_signal=False` vb.)

## Prompt Input Alanları
- strategy_name
- summary
- entry_rules
- exit_rules
- indicators
- tp_pct
- sl_pct
- source_url

## Çıktı Kalite Kapısı
- Syntax compile geçmeli
- BaseStrategy inheritance kontrolü
- `params` tanımı mevcut
- next() içinde order/position kontrolü var

## Örnek Dönüşüm Şablonu
- Entry: indikatör koşulu + opsiyonel ek filtre
- Exit: TP/SL ya da sinyal bazlı close
- Bracket: mümkünse `buy_with_bracket()` / `sell_with_bracket()`

## Not
- Opsiyon-spesifik stratejilerde (iron condor vb.) backtest aşaması OHLCV proxy modunda çalıştırılır.
- Bu nedenle raporda `backtest_mode=proxy` ve `proxy_reason` alanları zorunludur.
