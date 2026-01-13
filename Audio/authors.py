import sqlite3
import unicodedata
import re
import os
from dataclasses import dataclass
from typing import Optional, List

from Gemini.file_utils import DB2_PATH
DB_PATH = DB2_PATH

@dataclass
class Author:
    id: Optional[int] = None
    main_author_id: Optional[int] = None
    display_name: str = ""
    search_name_norm: str = ""
    name_slug: str = ""
    main_language: Optional[str] = None
    author_image_path: Optional[str] = None
    vita: Optional[str] = None
    stars: int = 0


    @staticmethod
    def create_slug(name: str) -> str:
        """Erstellt einen URL-freundlichen Slug (z.B. Jo Nesbø -> jo-nesbo)."""
        # Normalisierung (zerlegt é in e + accent)
        nfkd_form = unicodedata.normalize('NFKD', name)
        # Filtert alles weg, was kein ASCII ist
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
        # Kleinschreibung und Sonderzeichen durch Bindestrich ersetzen
        slug = re.sub(r'[^\w\s-]', '', only_ascii).strip().lower()
        return re.sub(r'[-\s]+', '-', slug)

    @staticmethod
    def normalize_name(name: str) -> str:
        """Entfernt Akzente für die Suche (z.B. Jo Nesbø -> Jo Nesbo)."""
        return "".join(c for c in unicodedata.normalize('NFKD', name)
                       if not unicodedata.combining(c))

class AuthorManager:
    def __init__(self):
        self.db_path = DB_PATH

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_author_by_name(self, name: str) -> Optional[Author]:
        """Sucht via Normal-Name oder Slug."""
        norm = Author.normalize_name(name)
        query = "SELECT * FROM authors WHERE search_name_norm = ? OR name_slug = ?"
        with self._get_conn() as conn:
            row = conn.execute(query, (norm, Author.create_slug(name))).fetchone()
            return Author(**dict(row)) if row else None

    def update_author(self, author: Author):
        """Aktualisiert alle Metadaten (Vita, Image, etc.)."""
        query = """
            UPDATE authors SET 
                main_author_id = ?, display_name = ?, search_name_norm = ?, 
                main_language = ?, author_image_path = ?, vita = ?, 
                stars = ?
            WHERE id = ?
        """
        with self._get_conn() as conn:
            conn.execute(query, (
                author.main_author_id, author.display_name, author.search_name_norm,
                author.main_language, author.author_image_path, author.vita,
                author.stars, author.id
            ))

    def add_author(self, author: Author) -> int:
        """Fügt einen Autor hinzu. Wenn author.id gesetzt ist, wird diese erzwungen."""
        if not author.name_slug:
            author.name_slug = Author.create_slug(author.display_name)
        if not author.search_name_norm:
            author.search_name_norm = Author.normalize_name(author.display_name)

        # Dynamische Abfrage: Falls ID vorhanden, nehmen wir sie mit ins INSERT
        fields = ["display_name", "search_name_norm", "name_slug", "main_language", "stars"]
        values = [author.display_name, author.search_name_norm, author.name_slug, author.main_language,
                  author.stars]

        if author.id is not None:
            fields.insert(0, "id")
            values.insert(0, author.id)

        placeholders = ", ".join(["?"] * len(values))
        query = f"INSERT INTO authors ({', '.join(fields)}) VALUES ({placeholders})"

        with self._get_conn() as conn:
            cursor = conn.execute(query, values)
            # Falls wir keine ID mitgegeben hatten, holen wir die neue von der DB
            if author.id is None:
                author.id = cursor.lastrowid
            return author.id