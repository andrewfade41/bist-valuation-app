# BIST Valuation App (Borsa Adil Değer Hesaplayıcı)

Borsa İstanbul (BİST) şirketlerinin **Temel ve Teknik Analiz** verilerini bir araya getirerek, her bir hisse için adil değer hesabı yapan ve potansiyel yatırım fırsatlarını (iskontolu hisseleri) tespit eden kapsamlı bir Python & Streamlit uygulamasıdır.

Bu proje, hem interaktif bir web arayüzü sunar (`app.py`), hem de arka planda her sabah çalışan tam otomatik bir e-posta bildirim botuna (`daily_scanner.py`) sahiptir.

---

## 🚀 Temel Özellikler

1. **Çoklu Adil Değer Hesaplama (3 Farklı Metot)**
   - **F/K'ya Göre Hedef Fiyat:** (Net Dönem Karı / Ödenmiş Sermaye) * Beklenen F/K Çarpanı
   - **PD/DD'ye Göre Hedef Fiyat:** (Ana Ortaklık Özkaynaklar / Ödenmiş Sermaye) * Beklenen PD/DD Çarpanı
   - **Özsermaye Karlılığına (ROE) Göre:** Hisse Başı Defter Değeri * (ROE / Beklenen Sabit Getiri Oranı)
   - **BİST & Sektör Ortalaması:** Hissenin içinde bulunduğu sektör ve genel BİST piyasası ortalamalarına göre belirlenen iki ek hedef fiyat metriği.

2. **Dinamik Teknik Analiz Filtreleri (TradingView Destekli)**
   - **RSI (14):** 30 altı (Aşırı Satım) ve 70 üstü (Aşırı Alım) bölgelerinin otomatik renklendirilmesi.
   - **MA200 Uzaklık:** 200 günlük hareketli ortalamanın neresinde olduğunu oranlayarak (iskonto/prim) tespit etme.
   - **Bilanço Açıklanma Tarihi:** Hisselerin bilançolarını ne zaman açıklayacağının/açıkladığının takibi.

3. **Tam Otomatik Bilanço Tarayıcı ve E-Posta Botu (GitHub Actions)**
   - Her gün saat 08:00'de (piyasa açılmadan hemen önce) arkaplanda çalışarak İş Yatırım üzerinden yeni bilançoları kontrol eder.
   - Eğer dün "Belirsiz" olan veya değişen yeni bir "Son Dönem" (Örn: 2024/03) bilançosu tespit ederse, o hisseler için anlık adil değerleri ve RSI'ı hesaplayıp e-posta listenize tablo olarak gönderir.

---

## 🛠️ Kurulum (Yerel Bilgisayarda Çalıştırma)

Terminalinizi açın ve aşağıdaki adımları sırasıyla uygulayın:

**1. Projeyi İndirin**
```bash
git clone https://github.com/KULLANICI_ADINIZ/bist-valuation-app.git
cd bist-valuation-app
```

**2. Gerekli Kütüphaneleri Yükleyin**
```bash
pip install -r requirements.txt
```

**3. Uygulamayı Başlatın**
```bash
streamlit run app.py
```
*(Tarayıcınızda otomatik olarak `localhost:8501` adresinde uygulama penceresi açılacaktır.)*

---

## 🌐 Canlıya Alma (Deploy)

Bu projeyi **ücretsiz olarak** 7/24 internette yayına alabilirsiniz.

### Arayüzü Streamlit Cloud'da Yayınlamak:
1. Projeyi kendi GitHub hesabınıza yükleyin.
2. [share.streamlit.io](https://share.streamlit.io/) adresine girin ve GitHub hesabınızı bağlayın.
3. **"New App"** butonuna basıp deponuzu ve `app.py` dosyasını seçin. "Deploy" butonuna basın. (Uygulamanız kullanıma hazırdır).

### E-Posta Botunu GitHub Actions'ta Çalıştırmak:
Proje içinde yüklü olan `.github/workflows/daily-scanner.yml` dosyası sayesinde arkaplan botunuz çalışmaya hazırdır. Sadece e-posta şifrenizi eklemeniz yeterlidir:
1. GitHub deponuzun ana sayfasından: **Settings** > **Secrets and variables** > **Actions** menüsüne gidin.
2. "New repository secret" diyerek `.env.example` dosyasında yer alan şu 5 bilgiyi tek tek ekleyin:
   - `SMTP_SERVER` *(smtp.gmail.com)*
   - `SMTP_PORT` *(587)*
   - `SMTP_EMAIL` *(kendi-gmail-adresiniz@gmail.com)*
   - `SMTP_PASSWORD` *(Google'dan alacağınız 16 haneli Uygulama Şifresi)*
   - `SUBSCRIBER_EMAILS` *(bildirim gönderilecek e-posta adresleri, virgülle ayrılarak)*

Ertesi sabah 08:00'den itibaren GitHub botunuz bilançoları otomatik tarayıp mail atmaya başlayacaktır.

---

## 🗂️ Dosya Yapısı
- `app.py`: Streamlit arayüz uygulamasının bulunduğu ana dosya.
- `calculator.py`: Formüllerin ve hesaplamaların yapıldığı matematiksel çekirdek.
- `data_fetcher.py`: İş Yatırım ve TradingView'den canlı veri çeken Web Scraper.
- `daily_scanner.py`: Günlük bilanço kontrolü yapan ve E-Posta atan bot.
- `fetch_sectors.py`: yfinance üzerinden şirketlerin sektör kodlarını json olarak çıkartan betik.
- `sectors.json`: Hisselerin endüstri/sektör eşleştirmelerinin tutulduğu cache bellek.
- `is_yatirim_periods.json`: Bir önceki günün bilanço dönemlerinin tutulduğu veritabanı (Karşılaştırma için).

---
*Yasal Uyarı: Bu yazılım bir yatırım tavsiyesi aracı değildir, temel ve teknik analiz çarpanlarını gösteren bir veri hesaplayıcıdır.*
