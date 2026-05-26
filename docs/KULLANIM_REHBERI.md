# Opus Backtrader - Kullanım Rehberi

## 📋 İçindekiler
1. [Sistem Genel Bakış](#sistem-genel-bakış)
2. [Kurulum](#kurulum)
3. [Dashboard Sayfaları](#dashboard-sayfaları)
4. [Stratejiler](#stratejiler)
5. [Teknik Yapı](#teknik-yapı)
6. [Artılar ve Eksiler](#artılar-ve-eksiler)
7. [CLI Kullanımı](#cli-kullanımı)

---

## 🏗️ Sistem Genel Bakış

**Opus Backtrader**, Python tabanlı kapsamlı bir algoritmik trading sistemidir.

### Temel Bileşenler:

| Bileşen | Açıklama |
|---------|----------|
| **Backtrader Engine** | Ana backtesting motoru - strateji çalıştırma, order yönetimi |
| **Data Manager** | Çoklu kaynaklardan veri çekme ve cache'leme |
| **Streamlit Dashboard** | Web tabanlı görsel arayüz (8 sayfa) |
| **MLflow** | Deney takibi ve sonuç karşılaştırma |
| **Paper Trader** | Sanal para ile canlı trading simülasyonu |
| **Pine Converter** | TradingView Pine Script → Python çevirici |

---

## ⚙️ Kurulum

```bash
# 1. Virtual environment oluştur
python -m venv venv

# 2. Aktive et
.\venv\Scripts\activate  # Windows
source venv/bin/activate # Linux/Mac

# 3. Paketleri kur
pip install -r requirements.txt

# 4. Dashboard'u başlat
streamlit run dashboard.py

# 5. MLflow UI (ayrı terminal)
mlflow ui --backend-store-uri mlruns
```

---

## 🖥️ Dashboard Sayfaları

### 1. 🏠 Dashboard (Ana Sayfa)
**Ne Yapar:** Hızlı backtest çalıştırma, genel istatistikler
**Nasıl Kullanılır:** 
- Kategori seç (US Stocks, Crypto, Forex)
- Sembol seç
- Strateji seç
- "Run Backtest" tıkla

---

### 2. 🔬 Backtest
**Ne Yapar:** Detaylı backtest konfigürasyonu
**Özellikler:**
- Sembol dropdown (kategori bazlı)
- Veri kaynağı seçimi (Yahoo, TradingView)
- Strateji parametreleri
- Risk yönetimi ayarları (Risk %, RR Ratio)
- Grafik sonuçları

---

### 3. 🎯 Optimize
**Ne Yapar:** Parametre optimizasyonu (grid search)
**Nasıl Çalışır:**
1. Parametre aralıkları belirle (slider ile)
2. Tüm kombinasyonları test et
3. En iyi parametreleri bul
4. Heatmap ile görselleştir

**Örnek:**
- Supertrend Period: 7-15
- Multiplier: 2.0-4.0
- Toplam: ~25 kombinasyon test edilir

---

### 4. 📥 Data Manager (YENİ!)
**Ne Yapar:** Veri indirme, cache yönetimi ve export
**Sekmeler:**
- **📥 Download Data:** Tekil/toplu veri indirme
- **💾 Cache Manager:** Cache görüntüleme, temizleme, TviewData sync
- **📂 TviewData Files:** Mevcut veri dosyaları
- **📤 Export:** CSV olarak dışa aktarma

---

### 5. 💹 Paper Trade
**Ne Yapar:** Sanal para ile gerçek zamanlı trading
**Özellikler:**
- $100,000 sanal sermaye
- Anlık fiyatlar (Yahoo Finance)
- Pozisyon takibi
- P&L hesaplama
- Trade geçmişi

**Kullanım:**
1. Sembol seç
2. Miktar gir
3. BUY veya SELL tıkla
4. Pozisyonları takip et

---

### 5. 🔄 Pine Convert (YENİ!)
**Ne Yapar:** TradingView Pine Script kodunu Python/Backtrader'a çevirir
**Özellikler:**
- Pine Script v5 desteği
- Otomatik fonksiyon dönüşümü
- İndikatör ve strateji desteği
- Python dosyası indirme

**Nasıl Kullanılır:**
1. Dashboard'da "🔄 Pine Convert" sayfasına git
2. Sol tarafa Pine Script kodunu yapıştır
3. "Python'a Çevir" butonuna tıkla
4. Sağ tarafta Python kodu görünecek
5. "Python Dosyası İndir" ile indir

**Desteklenen Fonksiyonlar:**
| Pine Script | Python/Backtrader |
|-------------|-------------------|
| `ta.sma(close, 14)` | `bt.indicators.SMA()` |
| `ta.ema(close, 14)` | `bt.indicators.EMA()` |
| `ta.rsi(close, 14)` | `bt.indicators.RSI()` |
| `ta.atr(14)` | `bt.indicators.ATR()` |
| `ta.macd(...)` | `bt.indicators.MACD()` |
| `ta.crossover(a, b)` | `bt.indicators.CrossOver()` |
| `strategy.entry(...)` | `self.buy()` / `self.sell()` |

**⚠️ Önemli Not:** Otomatik çeviri yaklaşık sonuç verir. Manuel kontrol gereklidir!

---

### 6. 📊 Compare
**Ne Yapar:** Birden fazla stratejiyi karşılaştır
**Nasıl:**
1. Aynı sembol/timeframe seç
2. Karşılaştırılacak stratejileri işaretle
3. Sonuçları tablo ve grafik olarak gör

---

### 7. 📋 History
**Ne Yapar:** Kayıtlı raporları görüntüle ve indir
**İçerik:**
- Excel raporları (.xlsx)
- İndirme butonu

---

### 8. ⚙️ Settings
**Ne Yapar:** Sistem ayarları ve MLflow yönetimi
**Özellikler:**
- MLflow durumu
- Son deneyler
- Veritabanı boyutu
- Cache temizleme
- Sistem bilgisi

---

## 📈 Stratejiler

### 1. Supertrend
**Tip:** Trend Following
**Çalışma Mantığı:**
- ATR bazlı dinamik stop-loss
- Trend değişiminde sinyal üretir
- Parametreler: `period`, `multiplier`

**En İyi Kullanım:** Güçlü trendli piyasalar
**Zayıf Yön:** Yatay piyasalarda whipsaw

---

### 2. SMA Crossover
**Tip:** Trend Following
**Çalışma Mantığı:**
- Hızlı SMA yavaş SMA'yı yukarı kesince AL
- Aşağı kesince SAT
- Parametreler: `fast_period`, `slow_period`

**En İyi Kullanım:** Uzun vadeli trendler
**Zayıf Yön:** Gecikmeli sinyaller

---

### 3. RSI Mean Reversion
**Tip:** Mean Reversion
**Çalışma Mantığı:**
- RSI < oversold → AL (aşırı satım)
- RSI > overbought → SAT (aşırı alım)
- Parametreler: `rsi_period`, `oversold`, `overbought`

**En İyi Kullanım:** Range-bound piyasalar
**Zayıf Yön:** Güçlü trendlerde kayıp

---

### 4. SMC (Smart Money Concepts)
**Tip:** Institutional Trading
**Çalışma Mantığı:**
- Order Blocks (kurumsal alım/satım bölgeleri)
- Fair Value Gaps (fiyat dengesizlikleri)
- Liquidity Levels (stop-loss kümelenmeleri)
- Break of Structure (trend değişimi)

**En İyi Kullanım:** Tüm piyasa koşulları
**Zayıf Yön:** Karmaşık, daha az sinyal

---

## 🔧 Teknik Yapı

### Backtest Engine
```
BacktestEngine
├── DataManager (veri çekme)
│   ├── YahooFetcher
│   ├── TradingViewFetcher
│   └── CCXTFetcher
├── Cerebro (Backtrader motoru)
│   ├── Strategy
│   ├── Analyzers
│   └── Broker
└── Results (sonuçlar)
```

### Veri Akışı
```
Veri Kaynağı → Cache (SQLite) → Backtrader → Analyzers → Dashboard
```

### Dosya Yapısı
```
├── main.py              # CLI giriş noktası
├── dashboard.py         # Streamlit arayüz
├── src/
│   ├── backtest/        # Engine ve analyzers
│   ├── strategies/      # Trading stratejileri
│   ├── indicators/      # Teknik göstergeler
│   ├── data/            # Veri yönetimi
│   ├── trading/         # Paper trading
│   ├── tracking/        # MLflow entegrasyonu
│   ├── converter/       # Pine Script converter
│   └── visualization/   # Grafikler
├── config/              # Ayar dosyaları
├── data/                # SQLite cache
└── mlruns/              # MLflow deneyleri
```

---

## ⚖️ Artılar ve Eksiler

### ✅ Artılar

| Özellik | Açıklama |
|---------|----------|
| **Backtrader Motoru** | Profesyonel, esnek, geniş topluluk |
| **Çoklu Veri Kaynağı** | Yahoo, TradingView, CCXT (kripto) |
| **Görsel Dashboard** | Kod yazmadan kullanım |
| **MLflow Entegrasyonu** | Otomatik deney takibi |
| **Paper Trading** | Risk almadan pratik |
| **Optimizasyon** | Grid search ile en iyi parametreler |
| **Modüler Yapı** | Kolay genişletilebilir |
| **Cache Sistemi** | Hızlı tekrar testler |

### ❌ Eksiler

| Konu | Açıklama |
|------|----------|
| **Gerçek Zamanlı Veri** | Henüz streaming yok |
| **Canlı Trading** | Sadece backtest ve paper trade |
| **TradingView API** | Bazen bağlantı sorunları |
| **Bracket Order Margin** | Büyük pozisyonlarda red |
| **Tek Sembol** | Aynı anda tek backtest |

---

## 💻 CLI Kullanımı

### Temel Komutlar

```bash
# Basit backtest
python main.py --strategy supertrend --symbol AAPL --timeframe 1d

# Detaylı backtest
python main.py --strategy sma --symbol MSFT --timeframe 1h \
    --bars 1000 --cash 50000 --risk-pct 0.02 --report

# Rapor ile
python main.py --strategy rsi --symbol GOOGL --report --chart
```

### Tüm Parametreler

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `--strategy` | Strateji adı | supertrend |
| `--symbol` | Sembol | AAPL |
| `--source` | Veri kaynağı | yahoo |
| `--timeframe` | Zaman dilimi | 1d |
| `--bars` | Bar sayısı | 1000 |
| `--cash` | Başlangıç sermayesi | 100000 |
| `--risk-pct` | Risk yüzdesi | 0.02 |
| `--rr-ratio` | Risk/Reward oranı | 2.0 |
| `--direction` | İşlem yönü | long |
| `--report` | Excel raporu oluştur | - |
| `--chart` | Grafik göster | - |

---

## 🚀 Hızlı Başlangıç

```bash
# 1. Dashboard başlat
streamlit run dashboard.py

# 2. Tarayıcıda aç
# http://localhost:8501

# 3. Dashboard üzerinden:
#    - Sembol seç (AAPL)
#    - Strateji seç (Supertrend)
#    - "Run Backtest" tıkla
#    - Sonuçları incele
```

---

## 📞 Destek

- **MLflow UI:** `mlflow ui --backend-store-uri mlruns`
- **Cache Temizle:** Settings → Clear Cache
- **Hesap Sıfırla:** Paper Trade → Reset Account
