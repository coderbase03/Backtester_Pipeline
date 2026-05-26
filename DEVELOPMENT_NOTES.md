# Opus Backtrader - Geliştirme Notları

## Bekleyen Hatalar / İyileştirmeler

### 1. TviewData Dashboard Entegrasyonu ❌
**Tarih:** 2026-01-03
**Durum:** Çözülmedi, sonraya bırakıldı

**Problem:**
- Backtest/Data Manager'dan indirilen veriler SQLite'a cache'leniyor
- sync_from_cache() ile CSV + Registry güncelleniyor
- Ancak TviewData Dashboard hala güncel verileri göstermiyor

**Olası Nedenler:**
1. Registry dosyası doğru konumda değil
2. TviewData Dashboard farklı bir path kullanıyor
3. Dashboard yeniden başlatma sorunu

**Çözüm Adımları:**
- [ ] TviewData Dashboard'un hangi registry'yi okuduğunu debug et
- [ ] Path'lerin doğru olup olmadığını kontrol et
- [ ] Alternatif: Doğrudan shared_data/processed taraması yap

---

## Tamamlanan Özellikler

### Terminal Veri İndirme
- `download_data.py` script'i oluşturuldu
- Tek sembol ve toplu indirme destekleniyor
- manage_data.py entegre edildi
