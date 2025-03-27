#!/bin/bash

# Renk tanımlamaları
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================================${NC}"
echo -e "${BLUE}          TÜRKÇE KİTAP OLUŞTURUCU KURULUMU            ${NC}"
echo -e "${BLUE}=======================================================${NC}"
echo

# Python sürümünü kontrol et
echo -e "${YELLOW}Python sürümü kontrol ediliyor...${NC}"
if command -v python3 &>/dev/null; then
    python_version=$(python3 --version)
    echo -e "${GREEN}$python_version bulundu.${NC}"
else
    echo -e "${RED}Python 3 bulunamadı. Lütfen Python 3.8 veya daha yeni bir sürüm yükleyin.${NC}"
    exit 1
fi

# Sanal ortam oluştur
echo -e "\n${YELLOW}Sanal ortam oluşturuluyor...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}Var olan 'venv' dizini bulundu. Yeniden oluşturmak ister misiniz? (e/h)${NC}"
    read -r response
    if [[ "$response" =~ ^([eE][vV]*|[yY][eE]*|[eE])$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo -e "${GREEN}Sanal ortam yeniden oluşturuldu.${NC}"
    else
        echo -e "${GREEN}Var olan sanal ortam kullanılacak.${NC}"
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}Sanal ortam oluşturuldu.${NC}"
fi

# Sanal ortamı etkinleştir
echo -e "\n${YELLOW}Sanal ortam etkinleştiriliyor...${NC}"
source venv/bin/activate || {
    echo -e "${RED}Sanal ortam etkinleştirilemedi.${NC}"
    exit 1
}
echo -e "${GREEN}Sanal ortam etkinleştirildi.${NC}"

# Bağımlılıkları yükle
echo -e "\n${YELLOW}Gerekli paketler yükleniyor...${NC}"
pip install --upgrade pip
pip install -r requirements.txt || {
    echo -e "${RED}Paketler yüklenemedi. Lütfen hataları kontrol edin.${NC}"
    exit 1
}
echo -e "${GREEN}Tüm bağımlılıklar başarıyla yüklendi.${NC}"

# API anahtarını kontrol et ve iste
check_api_key() {
    if [ ! -f .env ] || ! grep -q "GEMINI_API_KEY" .env || grep -q "GEMINI_API_KEY=your_api_key_here" .env; then
        echo -e "\n${YELLOW}Gemini API anahtarı bulunamadı veya geçerli değil.${NC}"
        echo -e "${YELLOW}Lütfen Gemini API anahtarınızı girin:${NC}"
        read -r api_key
        
        if [ -z "$api_key" ]; then
            echo -e "${RED}API anahtarı girilmedi. İşlem iptal ediliyor.${NC}"
            return 1
        fi
        
        if [ -f .env ]; then
            # .env dosyası varsa API anahtarını güncelle
            sed -i.bak "s|GEMINI_API_KEY=.*|GEMINI_API_KEY=$api_key|" .env && rm -f .env.bak
        else
            # .env dosyası yoksa yeni oluştur
            echo "GEMINI_API_KEY=$api_key" > .env
            echo "LOG_LEVEL=INFO" >> .env
            echo "MAX_TOKENS=4096" >> .env
            echo "TEMPERATURE=0.7" >> .env
        fi
        
        echo -e "${GREEN}API anahtarı .env dosyasına kaydedildi.${NC}"
    else
        echo -e "\n${GREEN}Gemini API anahtarı .env dosyasında bulundu.${NC}"
    fi
    return 0
}

# Kitap oluşturma işlemini başlat
start_generation() {
    echo -e "\n${BLUE}=======================================================${NC}"
    echo -e "${BLUE}          KİTAP OLUŞTURMA İŞLEMİ BAŞLIYOR             ${NC}"
    echo -e "${BLUE}=======================================================${NC}"
    
    echo -e "\n${YELLOW}Hikaye ayarları düzenlemek ister misiniz? (e/h)${NC}"
    read -r response
    if [[ "$response" =~ ^([eE][vV]*|[yY][eE]*|[eE])$ ]]; then
        if command -v nano &>/dev/null; then
            nano theme.config
        elif command -v vim &>/dev/null; then
            vim theme.config
        else
            echo -e "${RED}Metin düzenleyici bulunamadı. Lütfen theme.config dosyasını manuel olarak düzenleyin.${NC}"
            sleep 3
        fi
    fi
    
    # Betik çalıştır
    echo -e "\n${YELLOW}Kitap oluşturma işlemi başlatılıyor...${NC}"
    python3 story_generator.py || {
        echo -e "${RED}Kitap oluşturma işlemi başarısız oldu. Lütfen hataları kontrol edin.${NC}"
        return 1
    }
}

# Ana menü
main_menu() {
    while true; do
        echo -e "\n${BLUE}=======================================================${NC}"
        echo -e "${BLUE}                     ANA MENÜ                          ${NC}"
        echo -e "${BLUE}=======================================================${NC}"
        echo -e "${YELLOW}1. Kitap oluşturmayı başlat${NC}"
        echo -e "${YELLOW}2. theme.config dosyasını düzenle${NC}"
        echo -e "${YELLOW}3. API anahtarını güncelle${NC}"
        echo -e "${YELLOW}4. Çıkış${NC}"
        echo
        echo -e "${YELLOW}Seçiminiz (1-4):${NC}"
        read -r choice
        
        case $choice in
            1)
                start_generation
                ;;
            2)
                if command -v nano &>/dev/null; then
                    nano theme.config
                elif command -v vim &>/dev/null; then
                    vim theme.config
                else
                    echo -e "${RED}Metin düzenleyici bulunamadı. Lütfen theme.config dosyasını manuel olarak düzenleyin.${NC}"
                    sleep 3
                fi
                ;;
            3)
                rm -f .env
                check_api_key
                ;;
            4)
                echo -e "${GREEN}Programdan çıkılıyor...${NC}"
                break
                ;;
            *)
                echo -e "${RED}Geçersiz seçim. Lütfen 1-4 arasında bir numara girin.${NC}"
                ;;
        esac
    done
}

# API anahtarını kontrol et
check_api_key || exit 1

# Ana menüyü göster
main_menu

# Sanal ortamdan çık
deactivate
echo -e "\n${GREEN}İşlem tamamlandı.${NC}" 