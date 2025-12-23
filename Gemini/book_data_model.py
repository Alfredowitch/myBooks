# In book_data_model.py

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict, Any
import json


@dataclass
class BookMetadata:
    # ... (Alle bestehenden Felder bleiben hier) ...
    book_id: Optional[int] = field(default=None)  # DB-ID
    file_path: Optional[str] = field(default=None)
    title: Optional[str] = field(default=None)
    authors: List[Tuple[str, str]] = field(default_factory=list)  # Liste von (Vorname, Nachname)

    # KERN-METADATEN
    isbn: Optional[str] = field(default=None)
    year: Optional[str] = field(default=None)
    language: Optional[str] = field(default=None)
    series_name: Optional[str] = field(default=None)
    series_number: Optional[str] = field(default=None)

    # INHALTLICHE DATEN
    description: Optional[str] = field(default=None)  # Klappentext (aus EPUB oder API)
    keywords: List[str] = field(default_factory=list)  # Keywords/Subjects (aus EPUB)
    genre: Optional[str] = field(default=None)  # Unser gemapptes/manuelles Genre
    region: Optional[str] = field(default=None)
    notes: Optional[str] = field(default=None)  # Manuelle Notizen

    # RATING/STATUS
    stars: Optional[int] = field(default=None)  # Manuelle Sterne
    is_read: Optional[int] = field(default=0)
    is_complete: Optional[int] = field(default=0)
    average_rating: Optional[float] = field(default=None)  # API-Rating
    ratings_count: Optional[int] = field(default=None)  # API-Count

    # TEMPORÄRE DATEN
    temp_image_path: Optional[str] = field(default=None)  # Pfad zur temporären Cover-Datei

    # --- HILFSMETHODEN ---

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Erstellt eine Instanz aus einem Dictionary, ignoriert unbekannte Schlüssel."""
        # Nur Schlüssel verwenden, die im Dataclass definiert sind
        valid_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}

        # Spezielle Behandlung für Autoren und Keywords, falls sie None sind
        if 'authors' in filtered_data and filtered_data['authors'] is None:
            filtered_data['authors'] = []
        if 'keywords' in filtered_data and filtered_data['keywords'] is None:
            filtered_data['keywords'] = []

        return cls(**filtered_data)

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
        return False

    def merge_with(self, other_metadata: 'BookMetadata'):
        """
        Führt Metadaten aus einem anderen BookMetadata-Objekt in dieses Objekt zusammen.
        Es werden nur Felder überschrieben, die in diesem Objekt (self) leer sind.
        Dies stellt sicher, dass die primäre Quelle (z.B. Dateiname) immer Vorrang hat.
        """

        # Iteriere über die Attribute des anderen Objekts
        for field_name, other_value in asdict(other_metadata).items():

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
            # sollte temp_image_path von der EPUB-Quelle immer übernommen werden,
            # solange der Wert nicht None ist (unabhängig davon, ob er schon gesetzt wurde).
            # Wir nehmen an, dass read_epub die einzige Quelle dafür ist.
            if field_name == 'temp_image_path' and other_value is not None:
                setattr(self, field_name, other_value)

    def to_dict(self) -> dict:
        """Konvertiert das Objekt zurück in ein Dictionary für Legacy-Funktionen."""
        return {
            'file_path': self.file_path,
            'title': self.title,
            'authors': self.authors,  # Bleibt Liste von Tupeln
            'series_name': self.series_name,
            'series_number': self.series_number,
            'isbn': self.isbn,
            'genre': self.genre,
            'year': self.year,
            'language': self.language,
            'region': self.region,
            'description': self.description,
            'average_rating': self.average_rating,
            'ratings_count': self.ratings_count,
            'stars': self.stars,
            'is_read': self.is_read,
            'is_complete': self.is_complete,
            'temp_image_path': self.temp_image_path,
            'notes': self.notes,
            # Falls du 'categories' oder 'genre_epub' nutzt, hier auch aufnehmen:
            'categories': getattr(self, 'categories', []),
            'genre_epub': getattr(self, 'genre_epub', None)
        }

# WICHTIG: Stelle sicher, dass `fields` importiert wird (aus dataclasses)
from dataclasses import fields