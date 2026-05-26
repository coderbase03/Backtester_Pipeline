#!/usr/bin/env python
"""
Opus Backtrader - Akıllı Veri İndirme Script
=============================================

TradingView'dan veri indirmek için terminal aracı.
Incremental update: Sadece eksik barları indirir, mevcut verilerle birleştirir.

Kullanım:
    python download_data.py                     # İnteraktif menü
    python download_data.py BTCUSDT             # Tek sembol (incremental)
    python download_data.py BTCUSDT 4h 1000     # Sembol, timeframe, bar sayısı
    python download_data.py --crypto            # Tüm kripto
    python download_data.py --stocks            # Tüm hisseler
    python download_data.py --forex             # Tüm forex/emtia
    python download_data.py --update            # Tüm mevcut verileri güncelle
"""

import sys
import os
from datetime import datetime, timedelta

# Project root'a path ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tvDatafeed import TvDatafeed, Interval
import pandas as pd


# ============================
# CONFIGURATION
# ============================
DATA_DIR = os.path.join(os.path.dirname(__file__), 'src', 'tviewdata', 'shared_data', 'processed')

TIMEFRAME_MAP = {
    '1m': Interval.in_1_minute,
    '3m': Interval.in_3_minute,
    '5m': Interval.in_5_minute,
    '15m': Interval.in_15_minute,
    '30m': Interval.in_30_minute,
    '1h': Interval.in_1_hour,
    '2h': Interval.in_2_hour,
    '4h': Interval.in_4_hour,
    '1d': Interval.in_daily,
    '1w': Interval.in_weekly,
    '1M': Interval.in_monthly,
}

TIMEFRAME_NAMES = {
    '1m': '1min', '3m': '3min', '5m': '5min', '15m': '15min',
    '30m': '30min', '1h': '1hour', '2h': '2hour', '4h': '4hour',
    '1d': 'daily', '1w': 'weekly', '1M': 'monthly'
}

# Minutes per timeframe (for calculating missing bars)
TIMEFRAME_MINUTES = {
    '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
    '1h': 60, '2h': 120, '4h': 240, '1d': 1440, '1w': 10080, '1M': 43200
}

# ============================
# PRESET LISTS
# ============================
CRYPTO = [
    ('BTCUSDT', 'BINANCE'), ('ETHUSDT', 'BINANCE'), ('BNBUSDT', 'BINANCE'),
    ('SOLUSDT', 'BINANCE'), ('XRPUSDT', 'BINANCE'), ('ADAUSDT', 'BINANCE'),
    ('DOGEUSDT', 'BINANCE'), ('AVAXUSDT', 'BINANCE'), ('LINKUSDT', 'BINANCE'),
    ('DOTUSDT', 'BINANCE'), ('ATOMUSDT', 'BINANCE'), ('LTCUSDT', 'BINANCE'),
]

STOCKS = [
    ('AAPL', 'NASDAQ'), ('MSFT', 'NASDAQ'), ('GOOGL', 'NASDAQ'),
    ('AMZN', 'NASDAQ'), ('NVDA', 'NASDAQ'), ('TSLA', 'NASDAQ'),
    ('META', 'NASDAQ'), ('NFLX', 'NASDAQ'), ('AMD', 'NASDAQ'),
]

FOREX = [
    ('EURUSD', 'OANDA'), ('GBPUSD', 'OANDA'), ('USDJPY', 'OANDA'),
    ('AUDUSD', 'OANDA'), ('USDCAD', 'OANDA'), ('XAUUSD', 'OANDA'),
    ('XAGUSD', 'OANDA'), ('USOIL', 'TVC'), ('UKOIL', 'TVC'),
]

BIST = [
    ('THYAO', 'BIST'), ('GARAN', 'BIST'), ('ASELS', 'BIST'),
    ('EREGL', 'BIST'), ('KCHOL', 'BIST'),
]


def get_existing_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Mevcut CSV dosyasını oku."""
    tf_name = TIMEFRAME_NAMES.get(timeframe, timeframe)
    filepath = os.path.join(DATA_DIR, f"{symbol}_{tf_name}.csv")
    
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            # datetime sütununu parse et
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
            elif 'date' in df.columns:
                df['datetime'] = pd.to_datetime(df['date'])
                df.drop('date', axis=1, inplace=True)
            return df
        except Exception as e:
            print(f"  ⚠️ Dosya okunamadı: {e}")
    return pd.DataFrame()


def calculate_missing_bars(existing_df: pd.DataFrame, timeframe: str) -> int:
    """Eksik bar sayısını hesapla."""
    if existing_df.empty:
        return 5000  # Dosya yoksa maksimum indir
    
    # Son bar tarihini al
    if 'datetime' in existing_df.columns:
        last_date = pd.to_datetime(existing_df['datetime'].max())
    else:
        return 5000
    
    # Şu anki zaman
    now = datetime.now()
    
    # Fark hesapla (dakika cinsinden)
    diff_minutes = (now - last_date).total_seconds() / 60
    
    # Timeframe başına bar sayısı
    minutes_per_bar = TIMEFRAME_MINUTES.get(timeframe, 240)
    missing_bars = int(diff_minutes / minutes_per_bar) + 10  # 10 bar fazla al (güvenlik payı)
    
    # Min 50, Max 5000
    missing_bars = max(50, min(5000, missing_bars))
    
    return missing_bars


def merge_and_deduplicate(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Eski ve yeni verileri birleştir, duplicate'ları temizle."""
    if existing_df.empty:
        return new_df
    
    if new_df.empty:
        return existing_df
    
    # Sütun isimlerini normalize et
    for df in [existing_df, new_df]:
        if 'date' in df.columns and 'datetime' not in df.columns:
            df.rename(columns={'date': 'datetime'}, inplace=True)
    
    # datetime'ı parse et
    existing_df['datetime'] = pd.to_datetime(existing_df['datetime'])
    new_df['datetime'] = pd.to_datetime(new_df['datetime'])
    
    # Birleştir
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    
    # Duplicate'ları kaldır (datetime'a göre, son olanı tut)
    combined = combined.drop_duplicates(subset=['datetime'], keep='last')
    
    # Tarihe göre sırala
    combined = combined.sort_values('datetime').reset_index(drop=True)
    
    return combined


def download_symbol(symbol: str, exchange: str, interval: str = '4h', 
                    n_bars: int = None, tv=None, force_full: bool = False):
    """
    Tek sembol indir (incremental update destekli).
    
    Args:
        symbol: Sembol adı
        exchange: Exchange adı
        interval: Timeframe
        n_bars: Bar sayısı (None = otomatik hesapla)
        tv: TvDatafeed instance
        force_full: True ise mevcut veriyi yok say, komple indir
    """
    if tv is None:
        tv = TvDatafeed()
    
    # Interval mapping
    interval_obj = TIMEFRAME_MAP.get(interval)
    if not interval_obj:
        print(f"❌ Geçersiz timeframe: {interval}")
        print(f"   Geçerli: {', '.join(TIMEFRAME_MAP.keys())}")
        return None
    
    # Mevcut veriyi oku
    existing_df = pd.DataFrame() if force_full else get_existing_data(symbol, interval)
    
    # Bar sayısını belirle
    if n_bars is None:
        n_bars = calculate_missing_bars(existing_df, interval)
    
    # Bilgi mesajı
    if not existing_df.empty:
        last_date = existing_df['datetime'].max()
        print(f"\n📥 Güncelleniyor: {symbol} ({exchange}) - {interval}")
        print(f"   📅 Mevcut: {len(existing_df)} bar, son: {last_date}")
        print(f"   🔄 İndirilecek: ~{n_bars} yeni bar")
    else:
        print(f"\n📥 İndiriliyor: {symbol} ({exchange}) - {interval} ({n_bars} bar)")
    
    try:
        # Veri indir
        df = tv.get_hist(
            symbol=symbol,
            exchange=exchange,
            interval=interval_obj,
            n_bars=n_bars
        )
        
        if df is None or df.empty:
            print(f"  ❌ Veri boş!")
            return None
        
        # Reset index
        df.reset_index(inplace=True)
        if 'symbol' in df.columns:
            df.drop('symbol', axis=1, inplace=True)
        
        # Sütun isimlerini normalize et
        if 'date' in df.columns:
            df.rename(columns={'date': 'datetime'}, inplace=True)
        
        # Mevcut veriyle birleştir
        merged_df = merge_and_deduplicate(existing_df, df)
        
        # Kaydet
        tf_name = TIMEFRAME_NAMES.get(interval, interval)
        os.makedirs(DATA_DIR, exist_ok=True)
        filepath = os.path.join(DATA_DIR, f"{symbol}_{tf_name}.csv")
        merged_df.to_csv(filepath, index=False)
        
        # Sonuç mesajı
        new_bars = len(merged_df) - len(existing_df)
        print(f"  ✅ +{new_bars} yeni bar eklendi")
        print(f"  📊 Toplam: {len(merged_df)} bar")
        print(f"  📅 Aralık: {merged_df['datetime'].min()} → {merged_df['datetime'].max()}")
        
        return merged_df
        
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        return None


def download_preset(preset_name: str, interval: str = '4h', force_full: bool = False):
    """Preset listesini indir (incremental)."""
    presets = {
        'crypto': CRYPTO,
        'stocks': STOCKS,
        'forex': FOREX,
        'bist': BIST,
    }
    
    pairs = presets.get(preset_name)
    if not pairs:
        print(f"❌ Geçersiz preset: {preset_name}")
        print(f"   Geçerli: {', '.join(presets.keys())}")
        return
    
    print(f"\n{'='*60}")
    print(f"📦 {preset_name.upper()} {'İNDİRME' if force_full else 'GÜNCELLEME'} BAŞLIYOR")
    print(f"{'='*60}")
    print(f"Sembol sayısı: {len(pairs)}")
    print(f"Timeframe: {interval}")
    print(f"Mod: {'Tam indirme' if force_full else 'Incremental (eksik barlar)'}")
    print()
    
    tv = TvDatafeed()
    success = 0
    total_new_bars = 0
    
    for symbol, exchange in pairs:
        df = download_symbol(symbol, exchange, interval, tv=tv, force_full=force_full)
        if df is not None:
            success += 1
    
    print(f"\n{'='*60}")
    print(f"✅ TAMAMLANDI: {success}/{len(pairs)} başarılı")
    print(f"{'='*60}")


def update_all_existing():
    """Tüm mevcut verileri güncelle."""
    print(f"\n{'='*60}")
    print("🔄 TÜM VERİLER GÜNCELLENİYOR")
    print(f"{'='*60}")
    
    if not os.path.exists(DATA_DIR):
        print("❌ Veri klasörü bulunamadı!")
        return
    
    # Tüm CSV dosyalarını tara
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
    print(f"📁 {len(files)} dosya bulundu\n")
    
    tv = TvDatafeed()
    success = 0
    
    for filename in files:
        # Dosya adını parse et: SYMBOL_TIMEFRAME.csv
        parts = filename.replace('.csv', '').rsplit('_', 1)
        if len(parts) != 2:
            continue
        
        symbol = parts[0]
        tf_name = parts[1]
        
        # Timeframe'i normalize et
        tf_reverse = {v: k for k, v in TIMEFRAME_NAMES.items()}
        interval = tf_reverse.get(tf_name, tf_name)
        
        # Exchange tahmin et
        if symbol.endswith('USDT'):
            exchange = 'BINANCE'
        elif len(symbol) == 6 and 'USD' in symbol:
            exchange = 'OANDA'
        elif symbol in ['USOIL', 'UKOIL', 'GOLD', 'SILVER']:
            exchange = 'TVC'
        else:
            exchange = 'NASDAQ'
        
        df = download_symbol(symbol, exchange, interval, tv=tv)
        if df is not None:
            success += 1
    
    print(f"\n{'='*60}")
    print(f"✅ GÜNCELLEME TAMAMLANDI: {success}/{len(files)}")
    print(f"{'='*60}")


def interactive_menu():
    """İnteraktif menü."""
    print("\n" + "="*60)
    print("📋 VERİ İNDİRME MENÜSÜ (Incremental Update)")
    print("="*60)
    print("1. 🪙 Kripto (Top 12)")
    print("2. 📈 US Hisseler (Top 9)")
    print("3. 💱 Forex & Emtialar")
    print("4. 🇹🇷 BIST (Top 5)")
    print("5. ⚙️  Tek Sembol (Custom)")
    print("6. 🔄 Tüm Mevcut Verileri Güncelle")
    print("="*60)
    
    choice = input("\nSeçiminiz (1-6): ").strip()
    
    if choice == '1':
        interval = input("Timeframe (1m/5m/15m/1h/4h/1d) [4h]: ").strip() or '4h'
        download_preset('crypto', interval)
    elif choice == '2':
        interval = input("Timeframe (5m/15m/1h/4h/1d) [1d]: ").strip() or '1d'
        download_preset('stocks', interval)
    elif choice == '3':
        interval = input("Timeframe (5m/15m/1h/4h/1d) [4h]: ").strip() or '4h'
        download_preset('forex', interval)
    elif choice == '4':
        interval = input("Timeframe (1h/4h/1d) [4h]: ").strip() or '4h'
        download_preset('bist', interval)
    elif choice == '5':
        symbol = input("Sembol (örn: BTCUSDT): ").strip().upper()
        exchange = input("Exchange (BINANCE/NASDAQ/OANDA/BIST) [BINANCE]: ").strip().upper() or 'BINANCE'
        interval = input("Timeframe [4h]: ").strip() or '4h'
        full = input("Tam indirme mi? (e/H): ").strip().lower() == 'e'
        download_symbol(symbol, exchange, interval, force_full=full)
    elif choice == '6':
        update_all_existing()
    else:
        print("❌ Geçersiz seçim!")
    
    # manage_data.py çalıştır
    run_manage = input("\n📊 Registry güncellensin mi? (E/h): ").strip().lower()
    if run_manage != 'h':
        print("\n🔄 Registry güncelleniyor...")
        tviewdata_dir = os.path.join(os.path.dirname(__file__), 'src', 'tviewdata')
        orig_dir = os.getcwd()
        os.chdir(tviewdata_dir)
        os.system(sys.executable + ' manage_data.py')
        os.chdir(orig_dir)


def main():
    """Ana fonksiyon."""
    args = sys.argv[1:]
    
    if not args:
        interactive_menu()
        return
    
    # Komut kontrolü
    if args[0] == '--update':
        update_all_existing()
    elif args[0] == '--crypto':
        interval = args[1] if len(args) > 1 else '4h'
        download_preset('crypto', interval)
    elif args[0] == '--stocks':
        interval = args[1] if len(args) > 1 else '1d'
        download_preset('stocks', interval)
    elif args[0] == '--forex':
        interval = args[1] if len(args) > 1 else '4h'
        download_preset('forex', interval)
    elif args[0] == '--bist':
        interval = args[1] if len(args) > 1 else '4h'
        download_preset('bist', interval)
    elif args[0] == '--full':
        # Tam indirme modu
        if len(args) > 1:
            preset = args[1]
            interval = args[2] if len(args) > 2 else '4h'
            download_preset(preset.lstrip('-'), interval, force_full=True)
    else:
        # Tek sembol modu: download_data.py BTCUSDT 4h 5000
        symbol = args[0].upper()
        interval = args[1] if len(args) > 1 else '4h'
        n_bars = int(args[2]) if len(args) > 2 else None  # None = otomatik
        
        # Exchange tahmin et
        if symbol.endswith('USDT'):
            exchange = 'BINANCE'
        elif len(symbol) == 6 and 'USD' in symbol:
            exchange = 'OANDA'
        else:
            exchange = 'NASDAQ'
        
        download_symbol(symbol, exchange, interval, n_bars)


if __name__ == '__main__':
    main()
