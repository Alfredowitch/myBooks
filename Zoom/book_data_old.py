"""
DATEI: book_data_old.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Container-Klasse (BookData) mit Proxy-Properties.
              v1.5.0 unterstützt nun natives Laden via ID und Pfad sowie
              das Erzeugen von leeren Objekten für die Neu-Anlage.
"""

import sqlite3
import os
import re
from dataclasses import dataclass, asdict, fields
from typing import List, Optional, Tuple, Union, Any
from Gemini.file_utils import DB_PATH, sanitize_path, slugify


@dataclass
class SerieTData:
    id: int = 0
    name: str = ""
    name_de: str = ""
    name_en: str = ""
    name_fr: str = ""
    name_it: str = ""
    name_es: str = ""
    slug: str = ""
    link: str = ""
    notes: str = ""


@dataclass
class WorkTData:
    id: int = 0
    series_id: int = 0
    series_index: float = 0.0
    title: str = ""
    title_de: str = ""
    title_en: str = ""
    title_fr: str = ""
    title_it: str = ""
    title_es: str = ""
    slug: str = ""
    genre: str = ""
    regions: str = ""
    keywords: str = ""
    description: str = ""
    rating: float = 0.0  # Externer Durchschnitt (Konsolidiert)
    stars: int = 0  # Deine persönliche Bewertung (0-10)
    notes: str = ""


@dataclass
class BookTData:
    id: int = 0
    work_id: int = 0
    path: str = ""
    title: str = ""
    ext: str = ""
    isbn: str = ""
    language: str = ""
    year: str = ""
    image_path: str = ""
    genre: str = ""
    regions: str = ""
    keywords: str = ""
    rating_ol: float=0.0
    rating_ol_count: int= 0
    rating_g: float=0.0
    rating_g_count: int= 0
    stars: int = 0
    is_read: int = 0
    is_complete: int = 0
    scanner_version: str = "1.5.0"
    series_name: str = ""
    series_number: str = ""
    notes: str = ""
    description: str = ""

    def merge_with(self, data: Union[dict, 'BookTData']):
        """Schreibt Daten direkt in die Attribute dieses Atoms."""
        if not data:
            return

        # Falls wir ein anderes Atom oder ein BookData bekommen, zu Dict wandeln
        if hasattr(data, 'book'):  # Es ist ein BookData Manager
            source = asdict(data.book)
        elif hasattr(data, '__dataclass_fields__'):  # Es ist ein BookTData Atom
            source = asdict(data)
        else:  # Es ist bereits ein Dictionary
            source = data

        # Mapping für Scanner-Felder, die anders heißen als im Atom
        mappings = {
            'extension': 'ext',
            'epub_title': 'title',
            'file_title': 'title',
            'series_index': 'series_number'
        }

        for key, value in source.items():
            if value is None or value == "":
                continue

            # Key übersetzen falls nötig
            target_key = mappings.get(key, key)

            if hasattr(self, target_key):
                setattr(self, target_key, value)
            else:
                # Optional: Unbekannte Felder für spätere Analyse loggen
                # print(f"DEBUG: Feld {target_key} wird ignoriert.")
                pass

class BookData:
    def __init__(self,
                 book: Optional[BookTData] = None,
                 work: Optional[WorkTData] = None,
                 serie: Optional[SerieTData] = None,
                 path: Optional[str] = None):  # 'path' hier als Rettungsanker

        # 1. Atome initialisieren (entweder übergeben oder neue leere Dataclasses)
        self.book = book or BookTData()
        self.work = work or WorkTData()
        self.serie = serie or SerieTData()

    def migrate_from_atom(self):
        """
        Integrierte Migrationslogik (vormalig migration.py):
        Überführt flache Atom-Daten in die Werk- und Serienstruktur.
        """
        # 1. Serien-Logik (Kürzel-Mapping & Regex aus migration.py)
        if not self.book.series_name and self.book.path:
            # Fallback: '01-' oder 'name01-' im Pfad suchen
            match = re.search(r'(\d{1,3}-| - \d{1,3} -)', self.book.path)
            if match and self.authors:
                # Nutzt den Nachnamen des ersten Autors als Serienname (migration.py Logik)
                self.book.series_name = self.authors[0][1]

        if self.book.series_name:
            mapping = {"hp": "Harry Potter", "pjo": "Percy Jackson", "lotr": "Lord of the Rings"}
            norm_name = mapping.get(self.book.series_name.lower(), self.book.series_name)
            self.serie.name = norm_name
            self.serie.slug = slugify(norm_name)

        # 2. Werk-Logik & Konsolidierung
        # Wenn kein Werk-Titel da ist, nehmen wir den Buch-Titel
        self.work.title = self.book.title
        self.work.slug = slugify(self.work.title)

        # Sterne-Migration (Phase 2 der migration.py)
        if self.book.stars > self.work.stars:
            self.work.stars = self.book.stars

        # Beschreibung (Längere Beschreibung gewinnt)
        if len(self.book.description or "") > len(self.work.description or ""):
            self.work.description = self.book.description


    # ----------------------------------------------------------------------
    # KOMPATIBILITÄTSLAYER (v1.3 -> v1.5)
    # ----------------------------------------------------------------------
    @property
    def title(self): return self.book.title
    @title.setter
    def title(self, v): self.book.title = v

    @property
    def year(self): return self.book.year
    @year.setter
    def year(self, v): self.book.year = v

    @property
    def series_name(self): return self.book.series_name
    @series_name.setter
    def series_name(self, v): self.book.series_name = v

    @property
    def series_number(self): return self.book.series_number
    @series_number.setter
    def series_number(self, v):
        self.book.series_number = v
        try:
            if v: self.work.series_index = float(str(v).replace(',', '.'))
        except: pass

    @property
    def path(self): return self.book.path
    @path.setter
    def path(self, v): self.book.path = v

    @property
    def extension(self): return self.book.ext
    @extension.setter
    def extension(self, v): self.book.ext = v

    @property
    def isbn(self): return self.book.isbn
    @isbn.setter
    def isbn(self, v): self.book.isbn = v

    @property
    def language(self): return self.book.language
    @language.setter
    def language(self, v): self.book.language = v

    @property
    def work_id(self): return self.book.work_id
    @work_id.setter
    def work_id(self, v): self.book.work_id = v

    @property
    def is_complete(self) -> int:
        """Gibt den Vollständigkeits-Status aus dem Buch-Atom zurück."""
        return self.book.is_complete

    @is_complete.setter
    def is_complete(self, value: int):
        """Erlaubt das Setzen des Status direkt über den Manager."""
        self.book.is_complete = value

    # Falls der Scanner auch scanner_version direkt anspricht:
    @property
    def scanner_version(self) -> str:
        return self.book.scanner_version

    @scanner_version.setter
    def scanner_version(self, value: str):
        self.book.scanner_version = value

    # ----------------------------------------------------------------------
    # FABRIK-METHODEN (Laden & Erstellen)
    # ----------------------------------------------------------------------
    @classmethod
    def load_by_id(cls, book_id: int) -> Optional['BookData']:
        """Sucht das Buch erst per ID und delegiert dann an load_by_path."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM books WHERE id = ?", (book_id,))
        res = cursor.fetchone()
        conn.close()
        if res:
            return cls.load_by_path(res[0])
        return None

    @classmethod
    def load_by_path(cls, file_path: str) -> Optional['BookData']:
        """Lädt ein komplettes Aggregat aus der Datenbank via Pfad."""
        clean_path = sanitize_path(file_path)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = """
            SELECT b.*, 
                   w.id as w_id, w.series_id as w_sid, w.series_index as w_sidx, w.title as w_title, 
                   w.title_de as w_tde, w.title_en as w_ten, w.title_fr as w_tfr, w.title_es as w_tes, w.title_it as w_tit,
                   w.genre as w_genre, w.regions as w_regions, w.keywords as w_keywords,
                   w.description as w_desc, w.rating as w_rating, w.stars as w_stars, w.notes as w_notes,
                   s.id as s_id, s.name as s_name, s.name_de as s_de, s.name_en as s_en, 
                   s.name_fr as s_fr, s.name_es as s_es, s.name_it as s_it,
                   s.slug as s_slug, s.link as s_link, s.notes as s_notes
            FROM books b
            LEFT JOIN works w ON b.work_id = w.id
            LEFT JOIN series s ON w.series_id = s.id
            WHERE b.path = ?
        """
        cursor.execute(sql, (clean_path,))
        res = cursor.fetchone()
        if not res:
            conn.close()
            return None

        row = dict(res)
        # Atome befüllen mit Mapping der Aliase
        s_atom = SerieTData(
            id=row['s_id'] or 0, name=row['s_name'] or "",
            name_de=row['s_de'] or "", name_en=row['s_en'] or "",
            name_fr=row['s_fr'] or "", name_es=row['s_es'] or "", name_it=row['s_it'] or "",
            slug=row['s_slug'] or "", link=row['s_link'] or "", notes=row['s_notes'] or ""
        )
        w_atom = WorkTData(
            id=row['w_id'] or 0, series_id=row['w_sid'] or 0, series_index=row['w_sidx'] or 0.0,
            title=row['w_title'] or "", title_de=row['w_tde'] or "", title_en=row['w_ten'] or "",
            title_fr=row['w_tfr'] or "", title_es=row['w_tes'] or "", title_it=row['w_tit'] or "",
            genre=row['w_genre'] or "", regions=row['w_regions'] or "", keywords=row['w_keywords'] or "",
            description=row['w_desc'] or "", rating=row['w_rating'] or "", stars=row['w_stars'] or 0,
            notes=row['w_notes'] or ""
        )
        # Buch-Atom: Nutzt die dataclass Felder für automatisches Mapping
        b_dict = {}
        for f in fields(BookTData):
            if f.name in row: b_dict[f.name] = row[f.name]
        b_atom = BookTData(**b_dict)

        mgr = cls(book=b_atom, work=w_atom, serie=s_atom)
        # Autoren laden
        cursor.execute("""
            SELECT a.firstname, a.lastname FROM authors a
            JOIN work_to_author wa ON a.id = wa.author_id
            WHERE wa.work_id = ?
        """, (w_atom.id,))
        mgr.authors = [(r[0], r[1]) for r in cursor.fetchall()]
        conn.close()
        return mgr

    @classmethod
    def create_empty(cls, path: str) -> 'BookData':
        """Erzeugt ein minimales, valides Aggregat für eine Neu-Anlage."""
        b_atom = BookTData(path=path, title=os.path.basename(path), id=0)
        return cls(book=b_atom)

    # ----------------------------------------------------------------------
    # SPEICHER-LOGIK
    # ----------------------------------------------------------------------
    def calculate_consolidated_rating(self):
        """Berechnet das gewichtete Rating aus Google und OpenLibrary."""
        b = self.book
        total_count = b.rating_ol_count + b.rating_g_count
        if total_count > 0:
            # Gewichteter Durchschnitt: (Wert1 * Anzahl1 + Wert2 * Anzahl2) / Gesamtanzahl
            weighted_sum = (b.rating_ol * b.rating_ol_count) + (b.rating_g * b.rating_g_count)
            self.work.rating = round(weighted_sum / total_count, 2)
        elif b.rating_ol > 0 or b.rating_g > 0:
            # Falls Counts fehlen, aber Werte da sind: Einfacher Durchschnitt
            vals = [v for v in [b.rating_ol, b.rating_g] if v > 0]
            self.work.rating = round(sum(vals) / len(vals), 2)

    def save(self) -> bool:
        # 1. DIAGNOSE-BLOCK (Um den Geister-Fehler zu fangen)
        print(f"\n--- DEBUG SAVE START ---")
        print(f"Instanz-Typ: {type(self)}")
        print(f"Attribute im Objekt: {[a for a in dir(self) if not a.startswith('__')]}")

        if not hasattr(self, 'book') or self.book is None:
            print("❌ KRITISCH: 'self.book' fehlt oder ist None vor dem Speichern!")
            # Wir versuchen zu retten, was zu retten ist, oder brechen sauber ab
            return False

        try:
            """Berechnet vorher das konsolidierte Rating."""
            self.calculate_consolidated_rating()
            # Sicherer Zugriff auf stars
            if hasattr(self.book, 'stars') and self.book.stars > 0:
                self.work.stars = self.book.stars

            """Speichert alle drei Atome und die Autoren-Verknüpfung."""
            from dataclasses import asdict  # Sicherstellen, dass asdict verfügbar ist

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row  # Hilft bei der Fehlersuche
            cursor = conn.cursor()

            # 1. SERIE
            if self.serie and self.serie.name:
                # Wir suchen die Serie.
                # Falls wir später Autoren-Trennung wollen, käme hier: AND author_id = ...
                cursor.execute("SELECT id FROM series WHERE name = ?", (self.serie.name,))
                row = cursor.fetchone()
                if row:
                    # Wir haben eine passende Serie gefunden
                    self.serie.id = row[0]
                    # Wir updaten sie nur, wenn wir sicher sind (z.B. im Browser-Edit)
                    # Ansonsten nehmen wir einfach nur die ID für die Verknüpfung
                else:
                    # Nur wenn der Name absolut unbekannt ist, legen wir neu an
                    try:
                        cursor.execute("INSERT INTO series (name, slug) VALUES (?,?)",
                                       (self.serie.name, slugify(self.serie.name)))
                        self.serie.id = cursor.lastrowid
                    except sqlite3.IntegrityError:
                        # Letzte Rettung, falls in der Millisekunde jemand anderes
                        # die Serie angelegt hat
                        cursor.execute("SELECT id FROM series WHERE name = ?", (self.serie.name,))
                        self.serie.id = cursor.fetchone()[0]

            # 2. WERK
            if self.work:
                self.work.series_id = self.serie.id if self.serie else None
                w_dict = asdict(self.work)
                if self.work.id:
                    cols = ", ".join([f"{k}=?" for k in w_dict.keys() if k != 'id'])
                    cursor.execute(f"UPDATE works SET {cols} WHERE id=?",
                                   (*[v for k, v in w_dict.items() if k != 'id'], self.work.id))
                else:
                    cursor.execute("INSERT INTO works (title, series_id) VALUES (?,?)",
                                   (self.work.title, self.work.series_id))
                    self.work.id = cursor.lastrowid

            # 3. BUCH
            if self.book:
                self.book.work_id = self.work.id if self.work else None
                b_dict = asdict(self.book)
                if self.book.id:
                    cols = ", ".join([f"{k}=?" for k in b_dict.keys() if k != 'id'])
                    cursor.execute(f"UPDATE books SET {cols} WHERE id=?",
                                   (*[v for k, v in b_dict.items() if k != 'id'], self.book.id))
                else:
                    # IDs entfernen, falls sie 0 oder None sind für INSERT
                    if 'id' in b_dict: b_dict.pop('id')
                    cols = ", ".join(b_dict.keys())
                    placeholders = ", ".join(["?"] * len(b_dict))
                    cursor.execute(f"INSERT INTO books ({cols}) VALUES ({placeholders})", tuple(b_dict.values()))
                    self.book.id = cursor.lastrowid

            # 4. AUTOREN (work_to_author)
            if self.work and self.work.id:
                cursor.execute("DELETE FROM work_to_author WHERE work_id=?", (self.work.id,))
                for fn, ln in self.authors:
                    slug = slugify(f"{fn} {ln}")
                    cursor.execute("INSERT OR IGNORE INTO authors (firstname, lastname, slug) VALUES (?,?,?)",
                                   (fn, ln, slug))
                    cursor.execute("SELECT id FROM authors WHERE slug=?", (slug,))
                    res = cursor.fetchone()
                    if res:
                        aid = res[0]
                        cursor.execute("INSERT INTO work_to_author (work_id, author_id) VALUES (?,?)",
                                       (self.work.id, aid))

            conn.commit()
            print(f"✅ Speichern erfolgreich: Book ID {self.book.id}")
            return True

        except Exception as e:
            print(f"❌ Save Error: {e}")
            import traceback
            traceback.print_exc()
            if 'conn' in locals(): conn.rollback()
            return False
        finally:
            if 'conn' in locals(): conn.close()
            print(f"--- DEBUG SAVE ENDE ---\n")

    # ----------------------------------------------------------------------
    # SEARCH-HELPER für ComboBoxen und Book-Model
    # ----------------------------------------------------------------------
    @staticmethod
    def search(author_q: str, title_q: str) -> list:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        sql = """SELECT DISTINCT b.path FROM books b 
                 JOIN works w ON b.work_id = w.id
                 LEFT JOIN work_to_author wta ON w.id = wta.work_id
                 LEFT JOIN authors a ON wta.author_id = a.id WHERE 1=1"""
        params = []
        if author_q:
            for p in author_q.split():
                sql += " AND (a.firstname LIKE ? OR a.lastname LIKE ?)"
                params.extend([f"%{p}%", f"%{p}%"])
        if title_q:
            sql += " AND (w.title LIKE ? OR w.title_de LIKE ? OR w.title_en LIKE ?)"
            params.extend([f"%{title_q}%"] * 3)
        cursor.execute(sql, params)
        res = [r['path'] for r in cursor.fetchall()]
        conn.close()
        return res

    @staticmethod
    def get_prioritized_series(authors: list) -> list:
        """
        Ersetzt get_all_series_names.
        Holt alle Seriennamen: Erst die des aktuellen Autors, dann den Rest.
        """
        import sqlite3
        from Gemini.file_utils import DB_PATH, slugify

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Slugs für die Suche nach Autoren-Serien vorbereiten
        slugs = [slugify(f"{fn} {ln}") for fn, ln in authors if (fn or ln)]

        if not slugs:
            # Falls keine Autoren bekannt sind, wie früher einfach alles alphabetisch
            cursor.execute("SELECT DISTINCT name FROM series WHERE name != '' ORDER BY name ASC")
            res = [r[0] for r in cursor.fetchall()]
        else:
            # Die Prioritäts-Logik:
            # Teil 1: Serien, die bereits mit diesen Autoren verknüpft sind (Prio 1)
            # Teil 2: Alle anderen Serien (Prio 2)
            placeholders = ",".join(["?"] * len(slugs))
            sql = f"""
                SELECT DISTINCT name FROM (
                    SELECT s.name, 1 as prio 
                    FROM series s
                    JOIN works w ON s.id = w.series_id
                    JOIN work_to_author wa ON w.id = wa.work_id
                    JOIN authors a ON wa.author_id = a.id
                    WHERE a.slug IN ({placeholders})

                    UNION

                    SELECT name, 2 as prio 
                    FROM series 
                    WHERE name != ''
                ) 
                ORDER BY prio ASC, name ASC
            """
            cursor.execute(sql, slugs)
            res = [r[0] for r in cursor.fetchall()]

        conn.close()
        return res

    @staticmethod
    def get_works_by_authors(authors: list) -> list:
        """
        Holt alle Master-Titel der Werke, die mit den angegebenen Autoren verknüpft sind.
        Wird genutzt, um die Werk-Combobox im View zu befüllen.
        """
        import sqlite3
        from Gemini.file_utils import DB_PATH, slugify

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Slugs der Autoren für die Suche nutzen
        slugs = [slugify(f"{fn} {ln}") for fn, ln in authors if (fn or ln)]

        if not slugs:
            return []

        placeholders = ",".join(["?"] * len(slugs))

        # Wir suchen alle Werke, die mindestens einen der Autoren haben
        sql = f"""
            SELECT DISTINCT w.title 
            FROM works w
            JOIN work_to_author wa ON w.id = wa.work_id
            JOIN authors a ON wa.author_id = a.id
            WHERE a.slug IN ({placeholders})
            ORDER BY w.title ASC
        """

        cursor.execute(sql, slugs)
        res = [r[0] for r in cursor.fetchall()]
        conn.close()
        return res


def merge_with(self, other_data: Union['BookData', dict]):
    """
    Übernimmt Daten und verteilt sie intelligent auf die Atome.
    """
    if not other_data:
        return

    # 1. Datenquelle normalisieren
    if isinstance(other_data, dict):
        source_dict = other_data
    else:
        source_dict = other_data.to_dict() if hasattr(other_data, 'to_dict') else {}

    # 2. Mapping-Korrektur (Scanner nutzt oft 'ext', Property heißt 'extension')
    if 'ext' in source_dict and 'extension' not in source_dict:
        source_dict['extension'] = source_dict.pop('ext')

    # 3. Werte verteilen
    for key, value in source_dict.items():
        if value is None or value == "":
            continue

        # --- DEBUG LINE START ---
        print(f"DEBUG: Versuche Merge für Key: '{key}' mit Value: '{value}'")
        # --- DEBUG LINE END ---

        # A: Erst prüfen, ob es eine Proxy-Property im Manager gibt
        if hasattr(self, key):
            try:
                setattr(self, key, value)
                continue  # Erfolg, nächster Key
            except Exception:
                pass

                # B: Fallback - Direkt in die Atome schauen, falls keine Property existiert
        # Wir prüfen das Buch-Atom
        if hasattr(self.book, key):
            setattr(self.book, key, value)
        # Wir prüfen das Werk-Atom
        elif hasattr(self.work, key):
            setattr(self.work, key, value)
        # Wir prüfen das Serien-Atom
        elif hasattr(self.serie, key):
            setattr(self.serie, key, value)