# 🚀 Opus Backtrader VDS Deployment Rehberi (Debian)

Bu rehber, projenizi 2GB RAM / 2 vCPU özellikli Debian sunucunuzda çalıştırmanız için gerekli adımları içerir. Sunucunuzun özellikleri proje için yeterlidir ancak RAM kullanımı için **Swap Alanı (Sanal Bellek)** oluşturmamız önemle tavsiye edilir.

## 1. Sunucuya Hazırlık ve Bağlantı

Terminale (veya PowerShell'e) şu komutu yazarak sunucunuza bağlanın:
```bash
ssh root@<SUNUCU_IP_ADRESI>
```
*(Şifrenizi sorcaktır, yazarken ekranda görünmez, enter'a basın)*

---

## 2. Sistem Güncelleme ve Gerekli Paketler

Sunucuya girdikten sonra şu komutları sırasıyla çalıştırın:

```bash
# Paket listesini güncelle ve sistemi yükselt
apt update && apt upgrade -y

# Gerekli araçları kur (Python, Git, pip, venv)
apt install python3-full python3-pip python3-venv git htop screen -y
```

---

## 3. Performans İçin Swap Alanı Oluşturma (Önemli!)
3GB RAM, büyük veri analizlerinde darboğaz yapabilir. Diskinizden 4GB'ı RAM gibi kullanmak için:

```bash
# 4GB swap dosyası oluştur
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Kalıcı hale getir
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
```

---

## 4. Projeyi Sunucuya Aktarma

Bunun için en kolay yöntem **GitHub** kullanmaktır. Eğer projeniz henüz GitHub'da değilse, local bilgisayarınızdan dosyaları `scp` ile de atabiliriz. 

**Yöntem A: GitHub (Önerilen)**
1. Projenizi GitHub'a pushlayın (Private repo olabilir).
2. Sunucuda:
```bash
git clone https://github.com/KULLANICI_ADI/PROJE_ADI.git
cd PROJE_ADI
```

**Yöntem B: SCP (Localden Direkt Atma)**
Local bilgisayarınızda PowerShell'i açın ve proje klasörünün bir üst dizinine çıkıp:
```powershell
# Sadece gerekli klasörleri atar (venv ve __pycache__ hariç)
scp -r "5.Opus_backtrader" root@<SUNUCU_IP_ADRESI>:/root/opus_backtrader
```

---

## 5. Kurulum ve Çalıştırma

Proje klasörüne girdikten sonra (`cd opus_backtrader` veya klasör adı neyse):

```bash
# 1. Sanal ortam oluştur
python3 -m venv venv

# 2. Sanal ortamı aktif et
source venv/bin/activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. Streamlit'i Test Et (8503 portundan)
streamlit run dashboard.py --server.port 8503
```

*Eğer tarayıcıdan `http://<SUNUCU_IP>:8503` adresine gidip siteyi görüyorsanız kurulum başarılıdır!* `CTRL+C` ile durdurun.

---

## 6. Sürekli Arka Planda Çalıştırma (7/24)

Terminali kapattığınızda projenin kapanmaması için `screen` kullanacağız:

```bash
# Yeni bir oturum aç
screen -S opus

# Sanal ortamı aktif et
source venv/bin/activate

# Uygulamayı başlat
streamlit run dashboard.py --server.port 8503
```

Şimdi uygulamanız çalışıyor. Terminalden çıkmak ama çalışmasını sürdürmek için klavyeden:
1. `CTRL + A` tuşlarına aynı anda basın, bırakın.
2. `D` tuşuna basın.
*(Bu işlem "Detach" yapar, yani arka plana atar)*

Tekrar o ekrana dönmek isterseniz:
```bash
screen -r opus
```

---

## 7. Önemli Notlar

- **Veri Tabanı:** Localdeki `data/` klasörünüzü sunucuya atarsanız (`scp` ile), mevcut verilerinizle devam edersiniz.
- **TradingView:** `tvdatafeed` kütüphanesi sunucuda ilk çalıştırıldığında hata verebilir (UI yok diye). Bunu aşmak için local bilgisayarınızdaki `.tvdatafeed` (genelde `C:\Users\Kullanıcı\.tvdatafeed` veya root klasöründe) dosyasını sunucuya kopyalamanız gerekebilir.
