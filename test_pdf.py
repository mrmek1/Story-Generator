#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF Oluşturma Test Betiği

Bu basit betik PDF oluşturma metodlarını test eder.
"""

import os
import sys
import logging
import markdown
import subprocess
import importlib.util

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PDFTest")

# WeasyPrint kullanılabilirlik kontrolü
HAS_WEASYPRINT = importlib.util.find_spec("weasyprint") is not None

def test_pdf_generation():
    """PDF oluşturma yöntemlerini test eder."""
    logger.info("PDF oluşturma testi başlatılıyor...")
    
    # Test çıktı dizini
    os.makedirs("output", exist_ok=True)
    
    # Basit Markdown içeriği oluştur
    markdown_content = """
# PDF Test Belgesi

Bu belge, PDF oluşturma yeteneklerini test etmek için oluşturulmuştur.

## Özellikler

1. Başlıklar
2. **Kalın metin**
3. *İtalik metin*
4. `Kod bloğu`
5. [Bağlantı](https://example.com)

### Tablo Örneği

| Başlık 1 | Başlık 2 | Başlık 3 |
|----------|----------|----------|
| Hücre 1  | Hücre 2  | Hücre 3  |
| Hücre 4  | Hücre 5  | Hücre 6  |

---

Eğer bu PDF doğru bir şekilde oluşturulduysa, test başarılı demektir.
    """
    
    # Markdown dosyasını kaydet
    with open("output/test.md", "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    logger.info("Test Markdown dosyası oluşturuldu: output/test.md")
    
    # WeasyPrint ile dene
    weasyprint_success = False
    if HAS_WEASYPRINT:
        try:
            logger.info("WeasyPrint testi başlatılıyor...")
            # WeasyPrint'i güvenli bir şekilde import et
            from weasyprint import HTML
            logger.info("WeasyPrint başarıyla import edildi.")
            
            # HTML'e dönüştür
            html_content = markdown.markdown(markdown_content)
            
            # PDF oluştur
            HTML(string=html_content).write_pdf("output/test_weasyprint.pdf")
            logger.info("PDF başarıyla oluşturuldu: output/test_weasyprint.pdf")
            weasyprint_success = True
        except Exception as e:
            logger.error(f"WeasyPrint hatası: {e}")
    else:
        logger.warning("WeasyPrint paketi bulunamadı. WeasyPrint testi atlanıyor.")
    
    # Pandoc ile dene
    pandoc_success = False
    try:
        logger.info("Pandoc testi başlatılıyor...")
        # Önce PATH'i güncelleyelim (terminal yeniden başlatma gerekmeden)
        env = os.environ.copy()
        env["PATH"] = "/Library/TeX/texbin:" + env["PATH"]
        
        result = subprocess.run(
            ["pandoc", "output/test.md", "-o", "output/test_pandoc.pdf", "--pdf-engine=xelatex"],
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode == 0:
            logger.info("PDF başarıyla oluşturuldu: output/test_pandoc.pdf")
            pandoc_success = True
        else:
            logger.error(f"Pandoc hatası: {result.stderr}")
    except Exception as e:
        logger.error(f"Pandoc hatası: {e}")
    
    return weasyprint_success, pandoc_success

def suggest_alternatives():
    """PDF oluşturma için alternatif yöntemler önerir."""
    logger.info("\nAlternatif PDF oluşturma yöntemleri:")
    logger.info("1. Pandoc kurulumu: brew install pandoc")
    logger.info("2. Grip (GitHub Markdown önizleyici) kullanarak: pip install grip && grip output/test.md --export output/test.html")
    logger.info("3. Markdown Online Dönüştürücüler kullanarak.")
    logger.info("4. Markdown PDF VSCode eklentisi.")

if __name__ == "__main__":
    print("PDF oluşturma testleri başlatılıyor...")
    weasyprint_success, pandoc_success = test_pdf_generation()
    
    print("\n----- Test Sonuçları -----")
    
    if weasyprint_success:
        print("✅ WeasyPrint testi başarılı! PDF oluşturuldu.")
        print("   Oluşturulan PDF: output/test_weasyprint.pdf")
    else:
        print("❌ WeasyPrint testi başarısız.")
        if HAS_WEASYPRINT:
            print("   WeasyPrint paketi yüklü, ancak çalıştırılamadı.")
            print("   Gerekli sistem bağımlılıklarını yüklemek için:")
            print("   brew install pango cairo gdk-pixbuf gobject-introspection libffi")
        else:
            print("   WeasyPrint paketi yüklü değil.")
    
    if pandoc_success:
        print("✅ Pandoc testi başarılı! PDF oluşturuldu.")
        print("   Oluşturulan PDF: output/test_pandoc.pdf")
    else:
        print("❌ Pandoc testi başarısız.")
        print("   Pandoc kurulu değil veya çalıştırılamadı.")
        print("   Yüklemek için: brew install pandoc")
    
    if not weasyprint_success and not pandoc_success:
        print("\n❌ Tüm testler başarısız!")
        suggest_alternatives()
    else:
        print("\n✅ En az bir PDF oluşturma yöntemi çalışıyor!")
        
        if pandoc_success:
            print("☞ Pandoc kullanarak PDF oluşturulabilir.")
        elif weasyprint_success:
            print("☞ WeasyPrint kullanarak PDF oluşturulabilir.") 