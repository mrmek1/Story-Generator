# Türkçe Kitap Oluşturucu (Turkish Book Generator)

Bu betik, Gemini API ve vektör veritabanı kullanarak tamamen yapılandırılmış, tutarlı bir kitap üreten bir araçtır. Kitap, seçtiğiniz türde derinlemesine bir evren içerisinde yaklaşık 250 bölümlük bir hikaye sunar.

## Özellikler

- Kullanıcının belirlediği tema ve tür doğrultusunda özgün bir kitap üretir
- Karakterler, olaylar ve mekanlar arasında tutarlı ilişkiler ve bağlantılar kurar
- Tam Türkçe dil desteği ile hikaye oluşturur
- Çıktıyı hem Markdown hem de PDF formatında sunar
- Düzenli ilerleme kaydetme özelliği ile uzun üretim süreçlerinde güvenlik sağlar
- İlerleme çubuğu ve ayrıntılı loglama ile üretim sürecini takip etme olanağı sunar
- Her bölüm için ayrı dosya oluşturarak kolay navigasyon sağlar
- Otomatik hata yakalama ve kurtarma mekanizmaları

## Hızlı Başlangıç

En kolay kurulum için, birlikte gelen kurulum ve çalıştırma betiğini kullanabilirsiniz:

```bash
# Betiği çalıştırılabilir yap
chmod +x install_and_run.sh

# Kurulum ve çalıştırma betiğini başlat
./install_and_run.sh
```

Bu betik:
1. Gerekli Python kütüphanelerini kurar
2. Gemini API anahtarını sorar ve yapılandırır
3. Tema ayarlarını düzenlemenize olanak tanır
4. Kitap oluşturma işlemini başlatır

## Manuel Kurulum

### Gereksinimler

- Python 3.8 veya daha yeni bir sürüm
- Gemini API anahtarı ([Google AI Studio](https://ai.google.dev/) üzerinden alabilirsiniz)

### Kurulum Adımları

1. Python sanal ortamı oluşturun ve etkinleştirin:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate  # Windows
```

2. Gerekli kütüphaneleri yükleyin:

```bash
pip install -r requirements.txt
```

3. `.env` dosyası oluşturun ve Gemini API anahtarınızı ekleyin:

```
GEMINI_API_KEY=your_api_key_here
LOG_LEVEL=INFO
MAX_TOKENS=4096
TEMPERATURE=0.7
```

4. `theme.config` dosyasını hikaye tercihlerinize göre düzenleyin

## Kullanım

1. Betiği çalıştırın:

```bash
python story_generator.py
```

2. Alternatif olarak, belirli parametrelerle çalıştırabilirsiniz:

```bash
# API anahtarını komut satırında vererek
python story_generator.py --api-key=YOUR_GEMINI_API_KEY

# Farklı bir yapılandırma dosyası kullanarak
python story_generator.py --config=custom_theme.config
```

## Çıktı Dosyaları

Betik çalıştığında aşağıdaki dizin yapısını oluşturur:

- `output/`: Ana çıktı dizini
  - `kitap.md`: Tam kitap içeriği (Markdown formatı)
  - `kitap.pdf`: Tam kitap içeriği (PDF formatı)
  - `bolum_001.md`, `bolum_002.md`, ...: Her bölümün ayrı dosyası
  - `kitap_taslak.md`: Ara ilerleme dosyası

- `backup/`: Yedekleme ve ara işlem sonuçları
  - `universe_data.json`: Karakter ve konum verileri
  - `story_outline.json`: Bölüm taslakları
  - `vector_db_chapter_*.json`: Bölüm bazlı vektör veritabanı yedekleri

## Yapılandırma Seçenekleri

### theme.config

Bu dosyada hikaye özelliklerini belirleyebilirsiniz:

- `genre`: Kitabın türü (Fantastik, Bilim Kurgu, Gizem, vb.)
- `theme`: Ana tema (Dostluk, İhanet, Aşk, İntikam, Keşif, vb.)
- `main_plot`: Ana olay örgüsü fikri
- `target_audience`: Hedef kitle
- `chapter_count`: Bölüm sayısı
- `tone`: Hikayenin tonu (Karanlık, Neşeli, Dramatik, vb.)
- `character_complexity`: Karakter karmaşıklığı seviyesi

### .env

Bu dosyada API ve çalışma parametrelerini belirleyebilirsiniz:

- `GEMINI_API_KEY`: Gemini API anahtarı
- `LOG_LEVEL`: Loglama seviyesi (INFO, DEBUG, WARNING, ERROR)
- `MAX_TOKENS`: Maksimum token sayısı
- `TEMPERATURE`: Yaratıcılık seviyesi (0.0-1.0 arası)

## Çalışma Prensibi

1. Betik önce kullanıcının yapılandırmasına göre bir hikaye dünyası oluşturur (karakterler, mekanlar).
2. Vektör veritabanı, bu öğeler arasındaki ilişkileri korur ve tutarlılığı sağlar.
3. Hikaye taslağı oluşturulur ve her bölüm, önceki bölümleri dikkate alarak yazılır.
4. Her 5 bölümde bir ara sonuçlar diske kaydedilir.
5. Tüm bölümler tamamlandığında, kitap başlığı, ön söz ve ek bilgiler eklenir.
6. Nihai çıktı hem Markdown hem de PDF formatında oluşturulur.

## Notlar ve İpuçları

- Hikaye üretim süreci uzun olabilir; sabırlı olun.
- Gemini API çağrı limitleri nedeniyle, çok fazla çağrı yapılırsa hata alabilirsiniz.
- En iyi sonuçlar için, ana olay örgüsü ve türü hakkında mümkün olduğunca detaylı bilgi verin.
- İşlemi istediğiniz zaman Ctrl+C ile durdurabilirsiniz; kısmi sonuçlar kaydedilecektir.
- Büyük kitaplar için bölüm sayısını azaltabilir veya betiği parça parça çalıştırabilirsiniz.
- Çıktı dizinlerini (`output/` ve `backup/`) manuel olarak yedekleyerek önceki çalışmaları koruyabilirsiniz.

## Sorun Giderme

- **API Hataları**: API anahtarınızın doğru olduğundan ve kredi limitinizin yeterli olduğundan emin olun.
- **Bellek Sorunları**: Çok uzun kitaplar için bellek yetersiz kalabilir. Daha az bölüm sayısı ile deneyin.
- **PDF Oluşturma Sorunları**: Eğer PDF oluşturulamıyorsa, Markdown çıktısını kullanarak kendi araçlarınızla PDF'e dönüştürebilirsiniz.
- **Tutarsız İçerik**: Tür ve ana olay örgüsünü daha net tanımlayarak tutarlılığı artırın.

## Lisans

Bu proje açık kaynak olarak dağıtılmaktadır. 