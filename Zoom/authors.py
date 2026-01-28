import inspect
import sqlite3
import unicodedata
import re
import os
from dataclasses import dataclass
from collections import defaultdict  # Das hat gefehlt!
from typing import Optional, List

from Zoom.utils import DB_PATH


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
    def merge_authors_from_file(fix_file="author_fixes.txt"):
        # Sicherstellen, dass der Pfad relativ zum Skript gefunden wird
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, fix_file)

        if not os.path.exists(file_path):
            print(f"❌ Datei nicht gefunden: {file_path}")
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Statistik-Zähler
        merged_count = 0
        books_moved = 0

        try:
            # 'latin-1' fängt Windows-Sonderzeichen (0xe8 etc.) sicher ab
            with open(file_path, 'r', encoding='latin-1') as f:
                for line in f:
                    line = line.strip()
                    if not line or ';' not in line:
                        continue

                    parts = [p.strip() for p in line.split(';') if p.strip()]
                    if len(parts) < 2:
                        continue

                    winner_name = parts[0]
                    losers_names = parts[1:]

                    # 1. ID des Gewinners finden (Suche über kombinierten Namen)
                    cursor.execute("""
                        SELECT id FROM authors 
                        WHERE (firstname || ' ' || lastname) = ? 
                           OR (lastname || ' ' || firstname) = ?
                           OR lastname = ?
                    """, (winner_name, winner_name, winner_name))

                    res = cursor.fetchone()
                    if not res:
                        print(f"⚠️ Gewinner '{winner_name}' nicht in DB gefunden.")
                        continue
                    winner_id = res[0]

                    for loser_name in losers_names:
                        # 2. ID des Verlierers finden
                        cursor.execute("""
                            SELECT id FROM authors 
                            WHERE (firstname || ' ' || lastname) = ?
                               OR (lastname || ' ' || firstname) = ?
                               OR lastname = ?
                        """, (loser_name, loser_name, loser_name))
                        res_loser = cursor.fetchone()

                        if not res_loser:
                            continue

                        loser_id = res_loser[0]
                        if winner_id == loser_id:
                            continue

                        # 3. Bücher umhängen in allen relevanten Tabellen
                        for table in ['book_authors', 'book_locations']:
                            try:
                                # Update auf neue ID, IGNORE verhindert Fehler bei Dubletten
                                cursor.execute(f"UPDATE OR IGNORE {table} SET author_id = ? WHERE author_id = ?",
                                               (winner_id, loser_id))
                                books_moved += cursor.rowcount
                                # Alte Verknüpfungen löschen
                                cursor.execute(f"DELETE FROM {table} WHERE author_id = ?", (loser_id,))
                            except sqlite3.OperationalError:
                                continue

                        # 4. Den redundanten Autor löschen
                        cursor.execute("DELETE FROM authors WHERE id = ?", (loser_id,))
                        merged_count += 1
                        print(f"✅ Merged: {loser_name} -> {winner_name}")

            conn.commit()
            print(f"\nBereinigung fertig. {merged_count} Autoren entfernt, {books_moved} Buch-Links korrigiert.")

        except Exception as e:
            print(f"❌ Fehler: {e}")
        finally:
            conn.close()

    @staticmethod
    def find_remaining_collisions():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Wir laden alle Autoren
        cursor.execute("SELECT id, firstname, lastname FROM authors")
        authors = cursor.fetchall()

        slug_map = defaultdict(list)
        for auth in authors:
            full_name = f"{auth['firstname'] or ''} {auth['lastname'] or ''}".strip()

            # Nacktschnecken-Logik (muss exakt so sein wie im Haupt-Skript)
            slug = unicodedata.normalize('NFKD', full_name).encode('ASCII', 'ignore').decode('ASCII')
            slug = re.sub(r'[^\w\s-]', '', slug).strip().lower()
            slug = re.sub(r'[-\s]+', '-', slug)

            # Wir speichern ID und Name
            slug_map[slug].append({'id': auth['id'], 'name': full_name})

        print(f"{'SLUG':<30} | {'ID':<6} | {'NAME'}")
        print("-" * 60)

        found = False
        for slug, entries in slug_map.items():
            if len(entries) > 1:
                found = True
                for i, entry in enumerate(entries):
                    # Der erste in der Liste pro Slug bekommt einen Marker
                    prefix = "[WINNER]" if i == 0 else "[LOSER] "
                    print(f"{slug:<30} | {entry['id']:<6} | {prefix} {entry['name']}")
                print("-" * 60)

        if not found:
            print("Keine Kollisionen mehr gefunden! Du kannst den Slug-Generator jetzt starten.")

        conn.close()

    @staticmethod
    def merge_authors_by_id(winner_id, loser_id):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Alle potenziellen Tabellennamen, die Autoren-Links enthalten könnten
        possible_tables = ['book_authors', 'work_author', 'book_locations', 'work_to_author']

        print(f"Schmelze ID {loser_id} in ID {winner_id}...")

        for table in possible_tables:
            try:
                # Prüfen, ob Tabelle existiert
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if cursor.fetchone():
                    # Erst umhängen (IGNORE verhindert Fehler bei bereits existierenden Links)
                    cursor.execute(f"UPDATE OR IGNORE {table} SET author_id = ? WHERE author_id = ?",
                                   (winner_id, loser_id))
                    moved = cursor.rowcount
                    # Dann die Reste vom Loser löschen (falls IGNORE gegriffen hat)
                    cursor.execute(f"DELETE FROM {table} WHERE author_id = ?", (loser_id,))
                    if moved > 0:
                        print(f"  - {moved} Einträge in '{table}' korrigiert.")
            except sqlite3.Error as e:
                print(f"  - Fehler in Tabelle {table}: {e}")

        # Zum Schluss den doppelten Autor löschen
        cursor.execute("DELETE FROM authors WHERE id = ?", (loser_id,))

        conn.commit()
        conn.close()
        print(f"✅ ID {loser_id} erfolgreich entfernt.")

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

    import inspect

    def get_author(self, author_id: int) -> Optional[Author]:
        query = "SELECT * FROM authors WHERE id = ?"
        with self._get_conn() as conn:
            row = conn.execute(query, (author_id,)).fetchone()
            if not row:
                return None
            # Umwandeln in Dictionary
            row_dict = dict(row)
            # Nur die Felder nehmen, die die Klasse Author auch wirklich hat
            sig = inspect.signature(Author)
            valid_keys = sig.parameters.keys()
            filtered_dict = {k: v for k, v in row_dict.items() if k in valid_keys}
            return Author(**filtered_dict)

    def get_top_30_authors(self):
        query = """
            SELECT 
                a.id, 
                (a.firstname || ' ' || a.lastname) as display_name,
                COUNT(DISTINCT b.id) as total,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'de' THEN b.id END) as de,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'en' THEN b.id END) as en,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'fr' THEN b.id END) as fr,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'it' THEN b.id END) as it,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'es' THEN b.id END) as es
            FROM authors a
            JOIN work_author wa ON a.id = wa.author_id
            JOIN work_to_book wtb ON wa.work_id = wtb.work_id
            JOIN books b ON wtb.book_id = b.id
            GROUP BY a.id
            ORDER BY total DESC
            LIMIT 30
        """
        try:
            with self._get_conn() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query).fetchall()
                # Umwandeln in Liste von Dicts für die GUI
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Datenbank-Fehler im Manager: {e}")
            return []


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

