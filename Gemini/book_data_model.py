"""
DATEI: book_data_model.py
PROJEKT: MyBook-Management (v1.1.0)
BESCHREIBUNG: Definiert Metadaten zum Austausch mit allen Funktionen.
              BookData ist daher größer als die Datenbank und dient als Daten-Container
              In Merge werden alle Daten in die Strukturen der Datenbank gepresst.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict, Any
import json


@dataclass
class BookData:
    # SYSTEM & DATEI (Hier ist None okay, da intern genutzt)
    id: int = 0  # Statt book_id
    path: str = ""  # Statt file_path
    scanner_version: str = "1.0.0"

    # TITEL & AUTOR
    title: str = ""
    authors: List[Tuple[str, str]] = field(default_factory=list)

    # KERN-METADATEN (Strings sind besser als "" statt None für GUI)
    isbn: str = ""
    year: str = ""
    language: str = ""
    series_name: str = ""
    series_number: str = ""

    # INHALTLICHE DATEN
    description: str = ""             # Immer ein String, nie None
    is_manual_description: int = 0    # Dein neues Schutz-Flag (0 oder 1)
    notes: str = ""
    keywords: List[str] = field(default_factory=list)
    genre: str = ""
    region: str = ""

    # HILFSFELDER
    categories: List[str] = field(default_factory=list)
    genre_epub: str = ""

    # RATING/STATUS (Integer statt None verhindert Rechenfehler)
    stars: int = 0
    is_read: int = 0
    is_complete: int = 0
    average_rating: float = 0.0
    ratings_count: int = 0

    # BILDER
    image_path: str = ""  # Statt temp_image_path

    # --- HILFSMETHODEN der Klasse also zum Bauen---
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Erstellt eine Instanz aus einem Dictionary, ignoriert unbekannte Schlüssel."""
        if not data:
            return cls()  # return leeres BookData()
        # Nur Schlüssel verwenden, um ein Set aus den Attributnamen von BookMetaData zu liefern.
        valid_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}

        # Spezielle Behandlung für Autoren und Keywords, falls sie None sind
        if 'authors' in filtered_data and filtered_data['authors'] is None:
            filtered_data['authors'] = []
        if 'keywords' in filtered_data and filtered_data['keywords'] is None:
            filtered_data['keywords'] = []

        return cls(**filtered_data)

    # --- HILFSMETHODEN der Instanz also zum Nutzen oder Bearbeiten bestehender Instanzen---
    def to_dict(self):
        # Erstelle automatisch das komplette Dictionary
        d = asdict(self)
        return d

    def is_field_empty(self, value):
        """Prüft, ob ein Wert als leer (None, leerer String, leere Liste) gilt."""
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, list) and not value:
            return True
        if isinstance(value, tuple) and not value:
            return True
        # WICHTIG: 0 (für ID oder Ratings) oder False (is_read)
        # gelten hier NICHT als leer!
        return False

    def merge_with(self, other_metadata: 'BookData'):
        """
        Führt Metadaten aus einem anderen BookData-Objekt in dieses Objekt zusammen.
        Es werden nur Felder überschrieben, die in diesem Objekt (self) leer sind.
        Dies stellt sicher, dass die primäre Quelle (z.B. Dateiname) immer Vorrang hat.
        """
        if not other_metadata:
            return

        # Diese Felder dürfen NIEMALS durch einen automatischen Scan überschrieben werden,
        # wenn sie im Hauptobjekt (self) bereits einen Wert haben.
        protected_fields = ['id', 'db_id', 'is_read', 'scanner_version', 'stars', 'notes']

        # Iteriere über die Attribute (getattr(self, field_name)) des anderen Objekt,
        # das mit asdict(other_metadata) kurzzeitig ein Dictionary wird.
        for field_name, other_value in asdict(other_metadata).items():
            # 1. Schutz-Check: Schutzschalter für die Identität
            if field_name in protected_fields:
                # Wenn wir schon eine ID oder ein 'Gelesen'-Status haben, ignorieren wir das 'Other'
                current_val = getattr(self, field_name, None)
                if not self.is_field_empty(current_val):
                    continue
            # Hole den aktuellen Wert dieses Objekts
            current_value = getattr(self, field_name, None)
            # Prüfe, ob das aktuelle Feld als "leer" gilt (wird von der höheren Priorität nicht geliefert)
            if self.is_field_empty(current_value):
                # Prüfe, ob der Wert des anderen Objekts als "gültig" gilt (ist nicht leer)
                if not self.is_field_empty(other_value):
                    # Überschreibe nur, wenn das aktuelle Feld leer ist und das andere Feld einen Wert hat
                    setattr(self, field_name, other_value)
            # SPEZIALFALL: temp_image_path
            # Da Bilder groß sind und die temporäre Datei von read_epub erstellt wird,
            # sollte image_path von der EPUB-Quelle immer übernommen werden
            if field_name == 'image_path' and other_value is not None:
                setattr(self, field_name, other_value)

        # LOGIK FÜR DAS GENRE-BACKUP
        if self.is_field_empty(self.genre):
            # 1. Versuch: epub_genre nutzen
            if not self.is_field_empty(other_metadata.genre_epub):
                self.genre = other_metadata.genre_epub
                print(f"     [!] Genre leer -> '{self.genre}' aus EPUB-Genre gesetzt.")
            # 2. Versuch (falls immer noch leer): Erste Kategorie nutzen
            elif other_metadata.categories:
                self.genre = other_metadata.categories[0]
                print(f"     [!] Genre leer -> '{self.genre}' aus Kategorien gesetzt.")
        # DATEN-SAMMLER: Alles in Keywords werfen, was keine eigene Spalte hat
        # aus categories -> keywords
        if other_metadata.categories:
            for cat in other_metadata.categories:
                if cat not in self.keywords:  # Dubletten vermeiden
                    self.keywords.append(cat)
        if other_metadata.genre_epub and other_metadata.genre_epub not in self.keywords:
            self.keywords.append(other_metadata.genre_epub)

# WICHTIG: Stelle sicher, dass `fields` importiert wird (aus dataclasses)
from dataclasses import fields