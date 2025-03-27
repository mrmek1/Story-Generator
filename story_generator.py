#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story Generator - Kitap Oluşturucu

Bu betik, Gemini API ve vektör veritabanı kullanarak tam yapılandırılmış bir kitap üretir.
Kullanıcı sadece theme.config dosyasını düzenleyerek kendi tercihlerine göre hikaye üretebilir.
Tüm hikaye Türkçe olarak üretilir.
"""

import os
import sys
import json
import argparse
import asyncio
import logging
import traceback
import importlib.util
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import configparser
import random
import time
import uuid

# Gerekli kütüphaneleri içe aktarma
try:
    from dotenv import load_dotenv
    import google.generativeai as genai
    from google.generativeai.types import content_types
    from google.generativeai.types import generation_types
    import numpy as np
    from faiss import IndexFlatL2
    import markdown
    from tqdm import tqdm
except ImportError as e:
    print(f"Gerekli kütüphaneler yüklenmemiş: {e}")
    print("Lütfen şu komutu çalıştırın: pip install -r requirements.txt")
    sys.exit(1)

# WeasyPrint kullanılabilirlik kontrolü
HAS_WEASYPRINT = False
try:
    # WeasyPrint modülünün varlığını kontrol et ama import etme
    HAS_WEASYPRINT = importlib.util.find_spec("weasyprint") is not None
    if HAS_WEASYPRINT:
        print("WeasyPrint bulundu. PDF oluşturma etkinleştirildi.")
    else:
        print("WeasyPrint bulunamadı. PDF oluşturma için Pandoc kullanılacak.")
except:
    print("WeasyPrint kontrol edilirken hata oluştu. PDF oluşturma için Pandoc kullanılacak.")

# .env dosyasını yükle
load_dotenv()

# Loglama yapılandırması
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("story_generator.log")
    ]
)
logger = logging.getLogger("StoryGenerator")

# Veri modelleri
@dataclass
class Character:
    """Hikaye karakteri modeli."""
    id: str
    name: str
    description: str
    traits: List[str]
    background: str
    relationships: Dict[str, str]
    story_arc: str
    vector: Optional[np.ndarray] = None

@dataclass
class Location:
    """Hikaye konumu modeli."""
    id: str
    name: str
    description: str
    importance: str
    connected_locations: List[str]
    vector: Optional[np.ndarray] = None

@dataclass
class Event:
    """Hikaye olayı modeli."""
    id: str
    title: str
    description: str
    characters_involved: List[str]
    location_id: str
    preceding_events: List[str]
    following_events: List[str]
    chapter: int
    vector: Optional[np.ndarray] = None

@dataclass
class Chapter:
    """Hikaye bölümü modeli."""
    number: int
    title: str
    summary: str
    content: str
    characters: List[str]
    locations: List[str]
    events: List[str]
    
@dataclass
class StoryConfig:
    """Hikaye yapılandırma modeli."""
    genre: str
    theme: str
    main_plot: str
    target_audience: str
    chapter_count: int
    language: str = "Türkçe"
    tone: str = "Dengeli"
    character_complexity: str = "Karmaşık"

class GeminiClient:
    """Gemini API ile etkileşim için istemci sınıfı."""
    
    def __init__(self, api_key: str):
        """Gemini API istemcisini başlatır."""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.temperature = float(os.getenv('TEMPERATURE', '0.7'))
        self.max_tokens = int(os.getenv('MAX_TOKENS', '4096'))
        
    async def generate_content(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Verilen komut ile içerik oluşturur."""
        try:
            max_output_tokens = max_tokens or self.max_tokens
            response = await asyncio.to_thread(
                self.model.generate_content,
                content_types.to_contents(prompt),
                generation_config=generation_types.GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=self.temperature,
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API hatası: {e}")
            # Tekrar deneme mekanizması
            logger.info("5 saniye sonra tekrar deneniyor...")
            await asyncio.sleep(5)
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    content_types.to_contents(prompt),
                    generation_config=generation_types.GenerationConfig(
                        max_output_tokens=max_tokens or self.max_tokens,
                        temperature=self.temperature * 0.9,  # Hata durumunda daha düşük sıcaklık
                    )
                )
                return response.text
            except Exception as e2:
                logger.error(f"İkinci deneme de başarısız: {e2}")
                raise

class VectorDatabase:
    """Vektör veritabanı yönetimi için sınıf."""
    
    def __init__(self, vector_dim: int = 1536):
        """Vektör veritabanını başlatır."""
        self.character_index = IndexFlatL2(vector_dim)
        self.location_index = IndexFlatL2(vector_dim)
        self.event_index = IndexFlatL2(vector_dim)
        
        self.characters: Dict[str, Character] = {}
        self.locations: Dict[str, Location] = {}
        self.events: Dict[str, Event] = {}
        
        self.character_vectors: List[np.ndarray] = []
        self.location_vectors: List[np.ndarray] = []
        self.event_vectors: List[np.ndarray] = []
        
    def add_character(self, character: Character, vector: np.ndarray):
        """Karakteri vektör veritabanına ekler."""
        self.characters[character.id] = character
        self.character_vectors.append(vector)
        self.character_index.add(np.array([vector]))
        
    def add_location(self, location: Location, vector: np.ndarray):
        """Konumu vektör veritabanına ekler."""
        self.locations[location.id] = location
        self.location_vectors.append(vector)
        self.location_index.add(np.array([vector]))
        
    def add_event(self, event: Event, vector: np.ndarray):
        """Olayı vektör veritabanına ekler."""
        self.events[event.id] = event
        self.event_vectors.append(vector)
        self.event_index.add(np.array([vector]))
        
    def search_similar_characters(self, vector: np.ndarray, k: int = 5) -> List[Character]:
        """Benzer karakterleri bulur."""
        if self.character_index.ntotal == 0:
            return []
            
        distances, indices = self.character_index.search(np.array([vector]), k)
        return [list(self.characters.values())[i] for i in indices[0] if i < len(self.characters)]
        
    def search_similar_locations(self, vector: np.ndarray, k: int = 5) -> List[Location]:
        """Benzer konumları bulur."""
        if self.location_index.ntotal == 0:
            return []
            
        distances, indices = self.location_index.search(np.array([vector]), k)
        return [list(self.locations.values())[i] for i in indices[0] if i < len(self.locations)]
        
    def search_similar_events(self, vector: np.ndarray, k: int = 5) -> List[Event]:
        """Benzer olayları bulur."""
        if self.event_index.ntotal == 0:
            return []
            
        distances, indices = self.event_index.search(np.array([vector]), k)
        return [list(self.events.values())[i] for i in indices[0] if i < len(self.events)]
    
    def save_to_file(self, filename: str = "vector_db_backup.json"):
        """Veritabanı durumunu diske kaydeder."""
        try:
            character_data = [{
                "id": char.id,
                "name": char.name,
                "description": char.description,
                "traits": char.traits,
                "background": char.background,
                "relationships": char.relationships,
                "story_arc": char.story_arc
            } for char in self.characters.values()]
            
            location_data = [{
                "id": loc.id,
                "name": loc.name,
                "description": loc.description,
                "importance": loc.importance,
                "connected_locations": loc.connected_locations
            } for loc in self.locations.values()]
            
            event_data = [{
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "characters_involved": event.characters_involved,
                "location_id": event.location_id,
                "preceding_events": event.preceding_events,
                "following_events": event.following_events,
                "chapter": event.chapter
            } for event in self.events.values()]
            
            data = {
                "characters": character_data,
                "locations": location_data,
                "events": event_data
            }
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Vektör veritabanı durumu {filename} dosyasına kaydedildi.")
        except Exception as e:
            logger.error(f"Veritabanı kaydetme hatası: {e}")

class ConfigParser:
    """Tema yapılandırma dosyasını okur ve işler."""
    
    @staticmethod
    def parse_config(config_path: str) -> StoryConfig:
        """Yapılandırma dosyasını okur ve StoryConfig nesnesi döndürür."""
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        
        try:
            return StoryConfig(
                genre=config.get('Theme', 'genre', fallback='Fantastik'),
                theme=config.get('Theme', 'theme', fallback='Macera'),
                main_plot=config.get('Theme', 'main_plot', fallback='Kahramanın yolculuğu'),
                target_audience=config.get('Theme', 'target_audience', fallback='Yetişkin'),
                chapter_count=config.getint('Structure', 'chapter_count', fallback=250),
                language=config.get('Structure', 'language', fallback='Türkçe'),
                tone=config.get('Style', 'tone', fallback='Dengeli'),
                character_complexity=config.get('Style', 'character_complexity', fallback='Karmaşık')
            )
        except Exception as e:
            logger.error(f"Yapılandırma dosyası okuma hatası: {e}")
            raise

class StoryGenerator:
    """Ana hikaye oluşturma sınıfı."""
    
    def __init__(self, config: StoryConfig, api_key: str):
        """Hikaye oluşturucuyu başlatır."""
        self.config = config
        self.gemini_client = GeminiClient(api_key)
        self.vector_db = VectorDatabase()
        self.chapters: List[Chapter] = []
        
        # Çalışma dizinlerini oluştur
        os.makedirs("output", exist_ok=True)
        os.makedirs("backup", exist_ok=True)
        
    async def generate_vector(self, text: str) -> np.ndarray:
        """Metinden vektör temsili oluşturur."""
        # Basit bir hash tabanlı vektör oluşturma
        # Gerçek uygulamada, embedding modeli kullanılmalıdır
        hash_value = hash(text)
        random.seed(hash_value)
        return np.array([random.random() for _ in range(1536)])
        
    async def create_universe(self) -> None:
        """Hikaye evrenini başlatır."""
        logger.info("Hikaye evreni oluşturuluyor...")
        
        try:
            # Ana plot özetini oluştur
            plot_prompt = f"""
            Aşağıdaki özelliklere sahip bir kitap için ayrıntılı bir ana hikaye/olay örgüsü özeti oluştur:
            - Tür: {self.config.genre}
            - Tema: {self.config.theme}
            - Ana Olay Örgüsü Fikri: {self.config.main_plot}
            - Hedef Kitle: {self.config.target_audience}
            - Bölüm Sayısı: {self.config.chapter_count}
            
            Lütfen şunları içeren detaylı bir özet oluştur:
            1. Ana hikaye yayı
            2. Önemli dönüm noktaları
            3. Çatışma ve çözüm noktaları
            4. Temel tematik unsurlar
            
            Özet, yaklaşık {self.config.chapter_count} bölümlük bir kitabı destekleyecek kadar detaylı olmalıdır.
            """
            
            logger.info("Ana olay örgüsü oluşturuluyor...")
            plot_summary = await self.gemini_client.generate_content(plot_prompt)
            logger.info("Ana olay örgüsü oluşturuldu.")
            
            # Ana karakterleri oluştur
            characters_prompt = f"""
            Az önce oluşturulan şu ana hikaye özetine dayalı olarak:
            {plot_summary}
            
            Bu hikaye için 5-8 ana karakter ve 10-15 yardımcı karakter oluştur. Her karakter aşağıdaki şablonla JSON dizisinde olmalı:
            [
              {{
                "name": "Karakter Adı",
                "description": "Fiziksel ve kişilik özellikleri",
                "traits": ["Özellik1", "Özellik2", "Özellik3"],
                "background": "Karakter geçmişi",
                "relationships": {{"DiğerKarakter1": "İlişki açıklaması", "DiğerKarakter2": "İlişki açıklaması"}},
                "story_arc": "Hikayedeki karakter yayı"
              }},
              // Diğer karakterler
            ]
            
            Karakterler derinlikli, ilgi çekici ve {self.config.character_complexity} olmalıdır.
            Lütfen karakterleri sadece JSON formatında, başka hiçbir açıklama eklemeden döndür.
            """
            
            logger.info("Karakterler oluşturuluyor...")
            
            # JSON hatasını önlemek için daha net bir formatta karakter oluştur
            characters_json = await self.gemini_client.generate_content(characters_prompt)
            
            # Karakterleri işle ve veritabanına ekle
            retry_count = 0
            max_retries = 3
            characters_processed = False
            
            while retry_count < max_retries and not characters_processed:
                try:
                    # JSON'ı temizle - sadece ilk [ ve son ] arasını al
                    cleaned_json = characters_json
                    start_idx = characters_json.find('[')
                    end_idx = characters_json.rfind(']')
                    
                    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                        cleaned_json = characters_json[start_idx:end_idx+1]
                    
                    # JSON ayrıştırmayı dene
                    characters_data = json.loads(cleaned_json)
                    character_count = len(characters_data)
                    logger.info(f"{character_count} karakter oluşturuldu.")
                    
                    # Varsayılan değerlerle karakterleri işle
                    for char_data in tqdm(characters_data, desc="Karakterler işleniyor", unit="karakter"):
                        character = Character(
                            id=str(uuid.uuid4()),
                            name=char_data.get('name', 'İsimsiz Karakter'),
                            description=char_data.get('description', 'Açıklama yok'),
                            traits=char_data.get('traits', []),
                            background=char_data.get('background', 'Geçmiş bilgisi yok'),
                            relationships=char_data.get('relationships', {}),
                            story_arc=char_data.get('story_arc', '')
                        )
                        vector = await self.generate_vector(f"{character.name} {character.description} {character.background}")
                        character.vector = vector
                        self.vector_db.add_character(character, vector)
                    
                    characters_processed = True
                    
                except json.JSONDecodeError as e:
                    retry_count += 1
                    logger.error(f"Karakter JSON'ı ayrıştırılamadı ({retry_count}/{max_retries}): {str(e)}")
                    
                    if retry_count < max_retries:
                        # JSON formatını düzeltmek için daha spesifik bir istek
                        fix_prompt = f"""
                        Lütfen aşağıdaki karakterlerin bilgilerini geçerli bir JSON dizisi olarak yeniden düzenleyin.
                        Yalnızca aşağıdaki formatta karakterleri içeren JSON dizisini döndürün, başka açıklama eklemeyin:
                        
                        [
                          {{
                            "name": "Karakter1", 
                            "description": "Açıklama1",
                            "traits": ["Özellik1", "Özellik2"],
                            "background": "Geçmiş1",
                            "relationships": {{"DiğerKarakter": "İlişki"}},
                            "story_arc": "Arc1"
                          }},
                          {{
                            "name": "Karakter2",
                            "description": "Açıklama2",
                            "traits": ["Özellik1", "Özellik2"],
                            "background": "Geçmiş2",
                            "relationships": {{}},
                            "story_arc": "Arc2"
                          }}
                        ]
                        
                        Lütfen sadece tam bir JSON dizisi dönün, açıklama eklemeyin.
                        """
                        
                        logger.info("Karakter JSON'ı düzeltiliyor...")
                        characters_json = await self.gemini_client.generate_content(fix_prompt)
                    else:
                        # Son çare olarak basit karakter oluştur
                        logger.warning("Maksimum yeniden deneme sayısına ulaşıldı. Temel karakterler oluşturuluyor.")
                        
                        default_characters = [
                            {
                                "name": "Ana Kahraman",
                                "description": "Hikayenin ana kahramanı, cesur ve kararlı bir karakter.",
                                "traits": ["Cesur", "Kararlı", "Dürüst"],
                                "background": "Sıradan bir hayattan maceraya atılan genç.",
                                "relationships": {},
                                "story_arc": "Kahramanın yolculuğu"
                            },
                            {
                                "name": "Akıl Hocası",
                                "description": "Kahramana yol gösteren bilge karakter.",
                                "traits": ["Bilge", "Gizemli", "Yardımsever"],
                                "background": "Uzun yıllar boyunca bilgi biriktirmiş yaşlı bir rehber.",
                                "relationships": {"Ana Kahraman": "Rehber ve öğretmen"},
                                "story_arc": "Kahramana rehberlik etme"
                            },
                            {
                                "name": "Rakip",
                                "description": "Kahramanın yoluna çıkan güçlü rakip.",
                                "traits": ["Hırslı", "Zeki", "Rekabetçi"],
                                "background": "Kendi hedefleri için mücadele eden güçlü karakter.",
                                "relationships": {"Ana Kahraman": "Rakip"},
                                "story_arc": "Rekabet ve çatışma"
                            }
                        ]
                        
                        for char_data in default_characters:
                            character = Character(
                                id=str(uuid.uuid4()),
                                name=char_data["name"],
                                description=char_data["description"],
                                traits=char_data["traits"],
                                background=char_data["background"],
                                relationships=char_data["relationships"],
                                story_arc=char_data["story_arc"]
                            )
                            vector = await self.generate_vector(f"{character.name} {character.description} {character.background}")
                            character.vector = vector
                            self.vector_db.add_character(character, vector)
                        
                        characters_processed = True
            
            # Konumları oluştur
            locations_prompt = f"""
            Az önce oluşturulan şu ana hikaye özetine dayalı olarak:
            {plot_summary}
            
            Bu hikaye için 10-15 önemli konum oluştur. Her konum için şunları belirt:
            - İsim
            - Detaylı açıklama
            - Hikayedeki önemi
            - Bağlantılı diğer konumlar
            
            Konumlar zengin, detaylı ve hikaye türüne ({self.config.genre}) uygun olmalıdır.
            Lütfen konumları JSON formatında döndür.
            """
            
            logger.info("Konumlar oluşturuluyor...")
            locations_json = await self.gemini_client.generate_content(locations_prompt)
            
            # Konumları işle ve veritabanına ekle
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    locations_data = json.loads(locations_json)
                    location_count = len(locations_data)
                    logger.info(f"{location_count} konum oluşturuldu.")
                    
                    for loc_data in tqdm(locations_data, desc="Konumlar işleniyor", unit="konum"):
                        location = Location(
                            id=str(uuid.uuid4()),
                            name=loc_data.get('name', ''),
                            description=loc_data.get('description', ''),
                            importance=loc_data.get('importance', ''),
                            connected_locations=loc_data.get('connected_locations', [])
                        )
                        vector = await self.generate_vector(f"{location.name} {location.description}")
                        location.vector = vector
                        self.vector_db.add_location(location, vector)
                    
                    break  # JSON başarıyla ayrıştırıldı, döngüden çık
                    
                except json.JSONDecodeError:
                    retry_count += 1
                    logger.error(f"Konum JSON'ı ayrıştırılamadı ({retry_count}/{max_retries}), yeniden deneniyor...")
                    
                    # JSON format düzeltme için yeniden istek
                    if retry_count < max_retries:
                        fix_prompt = f"""
                        Lütfen aşağıdaki konum bilgilerini geçerli bir JSON dizisi olarak yeniden formatlayın:
                        
                        {locations_json}
                        
                        Her konum nesnesi şu alanları içermelidir:
                        - name: string
                        - description: string
                        - importance: string
                        - connected_locations: string array
                        
                        Lütfen SADECE JSON formatını döndür, başka açıklama ekleme.
                        """
                        locations_json = await self.gemini_client.generate_content(fix_prompt)
                    else:
                        logger.error("Maksimum yeniden deneme sayısına ulaşıldı. Basit konumlarla devam ediliyor...")
                        # Birkaç varsayılan konum oluştur
                        default_locations = [
                            {"name": "Ana Şehir", "description": "Hikayenin ana mekanı olan büyük şehir", "importance": "Merkezi", "connected_locations": []},
                            {"name": "Orman", "description": "Şehrin dışındaki geniş ve gizemli orman", "importance": "Önemli", "connected_locations": []},
                            {"name": "Dağlar", "description": "Ufukta yükselen heybetli dağlar", "importance": "Arka plan", "connected_locations": []}
                        ]
                        
                        for loc_data in default_locations:
                            location = Location(
                                id=str(uuid.uuid4()),
                                name=loc_data.get('name', ''),
                                description=loc_data.get('description', ''),
                                importance=loc_data.get('importance', ''),
                                connected_locations=loc_data.get('connected_locations', [])
                            )
                            vector = await self.generate_vector(f"{location.name} {location.description}")
                            location.vector = vector
                            self.vector_db.add_location(location, vector)
            
            # Veritabanını diske kaydet
            self.vector_db.save_to_file("backup/universe_data.json")            
            logger.info("Hikaye evreni başarıyla oluşturuldu.")
            
        except Exception as e:
            logger.error(f"Hikaye evreni oluşturma hatası: {str(e)}")
            logger.error(traceback.format_exc())
            # Temel bir hikaye evreni oluştur
            self._create_default_universe()
    
    def _create_default_universe(self):
        """Hata durumunda temel bir hikaye evreni oluşturur."""
        logger.warning("Varsayılan hikaye evreni oluşturuluyor...")
        
        # Basit karakterler ekle
        default_characters = [
            {
                "name": "Ana Kahraman",
                "description": "Hikayenin ana kahramanı, cesur ve kararlı bir karakter.",
                "traits": ["Cesur", "Kararlı", "Dürüst"],
                "background": "Sıradan bir hayattan maceraya atılan genç.",
                "relationships": {},
                "story_arc": "Kahramanın yolculuğu"
            },
            {
                "name": "Akıl Hocası",
                "description": "Kahramana yol gösteren bilge karakter.",
                "traits": ["Bilge", "Gizemli", "Yardımsever"],
                "background": "Uzun yıllar boyunca bilgi biriktirmiş yaşlı bir rehber.",
                "relationships": {"Ana Kahraman": "Rehber ve öğretmen"},
                "story_arc": "Kahramana rehberlik etme"
            },
            {
                "name": "Rakip",
                "description": "Kahramanın yoluna çıkan güçlü rakip.",
                "traits": ["Hırslı", "Zeki", "Rekabetçi"],
                "background": "Kendi hedefleri için mücadele eden güçlü karakter.",
                "relationships": {"Ana Kahraman": "Rakip"},
                "story_arc": "Rekabet ve çatışma"
            }
        ]
        
        # Vektörleri senkron olarak oluştur
        for char_data in default_characters:
            character = Character(
                id=str(uuid.uuid4()),
                name=char_data["name"],
                description=char_data["description"],
                traits=char_data["traits"],
                background=char_data["background"],
                relationships=char_data["relationships"],
                story_arc=char_data["story_arc"]
            )
            # Senkron olarak vektör oluştur
            vector = np.random.rand(1536)
            character.vector = vector
            self.vector_db.add_character(character, vector)
        
        # Basit konumlar ekle
        default_locations = [
            {"name": "Ana Şehir", "description": "Hikayenin ana mekanı olan büyük şehir", "importance": "Merkezi", "connected_locations": []},
            {"name": "Orman", "description": "Şehrin dışındaki geniş ve gizemli orman", "importance": "Önemli", "connected_locations": []},
            {"name": "Dağlar", "description": "Ufukta yükselen heybetli dağlar", "importance": "Arka plan", "connected_locations": []}
        ]
        
        for loc_data in default_locations:
            location = Location(
                id=str(uuid.uuid4()),
                name=loc_data["name"],
                description=loc_data["description"],
                importance=loc_data["importance"],
                connected_locations=loc_data["connected_locations"]
            )
            # Senkron olarak vektör oluştur
            vector = np.random.rand(1536)
            location.vector = vector
            self.vector_db.add_location(location, vector)
        
        logger.info("Varsayılan hikaye evreni oluşturuldu.")
        
    async def generate_story_outline(self) -> List[Dict[str, Any]]:
        """Hikaye taslağını oluşturur."""
        logger.info("Hikaye taslağı oluşturuluyor...")
        
        character_list = "\n".join([
            f"- {char.name}: {char.description[:100]}..." 
            for char in self.vector_db.characters.values()
        ])
        
        location_list = "\n".join([
            f"- {loc.name}: {loc.description[:100]}..." 
            for loc in self.vector_db.locations.values()
        ])
        
        outline_prompt = f"""
        Aşağıdaki bilgilere dayanarak, {self.config.chapter_count} bölümlük bir kitap için ayrıntılı bir taslak oluştur:
        
        Tür: {self.config.genre}
        Tema: {self.config.theme}
        Ana Olay Örgüsü: {self.config.main_plot}
        Ton: {self.config.tone}
        
        Karakterler:
        {character_list}
        
        Konumlar:
        {location_list}
        
        Her bölüm için şunları içeren bir taslak oluştur:
        - Bölüm numarası
        - Bölüm başlığı
        - Kısa özet (2-3 cümle)
        - Bölümde yer alan karakterler (karakter listesinden 2-5 karakter seç)
        - Bölümün geçtiği konum(lar) (konum listesinden 1-3 konum seç)
        - Bölümdeki ana olaylar (2-4 olay)
        
        Taslak, tutarlı bir hikaye ilerleyişi sunmalı ve tam olarak {self.config.chapter_count} bölüme yayılmalıdır.
        Her bölümü ayrı bir nesne olarak içeren geçerli bir JSON dizisi olarak döndür.
        """
        
        outline_json = await self.gemini_client.generate_content(outline_prompt, max_tokens=8192)
        
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                # JSON'ı temizle - sadece ilk ve son köşeli parantez arasını al
                cleaned_json = outline_json
                start_idx = outline_json.find('[')
                end_idx = outline_json.rfind(']')
                
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    cleaned_json = outline_json[start_idx:end_idx+1]
                
                outline_data = json.loads(cleaned_json)
                
                # Bölüm sayısını ayarla
                target_chapter_count = self.config.chapter_count
                actual_chapter_count = len(outline_data)
                
                if actual_chapter_count < target_chapter_count:
                    logger.warning(f"Oluşturulan bölüm sayısı ({actual_chapter_count}) hedeflenen sayıdan ({target_chapter_count}) az. Eksik bölümler oluşturuluyor...")
                    
                    # Son bölümün bilgilerini al
                    last_chapter = outline_data[-1]
                    
                    # Eksik bölümleri oluştur
                    for i in range(actual_chapter_count + 1, target_chapter_count + 1):
                        new_chapter = {
                            "number": i,
                            "title": f"Bölüm {i}",
                            "summary": f"Hikayenin {i}. bölümü",
                            "characters": last_chapter.get("characters", []),
                            "locations": last_chapter.get("locations", []),
                            "events": [f"Olay {i}.1", f"Olay {i}.2"]
                        }
                        outline_data.append(new_chapter)
                
                elif actual_chapter_count > target_chapter_count:
                    logger.warning(f"Oluşturulan bölüm sayısı ({actual_chapter_count}) hedeflenen sayıdan ({target_chapter_count}) fazla. Fazla bölümler çıkarılıyor...")
                    outline_data = outline_data[:target_chapter_count]
                
                # Bölüm numaralarını sırala
                for i, chapter in enumerate(outline_data):
                    chapter["number"] = i + 1
                
                # Outline'ı kaydet
                with open("backup/story_outline.json", "w", encoding="utf-8") as f:
                    json.dump(outline_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Hikaye taslağı oluşturuldu: {len(outline_data)} bölüm")
                return outline_data
                
            except json.JSONDecodeError as e:
                retry_count += 1
                logger.error(f"Taslak JSON'ı ayrıştırılamadı ({retry_count}/{max_retries}), yeniden deneniyor... Hata: {e}")
                
                if retry_count < max_retries:
                    # JSON format düzeltme
                    fix_prompt = f"""
                    Aşağıdaki kitap taslağını düzelt ve geçerli bir JSON olarak yeniden yaz:
                    
                    {outline_json}
                    
                    Her bölüm şu alanları içermeli:
                    - number: number (bölüm numarası)
                    - title: string (bölüm başlığı)
                    - summary: string (kısa özet)
                    - characters: string array (karakter adları)
                    - locations: string array (konum adları)
                    - events: string array (olaylar)
                    
                    Lütfen SADECE JSON dizisini döndür, ekstra metin ekleme. Tam olarak {self.config.chapter_count} bölüm içermeli.
                    """
                    
                    outline_json = await self.gemini_client.generate_content(fix_prompt, max_tokens=8192)
                else:
                    logger.error("Maksimum yeniden deneme sayısına ulaşıldı. Varsayılan taslak oluşturuluyor...")
                    # Basit bir taslak oluştur
                    outline_data = []
                    chars = list(self.vector_db.characters.values())
                    locs = list(self.vector_db.locations.values())
                    
                    char_names = [c.name for c in chars] if chars else ["Ana Karakter"]
                    loc_names = [l.name for l in locs] if locs else ["Ana Mekan"]
                    
                    for i in range(1, self.config.chapter_count + 1):
                        outline_data.append({
                            "number": i,
                            "title": f"Bölüm {i}",
                            "summary": f"Hikayenin {i}. bölümü",
                            "characters": random.sample(char_names, min(3, len(char_names))),
                            "locations": random.sample(loc_names, min(2, len(loc_names))),
                            "events": [f"Olay {i}.1", f"Olay {i}.2"]
                        })
                    
                    # Outline'ı kaydet
                    with open("backup/story_outline_default.json", "w", encoding="utf-8") as f:
                        json.dump(outline_data, f, ensure_ascii=False, indent=2)
                        
                    return outline_data

    async def generate_chapter(self, chapter_outline: Dict[str, Any]) -> Chapter:
        """Belirli bir bölüm için içerik oluşturur."""
        chapter_num = chapter_outline.get('number', 0)
        logger.info(f"Bölüm {chapter_num} oluşturuluyor...")
        
        # Karakterleri topla
        chapter_characters = chapter_outline.get('characters', [])
        character_details = []
        
        for char_name in chapter_characters:
            # Karakter ismini veritabanında ara
            matching_chars = [c for c in self.vector_db.characters.values() if c.name == char_name]
            if matching_chars:
                char = matching_chars[0]
                character_details.append(f"- {char.name}: {char.description}\n  Geçmiş: {char.background[:200]}...")
        
        # Karakterler yoksa veya bulunamadıysa, var olan karakterlerden rastgele ekle
        if not character_details and self.vector_db.characters:
            chars = list(self.vector_db.characters.values())
            selected_chars = random.sample(chars, min(3, len(chars)))
            for char in selected_chars:
                character_details.append(f"- {char.name}: {char.description}\n  Geçmiş: {char.background[:200]}...")
                chapter_characters.append(char.name)
        
        # Konumları topla
        chapter_locations = chapter_outline.get('locations', [])
        location_details = []
        
        for loc_name in chapter_locations:
            # Konum ismini veritabanında ara
            matching_locs = [l for l in self.vector_db.locations.values() if l.name == loc_name]
            if matching_locs:
                loc = matching_locs[0]
                location_details.append(f"- {loc.name}: {loc.description[:200]}...")
        
        # Konumlar yoksa veya bulunamadıysa, var olan konumlardan rastgele ekle
        if not location_details and self.vector_db.locations:
            locs = list(self.vector_db.locations.values())
            selected_locs = random.sample(locs, min(2, len(locs)))
            for loc in selected_locs:
                location_details.append(f"- {loc.name}: {loc.description[:200]}...")
                chapter_locations.append(loc.name)
        
        # Önceki bölümlerin bağlamını al
        previous_chapters_context = ""
        if chapter_num > 1 and self.chapters:
            prev_chapters = [ch for ch in self.chapters if ch.number < chapter_num]
            if prev_chapters:
                last_3_chapters = sorted(prev_chapters, key=lambda x: x.number, reverse=True)[:3]
                for prev_ch in reversed(last_3_chapters):
                    previous_chapters_context += f"\nBölüm {prev_ch.number} - {prev_ch.title}: {prev_ch.summary}\n"
        
        # Karakterleri seçili benzer olaylara bağlama
        related_events = []
        for character_name in chapter_characters:
            if self.vector_db.events:
                events_with_character = [
                    e for e in self.vector_db.events.values() 
                    if character_name in e.characters_involved
                ]
                if events_with_character:
                    # En son 3 olayı al
                    sorted_events = sorted(events_with_character, key=lambda x: x.chapter, reverse=True)[:3]
                    for event in sorted_events:
                        related_events.append(f"- {event.title}: {event.description}")
        
        related_events_str = "\n".join(related_events[:5])  # En fazla 5 ilgili olay
        
        chapter_prompt = f"""
        Aşağıdaki bilgilere dayanarak, bir kitap bölümü oluştur:
        
        Bölüm Numarası: {chapter_outline.get('number')}
        Bölüm Başlığı: {chapter_outline.get('title')}
        Bölüm Özeti: {chapter_outline.get('summary')}
        
        Karakterler:
        {"".join(character_details)}
        
        Konumlar:
        {"".join(location_details)}
        
        Ana Olaylar:
        {', '.join(chapter_outline.get('events', []))}
        
        Önceki Bölümler Bağlamı:
        {previous_chapters_context}
        
        İlgili Geçmiş Olaylar:
        {related_events_str}
        
        Bu bölüm için aşağıdaki özelliklerde içerik oluştur:
        - Akıcı ve sürükleyici anlatım
        - Karakter gelişimini ve motivasyonlarını yansıtan diyaloglar
        - Ayrıntılı mekan tasvirleri
        - Olayların tutarlı bir şekilde ilerlemesi
        - Belirtilen olayları içermeli ama detayları zenginleştirmeli
        - Önceki bölümlere ve geçmiş olaylara doğal referanslar
        
        Bölüm, tamamen Türkçe olarak, yaklaşık 2000-3000 kelime uzunluğunda olmalıdır. Markdown formatında döndür.
        """
        
        # İçerik oluşturma denemeleri
        max_retries = 2
        retry_count = 0
        chapter_content = None
        
        while retry_count <= max_retries and not chapter_content:
            try:
                chapter_content = await self.gemini_client.generate_content(chapter_prompt, max_tokens=8192)
                if not chapter_content or len(chapter_content) < 500:  # Çok kısa içerik, muhtemelen hata var
                    raise ValueError("Üretilen içerik çok kısa veya boş")
            except Exception as e:
                retry_count += 1
                logger.error(f"Bölüm {chapter_num} içerik oluşturma hatası ({retry_count}/{max_retries}): {e}")
                if retry_count <= max_retries:
                    logger.info(f"10 saniye sonra yeniden deneniyor...")
                    await asyncio.sleep(10)
                    # Daha kısa bir prompt dene
                    chapter_prompt = f"""
                    Aşağıdaki bilgilere dayanarak, bir kitap bölümü oluştur:
                    
                    Bölüm Numarası: {chapter_outline.get('number')}
                    Bölüm Başlığı: {chapter_outline.get('title')}
                    Bölüm Özeti: {chapter_outline.get('summary')}
                    
                    Karakterler: {', '.join(chapter_characters)}
                    
                    Konumlar: {', '.join(chapter_locations)}
                    
                    Ana Olaylar: {', '.join(chapter_outline.get('events', []))}
                    
                    Bu bölüm, tamamen Türkçe olarak, akıcı bir anlatımla yazılmalıdır. Markdown formatında döndür.
                    """
                else:
                    # Yeniden deneme başarısız, basit bir içerik oluştur
                    logger.warning("Maksimum yeniden deneme sayısına ulaşıldı. Basit bir bölüm içeriği oluşturuluyor...")
                    chapter_content = f"""
                    # Bölüm {chapter_outline.get('number')}: {chapter_outline.get('title')}
                    
                    {chapter_outline.get('summary')}
                    
                    Bu bölümde, {', '.join(chapter_characters)} karakterleri, {', '.join(chapter_locations)} konumlarında bir araya geldiler. 
                    
                    {', '.join(chapter_outline.get('events', []))} olayları yaşandı.
                    
                    [Otomatik oluşturulan içerik - Tam metin oluşturma başarısız]
                    """
        
        # Bölüm nesnesini oluştur
        chapter = Chapter(
            number=chapter_outline.get('number', 0),
            title=chapter_outline.get('title', ''),
            summary=chapter_outline.get('summary', ''),
            content=chapter_content,
            characters=chapter_characters,
            locations=chapter_locations,
            events=chapter_outline.get('events', [])
        )
        
        # Bu bölümdeki olayları vektör veritabanına ekle
        for event_name in chapter_outline.get('events', []):
            event = Event(
                id=str(uuid.uuid4()),
                title=event_name,
                description=f"Bölüm {chapter.number} olayı: {event_name}",
                characters_involved=chapter.characters,
                location_id=chapter.locations[0] if chapter.locations else "",
                preceding_events=[],  # Önceki olayları eklemek için mantık geliştirilebilir
                following_events=[],
                chapter=chapter.number
            )
            vector = await self.generate_vector(f"{event.title} {event.description}")
            event.vector = vector
            self.vector_db.add_event(event, vector)
        
        # Bölümü kaydet
        chapter_filename = f"output/bolum_{chapter.number:03d}.md"
        with open(chapter_filename, "w", encoding="utf-8") as f:
            f.write(f"# Bölüm {chapter.number}: {chapter.title}\n\n")
            f.write(chapter.content)
        
        logger.info(f"Bölüm {chapter_num} başarıyla oluşturuldu ve {chapter_filename} dosyasına kaydedildi.")
        return chapter
    
    async def generate_full_story(self) -> None:
        """Tüm hikayeyi oluşturur."""
        try:
            # Hikaye evrenini oluştur
            await self.create_universe()
            
            # Hikaye taslağını oluştur
            story_outline = await self.generate_story_outline()
            total_chapters = len(story_outline)
            
            logger.info(f"Toplam {total_chapters} bölüm oluşturulacak.")
            
            # Her bir bölümü oluştur
            progress_bar = tqdm(total=total_chapters, desc="Hikaye İlerlemesi", unit="bölüm")
            
            for chapter_index, chapter_outline in enumerate(story_outline):
                try:
                    # İlerleme bilgisini göster
                    progress_percent = (chapter_index + 1) / total_chapters * 100
                    logger.info(f"İlerleme: {chapter_index+1}/{total_chapters} ({progress_percent:.1f}%)")
                    
                    chapter = await self.generate_chapter(chapter_outline)
                    self.chapters.append(chapter)
                    
                    # Her 5 bölümde bir, ara sonuçları diske kaydet
                    if (chapter_index + 1) % 5 == 0 or chapter_index == total_chapters - 1:
                        self.save_progress()
                        self.vector_db.save_to_file(f"backup/vector_db_chapter_{chapter_index+1}.json")
                    
                    progress_bar.update(1)
                    
                except Exception as e:
                    logger.error(f"Bölüm {chapter_outline.get('number')} oluşturma hatası: {e}")
                    logger.info("Bir sonraki bölüme geçiliyor...")
                    continue
            
            progress_bar.close()
            
            # Kitap son işlemleri
            await self.finalize_book()
            
        except Exception as e:
            logger.error(f"Hikaye oluşturma işleminde kritik hata: {e}")
            # Son durumu kaydet
            self.save_progress()
            self.vector_db.save_to_file("backup/vector_db_error_state.json")
            raise
        
    def save_progress(self) -> None:
        """Mevcut ilerlemeyi diske kaydeder."""
        logger.info("İlerleme kaydediliyor...")
        
        # Mevcut içeriği Markdown olarak kaydet
        with open("output/kitap_taslak.md", "w", encoding="utf-8") as f:
            for chapter in self.chapters:
                f.write(f"# Bölüm {chapter.number}: {chapter.title}\n\n")
                f.write(chapter.content)
                f.write("\n\n---\n\n")
        
        logger.info("İlerleme başarıyla kaydedildi: output/kitap_taslak.md")
    
    async def finalize_book(self) -> None:
        """Nihai kitabı oluşturur ve biçimlendirir."""
        logger.info("Kitap sonlandırılıyor...")
        
        # Kitap başlığı ve ön söz oluştur
        title_prompt = f"""
        Aşağıdaki kitap türü ve teması için etkileyici ve çekici bir kitap başlığı oluştur:
        
        Tür: {self.config.genre}
        Tema: {self.config.theme}
        Ana Olay Örgüsü: {self.config.main_plot}
        
        Başlık Türkçe olmalı ve kitabın özünü yansıtmalıdır.
        """
        
        logger.info("Kitap başlığı oluşturuluyor...")
        book_title = await self.gemini_client.generate_content(title_prompt)
        
        foreword_prompt = f"""
        Aşağıdaki kitap için bir ön söz yaz:
        
        Başlık: {book_title}
        Tür: {self.config.genre}
        Tema: {self.config.theme}
        
        Ön söz, kitabın temasını ve dünyasını tanıtmalı, ancak önemli olayları açık etmemelidir.
        Türkçe olarak yaz ve yaklaşık 500 kelime uzunluğunda olsun.
        """
        
        logger.info("Ön söz oluşturuluyor...")
        foreword = await self.gemini_client.generate_content(foreword_prompt)
        
        # Karakterler listesini oluştur
        characters_summary = []
        for char in self.vector_db.characters.values():
            characters_summary.append(f"### {char.name}\n{char.description}\n\n**Karakter Özellikleri:** {', '.join(char.traits)}\n\n")
        
        # Konumlar listesini oluştur
        locations_summary = []
        for loc in self.vector_db.locations.values():
            locations_summary.append(f"### {loc.name}\n{loc.description}\n\n**Önemi:** {loc.importance}\n\n")
        
        # Karakterler ve dünya hakkında ek bilgiler oluştur
        appendix_prompt = f"""
        Bu kitap için bir ek bölüm oluştur:
        
        1. Dünya/evren haritası veya yapısı açıklaması
        2. Önemli terimler sözlüğü
        3. Kronolojik zaman çizelgesi
        
        Bu ek, okuyucunun hikayeyi daha iyi anlamasına yardımcı olmalıdır.
        Türkçe olarak yaz ve Markdown formatında döndür.
        """
        
        logger.info("Ek bilgiler oluşturuluyor...")
        appendix = await self.gemini_client.generate_content(appendix_prompt)
        
        # Tüm içeriği Markdown olarak birleştir
        logger.info("Kitap içeriği birleştiriliyor...")
        markdown_content = f"""# {book_title}

## Ön Söz

{foreword}

---

"""
        
        # Bölümleri ekle
        for chapter in sorted(self.chapters, key=lambda c: c.number):
            markdown_content += f"# Bölüm {chapter.number}: {chapter.title}\n\n"
            markdown_content += chapter.content
            markdown_content += "\n\n---\n\n"
        
        # Karakter listesini ekle
        markdown_content += f"""
# Karakterler

{"".join(characters_summary)}

# Konumlar

{"".join(locations_summary)}

# Ek Bilgiler

{appendix}
"""
        
        # Markdown dosyasını kaydet
        logger.info("Kitap Markdown olarak kaydediliyor...")
        with open("output/kitap.md", "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # PDF dosyasına dönüştür
        pdf_success = generate_pdf_from_markdown(markdown_content, "output/kitap.pdf")
        
        logger.info("Kitap başarıyla oluşturuldu ve kaydedildi:")
        logger.info("- output/kitap.md (Markdown formatı)")
        if pdf_success:
            logger.info("- output/kitap.pdf (PDF formatı)")
        else:
            logger.warning("PDF oluşturulamadı. Alternatif olarak şunları deneyebilirsiniz:")
            logger.warning("1. 'brew install pango cairo gdk-pixbuf gobject-introspection libffi' komutunu çalıştırın")
            logger.warning("2. Markdown dosyasını bir online dönüştürücü ile PDF'e çevirin")
            logger.warning("3. Pandoc kullanarak dönüştürün: pandoc -s output/kitap.md -o output/kitap.pdf")

# PDF oluşturma yardımcı fonksiyonu
def generate_pdf_from_markdown(markdown_content: str, output_path: str) -> bool:
    """Markdown içeriğinden PDF oluşturur."""
    try:
        # Önce WeasyPrint'i deneyelim
        if HAS_WEASYPRINT:
            try:
                logger.info("WeasyPrint ile PDF oluşturuluyor...")
                html = markdown.markdown(markdown_content)
                HTML(string=html).write_pdf(output_path)
                logger.info(f"PDF başarıyla oluşturuldu: {output_path}")
                return True
            except Exception as e:
                logger.error(f"WeasyPrint hatası: {e}")
                logger.info("Pandoc ile deneniyor...")
        
        # WeasyPrint çalışmazsa, Pandoc'u kullanalım        
        # Geçici markdown dosyası oluştur
        temp_md_path = f"{output_path}.temp.md"
        with open(temp_md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # Pandoc'u çalıştır
        logger.info("Pandoc ile PDF oluşturuluyor...")
        import subprocess
        
        # PATH'i güncelleyelim (TeX binaryleri için)
        env = os.environ.copy()
        env["PATH"] = "/Library/TeX/texbin:" + env["PATH"]
        
        result = subprocess.run(
            ["pandoc", temp_md_path, "-o", output_path, "--pdf-engine=xelatex"],
            capture_output=True,
            text=True,
            env=env
        )
        
        # Geçici dosyayı temizle
        try:
            os.remove(temp_md_path)
        except:
            pass
        
        if result.returncode == 0:
            logger.info(f"PDF başarıyla oluşturuldu: {output_path}")
            return True
        else:
            logger.error(f"Pandoc hatası: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"PDF oluşturma hatası: {e}")
        return False

def create_default_config():
    """Varsayılan yapılandırma dosyasını oluşturur."""
    config = configparser.ConfigParser()
    
    config['Theme'] = {
        'genre': 'Fantastik',
        'theme': 'Macera ve Keşif',
        'main_plot': 'Genç bir kahraman, kayıp bir hazineyi bulmak için tehlikeli bir yolculuğa çıkar.',
        'target_audience': 'Genç Yetişkin'
    }
    
    config['Structure'] = {
        'chapter_count': '250',
        'language': 'Türkçe'
    }
    
    config['Style'] = {
        'tone': 'Dengeli',
        'character_complexity': 'Karmaşık'
    }
    
    with open('theme.config', 'w', encoding='utf-8') as f:
        config.write(f)
    
    print("Varsayılan theme.config dosyası oluşturuldu.")
    print("Hikaye üretimini özelleştirmek için bu dosyayı düzenleyebilirsiniz.")

async def main():
    """Ana program akışı."""
    # Çalışma dizinlerini oluştur
    os.makedirs("output", exist_ok=True)
    os.makedirs("backup", exist_ok=True)
    
    parser = argparse.ArgumentParser(description='Tam yapılandırılmış kitap oluşturucu')
    parser.add_argument('--config', type=str, default='theme.config', help='Yapılandırma dosyası yolu')
    parser.add_argument('--api-key', type=str, help='Gemini API anahtarı (varsayılan: GEMINI_API_KEY çevre değişkeni)')
    parser.add_argument('--chapter-start', type=int, default=1, help='Başlangıç bölüm numarası')
    parser.add_argument('--chapter-end', type=int, default=None, help='Bitiş bölüm numarası')
    args = parser.parse_args()
    
    # .env dosyasının varlığını kontrol et
    if not os.path.exists('.env'):
        print("\nUYARI: .env dosyası bulunamadı. API anahtarını .env dosyasında veya komut satırında belirlemeniz gerekiyor.")
        print("Örnek .env dosyası oluşturuldu. Lütfen GEMINI_API_KEY değerini güncelleyin.")
        
        with open('.env', 'w', encoding='utf-8') as f:
            f.write("# Gemini API anahtarı\nGEMINI_API_KEY=your_api_key_here\n\n# Diğer ayarlar\nLOG_LEVEL=INFO\nMAX_TOKENS=4096\nTEMPERATURE=0.7")
    
    # API anahtarını .env dosyasından, çevre değişkeninden veya argüman olarak verilenden al
    api_key = args.api_key or os.getenv('GEMINI_API_KEY')
    
    if not api_key or api_key == 'your_api_key_here':
        print("\nHata: Geçerli bir Gemini API anahtarı bulunamadı.")
        print("Lütfen aşağıdakilerden birini yapın:")
        print("1. .env dosyasındaki GEMINI_API_KEY değerini güncelleyin")
        print("2. Veya şu komutu kullanın: python story_generator.py --api-key=YOUR_GEMINI_API_KEY")
        sys.exit(1)
    
    # Yapılandırma dosyasını kontrol et, yoksa varsayılanı oluştur
    if not os.path.exists(args.config):
        print(f"\n'{args.config}' dosyası bulunamadı, varsayılan yapılandırma oluşturuluyor...")
        create_default_config()
        print("Lütfen theme.config dosyasını düzenleyerek hikaye ayarlarınızı yapılandırabilirsiniz.")
        print("Değişiklikleri tamamladıktan sonra bu betiği tekrar çalıştırın.")
        sys.exit(0)
    
    try:
        # Yapılandırmayı oku
        config = ConfigParser.parse_config(args.config)
        
        # Hikaye oluşturucuyu başlat
        generator = StoryGenerator(config, api_key)
        
        # Yapılandırma özetini göster
        print("\n" + "="*60)
        print("HİKAYE GENERATİON BAŞLANIYOR")
        print("="*60)
        print(f"Tür: {config.genre}")
        print(f"Tema: {config.theme}")
        print(f"Ana Olay Örgüsü: {config.main_plot}")
        print(f"Hedef Kitle: {config.target_audience}")
        print(f"Bölüm Sayısı: {config.chapter_count}")
        print(f"Dil: {config.language}")
        print(f"Ton: {config.tone}")
        print(f"Karakter Karmaşıklığı: {config.character_complexity}")
        print("-"*60)
        
        # Hikayeyi oluştur
        print("\nHikaye oluşturma işlemi başlatılıyor...")
        print(f"Bu işlem, {config.chapter_count} bölüm için birkaç saat sürebilir.")
        print("İlerleme bilgileri gösterilecek ve ara sonuçlar düzenli olarak kaydedilecektir.")
        print("Lütfen işlemin tamamlanmasını bekleyin...\n")
        
        start_time = time.time()
        await generator.generate_full_story()
        elapsed_time = time.time() - start_time
        
        hours, remainder = divmod(elapsed_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print("\n" + "="*60)
        print("HİKAYE OLUŞTURMA TAMAMLANDI!")
        print("="*60)
        print(f"Toplam süre: {int(hours)} saat, {int(minutes)} dakika, {int(seconds)} saniye")
        print("\nSonuçlar şu dosyalarda kaydedildi:")
        print("- output/kitap.md (Markdown formatı)")
        print("- output/kitap.pdf (PDF formatı)")
        print("\nAyrıca her bölüm ayrı olarak output/ dizininde bulunabilir.")
        print("Yedek dosyalar ve ara çıktılar backup/ dizininde yer almaktadır.")
        
    except Exception as e:
        print(f"\nKritik Hata: {e}")
        print("\nHikaye oluşturma işleminde bir hata oluştu.")
        print("Detaylar için story_generator.log dosyasını kontrol edin.")
        logger.exception("Ana işlem sırasında işlenmemiş hata:")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nİşlem kullanıcı tarafından durduruldu.")
        print("Kısmi çıktılar output/ ve backup/ dizinlerinde bulunabilir.")
        sys.exit(0) 