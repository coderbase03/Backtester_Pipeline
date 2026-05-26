# Opus Backtrader - Yapılacaklar ve Geliştirmeler

## 📋 Yüksek Öncelikli Geliştirmeler

### 1. Auto-Backtest Pipeline ⏳
**Öncelik:** Yüksek  
**Durum:** Planlanıyor

Keşfedilen stratejilerin otomatik test edilmesi:
- Multi-symbol test (3 sembol: BTC, ETH, SPY)
- Multi-timeframe test (1h, 4h, 1d)
- Aggregate scoring (ortalama Sharpe, tutarlılık)
- Out-of-sample validation (train 2020-2023, test 2024-2025)

```python
# Örnek pipeline
test_grid = {'symbols': ['BTCUSDT', 'ETHUSDT', 'SPY'], 'timeframes': ['1h', '4h', '1d']}
results = parallel_backtest(strategy, test_grid)
if results['consistency'] > 0.5:
    mark_as_promising(strategy)
```

---

### 2. GitHub Strategy Scraper 🔧
**Öncelik:** Yüksek  
**Durum:** Planlanıyor

Doğrudan Python stratejilerini GitHub'dan çek:
- `backtrader strategy python stars:>50` araması
- README'den açıklama çıkarma
- Star count = quality signal
- Otomatik test pipeline'a entegrasyon

---

### 3. Strategy DNA & Duplicate Detection 📊
**Öncelik:** Orta  
**Durum:** Planlanıyor

Aynı stratejinin farklı paylaşımlarını tespit:
- Fingerprint: indicators + timeframe + type
- Similarity check (>85% = duplicate)
- "RSI < 30 buy" gibi aynı fikirleri grupla

---

### 4. TradingView Script Scraper 📈
**Öncelik:** Orta  
**Durum:** Planlanıyor

TradingView public scripts'i çek:
- Pine Script → Python direct conversion
- Script puanı ve kullanım sayısı
- Backtest chart screenshot

---

## 📋 Mevcut Bekleyen Geliştirmeler

### 5. Otomatik Veri Güncelleme Scheduler
**Öncelik:** Orta
**Durum:** Beklemede

Verilerin düzenli aralıklarla otomatik güncellenmesi için:

**Seçenek A: Windows Task Scheduler**
```powershell
schtasks /create /tn "OpusDataUpdate" /tr "python download_data.py --update" /sc hourly
```

**Seçenek B: Python APScheduler**
```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(update_all_data, 'interval', hours=1)
```

---

### 6. Telegram Bot Bildirimleri
**Öncelik:** Orta  
**Durum:** Planlanıyor

- Yeni yüksek skorlu strateji bulunduğunda bildirim
- Backtest tamamlandı bildirimi
- Paper trade sinyal bildirimi
- Günlük özet raporu

---

### 7. Otomatik Zamanlayıcı (Auto Scheduler) 🕐
**Öncelik:** Orta  
**Durum:** Planlanıyor

VDS üzerinde 7/24 çalışan scheduled tasks:
- Günde 1x otomatik Reddit veri toplama
- Yeni postları otomatik AI analizi
- Haftalık strateji raporu email/telegram

```python
# APScheduler örneği
scheduler.add_job(collect_daily, 'cron', hour=2)  # Her gece saat 2
scheduler.add_job(analyze_new, 'interval', hours=6)  # 6 saatte bir
```

---

### 8. Strateji Karşılaştırma (Side-by-Side) 📊
**Öncelik:** Orta  
**Durum:** Planlanıyor

İki stratejiyi paralel backtest et ve karşılaştır:
- Aynı sembol ve tarih aralığında test
- Equity curve overlay
- Risk/return karşılaştırma tablosu
- Correlation analizi

---

### 9. AI Strateji Generatörü 🤖
**Öncelik:** Orta  
**Durum:** Planlanıyor

Kullanıcının verdiği prompttan yeni strateji üret:
- "RSI + MACD + Supertrend kombinasyonu yap"
- "Momentum + Mean Reversion hybrid strateji oluştur"
- Otomatik backtest ve iterasyon

---

### 10. Paper Trading Modu 📈
**Öncelik:** Yüksek  
**Durum:** Planlanıyor

Gerçek piyasa verisiyle simülasyon:
- Canlı TradingView verileri
- Position tracking dashboard
- P&L real-time güncelleme
- Sinyal geçmişi ve performans

---

## ✅ Tamamlanan Özellikler

| Özellik | Tarih | Açıklama |
|---------|-------|----------|
| Jenerik Strateji Mimarisi | - | BaseStrategy, alt stratejiler |
| Parametre Optimizasyonu | - | GridSearch, Optuna desteği |
| TviewData Entegrasyonu | - | Chart system, data files |
| Data Manager Sayfası | - | Download, cache, export |
| Incremental Data Update | 2026-01 | Eksik bar indirme, duplicate önleme |
| Terminal Veri İndirme | 2026-01 | download_data.py script |
| Reddit Strategy Scraper | 2026-01 | 2-aşamalı AI analizi |
| Pine → Python Converter | 2026-01 | GPT/GLM ile kod çevirisi |
| **Regex Pre-filter** | 2026-01-12 | Zero-cost noise filtering, %80 maliyet azaltma |
| **Code Priority Scoring** | 2026-01-12 | Kod+backtest içeren postlara öncelik |
| **Strateji Yönetim UI** | 2026-01-12 | Sıfırla/Sil butonları |
| **Proje Temizliği** | 2026-01-12 | 15 kullanılmayan dosya silindi |

---

## 🐛 Bilinen Sorunlar

### 1. tvDatafeed "nologin" Uyarısı
**Seviye:** Düşük
**Açıklama:** Login olmadan veri çekme çalışıyor ancak uyarı gösteriyor
**Çözüm:** config/secrets.yaml'a login bilgileri ekle

### 2. Streamlit use_container_width Deprecation
**Seviye:** Düşük  
**Açıklama:** 2025-12-31 sonrası `width='stretch'` kullanılmalı
**Çözüm:** Dashboard genelinde güncelle

---

## 💡 Stratejik Öneriler

### Yaklaşım Değişikliği
Mevcut: Discovery-heavy (çok post topla, manuel incele)  
Önerilen: Validation-heavy (az topla, otomatik test, kaliteliyi göster)

### Akış Optimizasyonu
```
1000 Reddit post
    ↓ Regex filter (free)
100 post with keywords
    ↓ AI Stage 1 (cheap)
20 valuable posts
    ↓ AI Stage 2 (full extraction)
10 strategies
    ↓ Auto-backtest (9 test each)
3 validated strategies → Show to user
```

---

## 📝 Notlar

- Detaylı hata notları: `DEVELOPMENT_NOTES.md`
- CLI kullanımı: `docs/CLI_GUIDE.md`
- Kullanım rehberi: `docs/KULLANIM_REHBERI.md`

---

## 2026-05-26 Yeni Yapılacaklar (Eklenen)

### 11) Cron Job Senaryosu (Data Downloader + Reddit Full Pipeline + Raporlama)
**Öncelik:** Yüksek  
**Durum:** Planlanacak
- VDS üzerinde cron/scheduler tasarımı netleştirilecek.
- Günlük veri indirme + Reddit collect/analyze + rapor üretimi uçtan uca otomatikleştirilecek.

### 12) Reddit Analiz Skorlama/Strateji Derin Çalışması
**Öncelik:** Yüksek  
**Durum:** Planlanacak
- Stage-1/Stage-2 skorlamaları yeniden kalibre edilecek.
- Actionable strategy tespit kalitesi ve false positive oranı iyileştirilecek.

### 13) GLM -> DeepSeek v4 Pro Geçişi
**Öncelik:** Yüksek  
**Durum:** Planlanacak
- Kod üretim ve/veya uygun pipeline adımlarında DeepSeek v4 Pro entegrasyonu yapılacak.
- Maliyet/kalite/latency karşılaştırması raporlanacak.

### 14) Analiz Model Karşılaştırması (o4-mini vs DeepSeek v4 Flash)
**Öncelik:** Yüksek  
**Durum:** Planlanacak
- Aynı veri setinde model bazlı analiz benchmark çalıştırılacak.
- Doğruluk, tutarlılık, token maliyeti, hız metrikleri kıyaslanacak.

### 15) Canlıya Alım + Stabilizasyon Test Dönemi
**Öncelik:** Yüksek  
**Durum:** Planlanacak
- Proje production ortamına alınacak.
- Belirli bir gözlem süresinde (ör. 1-2 hafta) stabilite/kalite takibi yapılacak.

### 16) Token Bazlı Maliyet Takibi (Detaylı)
**Öncelik:** Yüksek  
**Durum:** Planlanacak
- Provider/model/stage bazında input-output token ve USD maliyet logları standardize edilecek.
- Dashboard/rapor katmanında maliyet görünürlüğü artırılacak.
