from __future__ import annotations
import sqlite3
import copy
from dataclasses import dataclass, asdict, fields, field
from typing import List, Optional, Tuple, Any, Union

from Zoom.utils import DB_PATH, slugify, sanitize_path


@dataclass
class BookTData:
    """Der Junior: Unser flacher Datenträger."""
    id: int = 0
    path: str = ""
    title: str = ""
    ext: str = ""
    isbn: str = ""
    genre: str = ""
    stars: int = 0
    description: str = ""
    language: str = ""
    series_name: str = ""
    series_number: str = ""
    is_complete: int = 0
    scanner_version: str = ""
    rating_ol: float = 0.0
    rating_ol_count: int = 0
    rating_g: float = 0.0
    rating_g_count: int = 0
    is_manual_description: int = 0
    year: int = 0
    work_id: int = 0
    # Komplexe Typen brauchen eine default_factory
    genre_epub: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)
    authors: list = field(default_factory=list)

    def merge_with(self, data: Union[dict, 'BookTData']):
        """Junior saugt Daten auf und mapped Felder."""
        if not data: return
        source = data if isinstance(data, dict) else asdict(data)

        mappings = {
            'extension': 'ext',
        }

        for key, value in source.items():
            if value is None or value == "":
                continue

            target_key = mappings.get(key, key)
            if hasattr(self, target_key):
                if target_key in ['keywords', 'regions']:
                    current_val = getattr(self, target_key)
                    if isinstance(value, (list, set, str)):
                        if isinstance(value, str): value = [value]
                        current_val.update(value)
                else:
                    setattr(self, target_key, value)


@dataclass
class WorkTData:
    id: int = 0
    title: str = ""
    title_de: str = ""
    title_en: str = ""
    title_fr: str = ""
    title_it: str = ""
    title_es: str = ""
    series_id: Optional[int] = None
    series_index: float = 0.0
    stars: int = 0
    description: str = ""
    rating: float = 0.0
    slug: str = ""


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


class BookData:
    # ----------------------------------------------------------------------
    # Der Manager (Aggregat): Hält die drei Atome book, work und serie.
    # ----------------------------------------------------------------------
    def __init__(self, book=None, work=None, serie=None):
        self.book = book or BookTData()
        self.work = work or WorkTData()
        self.serie = serie or SerieTData()

        self.authors: List[Tuple[str, str]] = []
        self.db_snapshot = None
        self.is_in_db = False

        self.all_available_works = []
        self.all_available_series = []
        self.db_book = None

    # ----------------------------------------------------------------------
    # Zustandsmanagement.
    # ----------------------------------------------------------------------
    @property
    def is_dirty(self) -> bool:
        """ Vergleicht den aktuellen Stand der Atome mit dem Snapshot beim Laden. """
        if not self.db_snapshot:
            return True

        current_state = (self.book.title, self.work.title, self.serie.name, self.book.authors)
        old_state = (
            self.db_snapshot['book'].title,
            self.db_snapshot['work'].title,
            self.db_snapshot['serie'].name,
            self.db_snapshot['authors']
        )
        return current_state != old_state

    def capture_db_state(self):
        """Erstellt eine tiefe Kopie des aktuellen Zustands für den Vergleich."""
        self.db_snapshot = {
            'book': copy.deepcopy(self.book),
            'work': copy.deepcopy(self.work),
            'serie': copy.deepcopy(self.serie),
            'authors': copy.deepcopy(self.book.authors)
        }


    # ----------------------------------------------------------------------
    # SQL-LADE-Funktionen
    # ----------------------------------------------------------------------
    @classmethod
    def load_by_id(cls, book_id: int) -> Optional['BookData']:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM books WHERE id = ?", (book_id,))
        res = cursor.fetchone()
        conn.close()

        if res:
            mgr = cls.load_by_path(res[0])
            if mgr:
                mgr.capture_db_state()
            return mgr
        return None

    @classmethod
    def load_by_path(cls, file_path: str) -> Optional['BookData']:
        clean_path = sanitize_path(file_path)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        sql = """
            SELECT b.*, w.id as w_id, w.series_id as w_sid, w.series_index as w_sidx, w.title as w_title, 
                   w.title_de as w_tde, w.title_en as w_ten, w.stars as w_stars, w.description as w_desc,
                   s.id as s_id, s.name as s_name, s.slug as s_slug
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
        # --- HIER DIE DEBUG AUSGABE ---
        print("\n--- 🕵️ DB-DATA CHECK ---")
        print(f"Buch-ID:   {row.get('id')}")
        print(f"Werk-Titel: {row.get('w_title')}")
        print(f"Werk-DE:    {row.get('w_title_de')}")
        print(f"Werk-Desc:  {row.get('w_description')[:50] if row.get('w_description') else 'LEER'}...")
        print(f"Werk-Rate:  {row.get('w_rating')}")
        print(f"Serie:      {row.get('s_name')}")
        print(f"Serie-DE:   {row.get('s_name_de')}")
        print("------------------------\n")

        # Helper zum sauberen Set-Laden
        def str_to_set(s):
            if s is None: return set()
            s_str = str(s).strip()
            if not s_str: return set()
            return set(p.strip() for p in s_str.split(",") if p.strip())

        # 1. Book Atom befüllen
        book_data = {f.name: row[f.name] for f in fields(BookTData) if f.name in row}
        # Sets explizit konvertieren BEVOR das Objekt erzeugt wird
        book_data['keywords'] = str_to_set(row.get('keywords'))
        book_data['regions'] = str_to_set(row.get('regions'))
        book_atom = BookTData(**book_data)

        # 2. Work Atom befüllen (Prefix 'w_' entfernen)
        work_atom = WorkTData()
        if row['w_id']:
            work_data = {}
            # Extrahiere nur Felder, die tatsächlich in WorkTData definiert sind
            valid_fields = {f.name for f in fields(WorkTData)}
            for f in fields(WorkTData):
                db_key = f"w_{f.name}"
                if db_key in row:
                    val = row[db_key]
                    if f.name in ['keywords', 'regions']:
                        work_data[f.name] = str_to_set(val)
                    else:
                        work_data[f.name] = val
            # Erzeuge WorkTData mit den bereits konvertierten Daten
            work_atom = WorkTData(**work_data)

        # 3. Serie Atom befüllen (Prefix 's_' entfernen)
        serie_atom = SerieTData()
        if row['s_id']:
            serie_data = {f.name: row[f"s_{f.name}"] for f in fields(SerieTData) if f"s_{f.name}" in row}
            serie_atom = SerieTData(**serie_data)

        mgr = cls(book=book_atom, work=work_atom, serie=serie_atom)
        mgr.is_in_db = True

        # Autoren laden
        if mgr.work.id > 0:
            cursor.execute("""SELECT a.firstname, a.lastname FROM authors a
                              JOIN work_to_author wa ON a.id = wa.author_id WHERE wa.work_id = ?""", (mgr.work.id,))
            mgr.book.authors = [(r[0], r[1]) for r in cursor.fetchall()]
        conn.close()
        mgr.capture_db_state()
        return mgr

    # ----------------------------------------------------------------------
    # Funkionen auf BOOK
    # ----------------------------------------------------------------------
    def search_books_in_db(self, author_query: str, title_query: str) -> List[str]:
        results = BookData.search(author_query, title_query)
        return [sanitize_path(p) for p in results]

    def migrate_from_book(self):
        if not self.book or not self.work:
            return
        if self.book.title and not self.work.title:
            self.work.title = self.book.title
        if self.book.stars and (not self.work.stars or self.work.stars == 0):
            self.work.stars = self.book.stars
        if self.book.description and not self.work.description:
            self.work.description = self.book.description
        if (not self.work.rating or self.work.rating == 0):
            self.work.rating = self.calculate_consolidated_rating()

        if self.book.series_name and not self.serie.name:
            self.serie.name = self.book.series_name

    def calculate_consolidated_rating(self):
        b = self.book
        total_count = b.rating_ol_count + b.rating_g_count
        if total_count > 0:
            weighted_sum = (b.rating_ol * b.rating_ol_count) + (b.rating_g * b.rating_g_count)
            return round(weighted_sum / total_count, 2)
        elif b.rating_ol > 0 or b.rating_g > 0:
            vals = [v for v in [b.rating_ol, b.rating_g] if v > 0]
            return round(sum(vals) / len(vals), 2)
        return 0.0


    def get_description_by_lang(self, associated_books: List[BookTData], lang: str) -> Optional[str]:
        """Sucht in der Liste vorhandener Bücher nach einer Beschreibung in der Zielsprache."""
        for b in associated_books:
            if b.language == lang and b.description:
                return b.description
        return None


    # ----------------------------------------------------------------------
    # SQL-Such-Funktionen für Autoren
    # ----------------------------------------------------------------------
    @staticmethod
    def search(author_q: str, title_q: str) -> list:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
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
    def reset_authors(new_authors, wid, cursor: sqlite3.Cursor):
        if not new_authors or not wid:
            return
        cursor.execute("DELETE FROM work_to_author WHERE work_id = ?", (wid,))
        for fn, ln in new_authors:
            a_slug = slugify(f"{fn} {ln}")
            cursor.execute("INSERT OR IGNORE INTO authors (firstname, lastname, slug) VALUES (?,?,?)",
                           (fn, ln, a_slug))
            cursor.execute("SELECT id FROM authors WHERE slug=?", (a_slug,))
            aid = cursor.fetchone()[0]
            cursor.execute("INSERT INTO work_to_author (work_id, author_id) VALUES (?,?)",
                           (wid, aid))


    # --- Ergänzung für Punkt 1 & 8: Spracherkennung ---
    def get_author_language(self) -> str:
        """Ermittelt die Primärsprache des ersten Autors aus der DB (Spalte: language)."""
        if not self.book.authors:
            return 'en'
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            fn, ln = self.book.authors[0]
            cursor.execute("SELECT language FROM authors WHERE firstname = ? AND lastname = ?", (fn, ln))
            res = cursor.fetchone()
            return res[0].lower() if res and res[0] else 'en'
        except sqlite3.OperationalError:
            # Falls die Spalte 'language' auch nicht existiert, schauen wir kurz nach
            print("⚠️ Spalte 'language' in Tabelle 'authors' nicht gefunden.")
            return 'en'
        finally:
            conn.close()

    # ----------------------------------------------------------------------
    # SQL-Such-Funktionen für Work
    # ----------------------------------------------------------------------
    def find_best_work_match(self, title: str, lang: str) -> Optional[int]:
        """Sucht ein Werk basierend auf dem Titel in der Primärsprache des Autors oder anderen Spalten."""
        if not title: return None
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # Prio 1: Suche in der spezifischen Sprachspalte des Autors
            col = f"title_{lang}" if lang in ['de', 'en', 'fr', 'it', 'es'] else "title"
            sql = f"SELECT id FROM works WHERE {col} = ?"
            cursor.execute(sql, (title,))
            res = cursor.fetchone()
            if res: return res[0]

            # Prio 2: Suche in allen Titel-Spalten
            sql = "SELECT id FROM works WHERE title=? OR title_de=? OR title_en=? OR title_fr=? OR title_es=? OR title_it=?"
            cursor.execute(sql, (title,) * 6)
            res = cursor.fetchone()
            return res[0] if res else None
        finally:
            conn.close()

    @staticmethod
    def find_work_by_series_fingerprint(book_data: BookData) -> Optional[int]:
        if not book_data.book.authors or not book_data.book.series_number:
            return None
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            fn, ln = book_data.book.authors[0]
            author_slug = slugify(f"{fn} {ln}")
            cursor.execute("SELECT language FROM authors WHERE slug = ?", (author_slug,))
            res = cursor.fetchone()
            author_lang = res[0] if res and res[0] else 'en'

            sql = """
                SELECT b.work_id 
                FROM books b
                JOIN work_to_author wa ON b.work_id = wa.work_id
                JOIN authors a ON wa.author_id = a.id
                WHERE a.slug = ? 
                  AND b.series_number = ? 
                  AND b.language = ?
                  AND b.work_id IS NOT NULL
                LIMIT 1
            """
            cursor.execute(sql, (author_slug, book_data.book.series_number, author_lang))
            res = cursor.fetchone()
            return res[0] if res else None
        except Exception as e:
            print(f"⚠️ Fehler im Model bei Fingerprint-Match: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def get_works_by_authors(authors: list) -> list:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        slugs = [slugify(f"{fn} {ln}") for fn, ln in authors if (fn or ln)]
        if not slugs: return []
        placeholders = ",".join(["?"] * len(slugs))
        sql = f"""SELECT DISTINCT w.title FROM works w
                  JOIN work_to_author wa ON w.id = wa.work_id
                  JOIN authors a ON wa.author_id = a.id
                  WHERE a.slug IN ({placeholders}) ORDER BY w.title ASC"""
        cursor.execute(sql, slugs)
        res = [r[0] for r in cursor.fetchall()]
        conn.close()
        return res

    # --- Ergänzung für Punkt 7: Titel-Mapping ---
    def assign_book_title_to_work_lang(self):
        """Ordnet den aktuellen Buchtitel der passenden Sprachspalte im Werk zu."""
        lang = (self.book.language or 'en').lower()
        if 'de' in lang:
            self.work.title_de = self.book.title
        elif 'en' in lang:
            self.work.title_en = self.book.title
        elif 'fr' in lang:
            self.work.title_fr = self.book.title
        elif 'es' in lang:
            self.work.title_es = self.book.title
        elif 'it' in lang:
            self.work.title_it = self.book.title

        # Falls der Haupttitel noch leer ist
        if not self.work.title:
            self.work.title = self.book.title

    def load_work_into_manager(self, work_id: int):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM works WHERE id = ?", (work_id,))
            row = cursor.fetchone()
            if row:
                for key in row.keys():
                    if hasattr(self.work, key):
                        setattr(self.work, key, row[key])
        finally:
            conn.close()


    # --- Ergänzung für Punkt 2, 4, 5, 6: Daten-Aggregation ---
    def get_all_books_for_work(self, work_id: int) -> List[BookTData]:
        """Holt alle Bücher, die bereits an diesem Werk hängen, für den Durchschnitt/Merge."""
        if not work_id: return []
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM books WHERE work_id = ?", (work_id,))
            return [BookTData(**dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

    # ----------------------------------------------------------------------
    # SQL-Such-Funktionen für Series
    # ----------------------------------------------------------------------

    def find_best_serie_match(self, name: str, lang: str) -> Optional[int]:
        """Analog zu Work: Sucht die beste Serien-ID."""
        if not name: return None
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            col = f"name_{lang}" if lang in ['de', 'en', 'fr', 'it', 'es'] else "name"
            cursor.execute(f"SELECT id FROM series WHERE {col} = ?", (name,))
            res = cursor.fetchone()
            if not res:
                cursor.execute("SELECT id FROM series WHERE name=? OR name_de=? OR name_en=?", (name, name, name))
                res = cursor.fetchone()
            return res[0] if res else None
        finally:
            conn.close()

    def get_series_details_by_id(self, s_id: int) -> SerieTData:
        """Lädt eine Serie anhand ihrer ID aus der DB."""
        if not s_id: return SerieTData()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM series WHERE id = ?", (s_id,))
            row = cursor.fetchone()
            if row:
                return SerieTData(**dict(row))
            return SerieTData()
        finally:
            conn.close()

    @staticmethod
    def get_prioritized_series(authors: list) -> list:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        slugs = [slugify(f"{fn} {ln}") for fn, ln in authors if (fn or ln)]
        if not slugs:
            cursor.execute("SELECT DISTINCT name FROM series WHERE name != '' ORDER BY name ASC")
            res = [r[0] for r in cursor.fetchall()]
        else:
            placeholders = ",".join(["?"] * len(slugs))
            sql = f"""
                SELECT DISTINCT name FROM (
                    SELECT s.name, 1 as prio FROM series s
                    JOIN works w ON s.id = w.series_id
                    JOIN work_to_author wa ON w.id = wa.author_id
                    JOIN authors a ON wa.author_id = a.id
                    WHERE a.slug IN ({placeholders})
                    UNION
                    SELECT name, 2 as prio FROM series WHERE name != ''
                ) ORDER BY prio ASC, name ASC"""
            cursor.execute(sql, slugs)
            res = [r[0] for r in cursor.fetchall()]
        conn.close()
        return res

    def get_all_series_names(self) -> List[str]:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, name_de, name_en FROM series")
        names = set()
        for row in cursor.fetchall():
            for n in row:
                if n: names.add(n)
        conn.close()
        return sorted(list(names))

    def get_series_id_by_name(self, name: str) -> Optional[int]:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM series WHERE name=? OR name_de=? OR name_en=?", (name,) * 3)
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    def get_work_titles_for_series(self, series_id: int) -> List[str]:
        if not series_id: return []
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title, title_de, title_en FROM works WHERE series_id = ?", (series_id,))
        titles = set()
        for row in cursor.fetchall():
            for t in row:
                if t: titles.add(t)
        conn.close()
        return sorted(list(titles))

    # --- Ergänzung für Punkt 9: Serien-Sync ---
    def sync_serie_names(self, author_lang: str):
        """Synchronisiert den Seriennamen des Buches mit der Sprachspalte der Serie."""
        if not self.serie.id: return

        # Wenn das Buch in der Sprache des Autors ist, setzen wir den Hauptnamen
        if self.book.language == author_lang:
            self.serie.name = self.book.series_name

        # Sprachspezifische Spalten befüllen
        lang = (self.book.language or 'en').lower()
        if 'de' in lang:
            self.serie.name_de = self.book.series_name
        elif 'en' in lang:
            self.serie.name_en = self.book.series_name

    def get_series_details_by_name(self, name: str) -> SerieTData:
        if not name: return SerieTData()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = "SELECT * FROM series WHERE name=? OR name_de=? OR name_en=? LIMIT 1"
            cursor.execute(sql, (name, name, name))
            row = cursor.fetchone()
            if row: return SerieTData(**dict(row))
            return SerieTData(name=name)
        finally:
            conn.close()

    # ----------------------------------------------------------------------
    # SAVE-Funktionen
    # ----------------------------------------------------------------------
    def save(self) -> bool:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # --- 1. SERIE ---
            if self.serie.name:
                new_slug = slugify(self.serie.name)
                cursor.execute("SELECT id FROM series WHERE slug = ? AND id != ?", (new_slug, self.serie.id or 0))
                conflict = cursor.fetchone()
                if conflict:
                    self.serie.id = conflict[0]

                s_dict = {k: v for k, v in asdict(self.serie).items() if not isinstance(v, (list, dict)) and k != 'id'}
                s_dict['slug'] = new_slug

                if self.serie.id and self.serie.id > 0:
                    cols = ", ".join([f"{k}=?" for k in s_dict.keys()])
                    cursor.execute(f"UPDATE series SET {cols} WHERE id=?", (*s_dict.values(), self.serie.id))
                else:
                    cols = ", ".join(s_dict.keys())
                    placeholders = ", ".join(["?"] * len(s_dict))
                    cursor.execute(f"INSERT INTO series ({cols}) VALUES ({placeholders})", tuple(s_dict.values()))
                    self.serie.id = cursor.lastrowid

            # --- 2. WERK ---
            if self.work.title:
                self.work.series_id = self.serie.id if self.serie.id and self.serie.id > 0 else None
                self.work.slug = slugify(self.work.title)

                w_dict = {k: v for k, v in asdict(self.work).items() if not isinstance(v, (list, dict)) and k != 'id'}

                if self.work.id and self.work.id > 0:
                    cols = ", ".join([f"{k}=?" for k in w_dict.keys()])
                    cursor.execute(f"UPDATE works SET {cols} WHERE id=?", (*w_dict.values(), self.work.id))
                else:
                    cols = ", ".join(w_dict.keys())
                    placeholders = ", ".join(["?"] * len(w_dict))
                    cursor.execute(f"INSERT INTO works ({cols}) VALUES ({placeholders})", tuple(w_dict.values()))
                    self.work.id = cursor.lastrowid

            # --- 3. BUCH ---
            if self.book.path:
                self.book.work_id = self.work.id if self.work.id and self.work.id > 0 else None
                b_dict = {k: v for k, v in asdict(self.book).items() if not isinstance(v, (list, dict, set)) and k != 'id'}

                if self.book.id and self.book.id > 0:
                    cols = ", ".join([f"{k}=?" for k in b_dict.keys()])
                    cursor.execute(f"UPDATE books SET {cols} WHERE id=?", (*b_dict.values(), self.book.id))
                else:
                    cols = ", ".join(b_dict.keys())
                    placeholders = ", ".join(["?"] * len(b_dict))
                    cursor.execute(f"INSERT INTO books ({cols}) VALUES ({placeholders})", tuple(b_dict.values()))
                    self.book.id = cursor.lastrowid

            # --- 4. AUTOREN ---
            if self.work.id and self.work.id > 0 and self.book.authors:
                self.reset_authors(self.book.authors, self.work.id, cursor)

            conn.commit()
            self.capture_db_state()
            return True
        except sqlite3.Error as e:
            print(f"❌ DB Fehler in save: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ----------------------------------------------------------------------
    # GETTER und SETTER für localised Names
    # ----------------------------------------------------------------------
    def get_localized_series_name(self) -> str:
        lang = (self.book.language or 'de').lower()
        if 'de' in lang: return self.serie.name_de or self.serie.name
        if 'en' in lang: return self.serie.name_en or self.serie.name
        return self.serie.name or "Unbekannte Serie"

    def get_localized_work_title(self) -> str:
        lang = (self.book.language or 'de').lower()
        if 'de' in lang: return self.work.title_de or self.work.title
        if 'en' in lang: return self.work.title_en or self.work.title
        return self.work.title or "Unbekannter Titel"

    def set_localized_title(self, new_title: str):
        lang = (self.book.language or 'de').lower()
        self.book.title = new_title
        if 'de' in lang: self.work.title_de = new_title
        elif 'en' in lang: self.work.title_en = new_title
        if not self.work.title: self.work.title = new_title

    def set_localized_series(self, new_series_name: str):
        lang = (self.book.language or 'de').lower()
        self.book.series_name = new_series_name
        if 'de' in lang: self.serie.name_de = new_series_name
        elif 'en' in lang: self.serie.name_en = new_series_name
        if not self.serie.name or self.serie.id == 0: self.serie.name = new_series_name

    def set_series_index(self, index: float):
        self.book.series_number = str(index)
        self.work.series_index = index


    # ----------------------------------------------------------------------
    # DELETE-Funktionen
    # ----------------------------------------------------------------------
    def delete_book(self) -> bool:
        if not self.book.id: return False
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM books WHERE id = ?", (self.book.id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Löschfehler: {e}")
            return False




    def get_work_details_by_title(self, title: str, authors: list) -> WorkTData:
        if not title: return WorkTData()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            lastnames = [a[1] for a in authors]
            placeholders = ",".join(["?"] * len(lastnames))
            sql = f"""
                SELECT w.* FROM works w
                JOIN work_to_author wta ON w.id = wta.work_id
                JOIN authors aut ON wta.author_id = aut.id
                WHERE (w.title=? OR w.title_de=? OR w.title_en=?)
                  AND aut.lastname IN ({placeholders})
                LIMIT 1
            """
            cursor.execute(sql, (title, title, title, *lastnames))
            row = cursor.fetchone()
            if row: return WorkTData(**dict(row))
            return WorkTData(title=title)
        finally:
            conn.close()






