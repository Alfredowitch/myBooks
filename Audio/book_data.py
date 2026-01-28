from __future__ import annotations
import sqlite3
import copy
import traceback # Für detaillierte Fehlersuche
from dataclasses import dataclass, asdict, fields, field
from typing import List, Optional, Tuple, Any, Union

from Zoom.utils import DB_PATH, slugify, sanitize_path


def force_set(value, debug_name="Unknown") -> set:
    """Wandelt Eingaben sicher in ein Set von Strings um und splittet Kommas."""
    if not value:
        return set()

    # Fall 1: Es ist bereits ein Set oder eine Liste
    if isinstance(value, (set, list, tuple)):
        return {str(x).strip() for x in value if x is not None and str(x).strip()}

    # Fall 2: Es ist ein String (der eventuell Kommas enthält)
    if isinstance(value, str):
        if "," in value:
            return {p.strip() for p in value.split(",") if p.strip()}
        return {value.strip()} if value.strip() else set()

    # Fall 3: Es ist eine nackte Zahl (int)
    return {str(value).strip()}

# --- DATEN-ATOME (Dataclasses) ---

@dataclass
class BookTData:
    id: int = 0
    work_id: int = 0
    path: str = ""
    title: str = ""
    ext: str = ""
    isbn: str = ""
    genre: str = ""
    stars: int = 0
    description: str = ""
    notes: str = ""
    language: str = ""
    series_name: str = ""
    series_number: str = ""
    is_complete: int = 0
    is_read: int = 0
    scanner_version: str = ""
    rating_ol: float = 0.0
    rating_ol_count: int = 0
    rating_g: float = 0.0
    rating_g_count: int = 0
    is_manual_description: int = 0
    year: str = ""
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)
    authors: list = field(default_factory=list)

    def __post_init__(self):
        # Wir erzwingen den Typ und loggen Abweichungen
        self.keywords = force_set(self.keywords, "Book.Init.keywords")
        self.regions = force_set(self.regions, "Book.Init.regions")
        # Falls irgendetwas versucht, ein Attribut 'rating' zu setzen,
        # fangen wir das hier ab oder mappen es um.
        if hasattr(self, 'rating'):
            print("⚠️ DEBUG: Jemand hat 'rating' gesetzt!")

    # Das ist der "Türsteher" der Klasse. Bei neuen Daten wird automatisch SET aufgerufen
    def __setattr__(self, name, value):
        # DEBUG: Was wird hier gerade gesetzt?
        # print(f"SETATTR: {name} = {value} ({type(value)})") # Nur bei extremen Problemen aktivieren

        if name in ['keywords', 'regions']:
            if not isinstance(value, set):
                super().__setattr__(name, force_set(value, f"Book.{name}"))
            else:
                super().__setattr__(name, value)
        elif name == 'year':
            # Hier zwingen wir ALLES zu String, um den Fehler zu killen
            super().__setattr__(name, str(value) if value is not None else "")
        else:
            super().__setattr__(name, value)

    def merge_with(self, data: Union[dict, 'BookTData']):
        if not data: return
        source = data if isinstance(data, dict) else asdict(data)
        # Debug: Was kommt hier rein?
        if 'keywords' in source:
            print(f"DEBUG [Merge]: Eingehende Keywords Typ: {type(source['keywords'])}")
            print(f"DEBUG [Merge]: Ziel Keywords Typ: {type(self.keywords)}")

        mappings = {'extension': 'ext'}
        for key, value in source.items():
            if value is None or value == "": continue
            target_key = mappings.get(key, key)
            if hasattr(self, target_key):
                if target_key in ['keywords', 'regions']:
                    # Sicherstellen, dass das Ziel ein Set IST
                    if not isinstance(getattr(self, target_key), set):
                        setattr(self, target_key, set())
                    current_val = getattr(self, target_key)

                    if not isinstance(current_val, set):
                        print(f"⚠️ ALARM: {target_key} im Zielobjekt ist {type(current_val)}!")
                        setattr(self, target_key, force_set(current_val, f"Merge.FixTarget.{target_key}"))
                        current_val = getattr(self, target_key)

                    # Wert normalisieren (String/Liste/Set -> Set)
                    if isinstance(value, str):
                        new_vals = set(p.strip() for p in value.split(",") if p.strip())
                        current_val.update(new_vals)
                    elif isinstance(value, (list, set)):
                        # DEBUG PRINT: Was versuchen wir hinzuzufügen?
                        print(f"🔍 DEBUG: Adding to {target_key}: {value}")
                        current_val.update(str(v).strip() for v in value if v is not None)
                        # current_val.update(v.strip() for v in value if v and str(v).strip())
                else:
                    setattr(self, target_key, value)


@dataclass
class WorkTData:
    id: int = 0
    title: str = ""
    slug: str = ""
    title_de: str = ""
    title_en: str = ""
    title_fr: str = ""
    title_it: str = ""
    title_es: str = ""
    description: str = ""
    notes: str = ""
    series_id: Optional[int] = None
    series_index: float = 0.0
    stars: int = 0
    rating: float = 0.0
    genre: str = ""
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)


    # --- DER FIX FÜR DEN FEHLER ---
    def __init__(self, **kwargs):
        # Hole alle offiziellen Felder der Dataclass
        names = {f.name for f in fields(self.__class__)}
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)
        # Manuelle Post-Init Logik, da __post_init__ bei manuellem __init__ nicht automatisch kommt
        self.keywords = force_set(getattr(self, 'keywords', set()))
        self.regions = force_set(getattr(self, 'regions', set()))

    # Das ist der "Türsteher" der Klasse. Bei neuen Daten wird automatisch SET aufgerufen
    def __setattr__(self, name, value):
        if name in ['keywords', 'regions'] and not isinstance(value, set):
            super().__setattr__(name, force_set(value))
        else:
            super().__setattr__(name, value)

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
    notes: str = ""
    link: str = ""


# --- DER MANAGER (AGGREGAT) ---

class BookData:
    def __init__(self, book=None, work=None, serie=None):
        self.book = book or BookTData()
        self.work = work or WorkTData()
        self.serie = serie or SerieTData()
        self.db_snapshot = None
        self.is_in_db = False
        self.all_available_works = []
        self.all_available_series = []

    # ----------------------------------------------------------------------
    # I. LOAD (Fabrik-Methoden & DB-Abfragen)
    # ----------------------------------------------------------------------
    @classmethod
    def load_by_id(cls, book_id: int) -> Optional['BookData']:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM books WHERE id = ?", (book_id,))
        res = cursor.fetchone()
        conn.close()
        return cls.load_by_path(res[0]) if res else None

    @classmethod
    def load_by_path(cls, file_path: str) -> Optional['BookData']:
        clean_path = sanitize_path(file_path)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            # 1. Buch-Daten laden (SELECT * ist hier sicher, da nur eine Tabelle)
            res_book = cursor.execute("SELECT * FROM books WHERE path = ?", (clean_path,)).fetchone()
            if not res_book:
                conn.close()
                return None

            row_b = dict(res_book)

            # Erzeugt BookTData; Keywords/Regions werden durch __post_init__ automatisch zu Sets
            book_params = {f.name: row_b[f.name] for f in fields(BookTData) if f.name in row_b}
            book_atom = BookTData(**book_params)
            # --- 🕵️ KRITISCHER DB-LOG ---
            print(f"\n--- 🗄️ DATABASE RAW SNAPSHOT (ID: {clean_path}) ---")
            print(f"Book_ID: {book_atom.id}")
            print(f"Work-Ref: {book_atom.work_id}")
            print(f"TITEL: {book_atom.title}")
            print(f"YEAR: {book_atom.year} (Typ: {type(book_atom.year).__name__})")
            print(
                f"SERIES_INDEX: {getattr(book_atom, 'series_index', 'N/A')} (Typ: {type(getattr(book_atom, 'series_index', None)).__name__})")
            print(f"KEYWORDS: {book_atom.keywords} (Typ: {type(book_atom.keywords).__name__})")

            # Check auf Int-Leichen in den Keywords
            if isinstance(book_atom.keywords, set):
                int_keys = [k for k in book_atom.keywords if not isinstance(k, str)]
                if int_keys:
                    print(f"⚠️ GEFUNDEN: Integer in Keywords! -> {int_keys}")

            print(f"AUTHORS: {book_atom.authors}")
            print("----------------------------------------------\n")

            # 2. Werk-Daten laden (basierend auf der work_id des Buches)
            work_atom = WorkTData()
            if book_atom.work_id:
                res_work = cursor.execute("SELECT * FROM works WHERE id = ?", (book_atom.work_id,)).fetchone()
                if res_work:
                    row_w = dict(res_work)
                    work_params = {f.name: row_w[f.name] for f in fields(WorkTData) if f.name in row_w}
                    work_atom = WorkTData(**work_params)
                # NEU: Anzahl der verknüpften Bücher ermitteln
                # Wir nutzen deine Funktion
                sibling_books = cls().get_all_books_for_work(work_atom.id)
                work_atom.book_count = len(sibling_books)

            # 3. Serien-Daten laden (basierend auf der series_id des Werks)
            serie_atom = SerieTData()
            if work_atom.series_id:
                res_serie = cursor.execute("SELECT * FROM series WHERE id = ?", (work_atom.series_id,)).fetchone()
                if res_serie:
                    row_s = dict(res_serie)
                    serie_params = {f.name: row_s[f.name] for f in fields(SerieTData) if f.name in row_s}
                    serie_atom = SerieTData(**serie_params)

            # 4. Autoren laden (Verknüpfung via Work)
            authors_list = []
            if work_atom.id:
                sql_auth = """SELECT a.firstname, a.lastname FROM authors a
                                  JOIN work_to_author wa ON a.id = wa.author_id 
                                  WHERE wa.work_id = ?"""
                authors_list = [(r[0], r[1]) for r in cursor.execute(sql_auth, (work_atom.id,)).fetchall()]

            # Autoren dem Buch-Atom zuweisen
            book_atom.authors = authors_list

            # Manager instanziieren und Zustand für Dirty-Check einfrieren
            mgr = cls(book=book_atom, work=work_atom, serie=serie_atom)
            mgr.is_in_db = True

            # Dropdown-Listen für die UI befüllen (Autor-priorisiert)
            mgr.all_available_series = mgr.get_prioritized_series(authors_list)
            mgr.all_available_works = mgr.get_works_by_authors(authors_list)

            conn.close()
            mgr.capture_db_state()
            return mgr
        except Exception as e:
            conn.close()
            print("\n" + "!" * 60)
            print(f"❌ DEBUG FEHLER in load_by_path:")
            print(f"Pfad: {file_path}")
            print(traceback.format_exc())  # Das zeigt uns die Zeilennummer!
            print("!" * 60 + "\n")
            raise e  # Fehler weiterreichen, damit das Popup trotzdem kommt

    @staticmethod
    def search_paths(author_q: str, title_q: str) -> List[str]:
        conn = sqlite3.connect(DB_PATH)
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
        res = [sanitize_path(r[0]) for r in cursor.fetchall()]
        conn.close()
        return res

    # ----------------------------------------------------------------------
    # II. ATOMS (Book, Work, Series Logik)
    # ----------------------------------------------------------------------
    # --- BOOK ---
    @staticmethod
    def search_books_in_db(author_query: str, title_query: str) -> List[str]:
        results = BookData.search_paths(author_query, title_query)
        return [sanitize_path(p) for p in results]

    def calculate_consolidated_rating(self):
        b = self.book
        total_count = b.rating_ol_count + b.rating_g_count
        if total_count > 0:
            return round(((b.rating_ol * b.rating_ol_count) + (b.rating_g * b.rating_g_count)) / total_count, 2)
        vals = [v for v in [b.rating_ol, b.rating_g] if v > 0]
        return round(sum(vals) / len(vals), 2) if vals else 0.0


    def get_description_by_lang(self, associated_books: List[BookTData], lang: str) -> Optional[str]:
        """Sucht in der Liste vorhandener Bücher nach einer Beschreibung in der Zielsprache."""
        for b in associated_books:
            if b.language == lang and b.description:
                return b.description
        return None

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

    # --- WORK ---
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

    def find_best_work_match(self, title: str, lang: str) -> Optional[int]:
        if not title: return None
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        col = f"title_{lang}" if lang in ['de', 'en', 'fr', 'it', 'es'] else "title"
        cursor.execute(f"SELECT id FROM works WHERE {col} = ?", (title,))
        res = cursor.fetchone()
        if not res:
            cursor.execute("SELECT id FROM works WHERE title=? OR title_de=? OR title_en=?", (title, title, title))
            res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    def load_work_into_manager(self, work_id: int):
        conn = sqlite3.connect(DB_PATH);
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM works WHERE id = ?", (work_id,)).fetchone()
        if row:
            for key in row.keys():
                if hasattr(self.work, key): setattr(self.work, key, row[key])
        conn.close()


    # --- Ergänzung für Punkt 7: Titel-Mapping ---
    def assign_book_title_to_work_lang(self):
        """Ordnet den aktuellen Buchtitel der passenden Sprachspalte im Werk zu."""
        lang_code = (self.book.language or 'en').lower()[:2]
        target_field = f"title_{lang_code}"
        # 1. Sprachspezifisches Feld nur befüllen, wenn leer
        if hasattr(self.work, target_field):
            current_lang_val = getattr(self.work, target_field)
            if not current_lang_val:
                setattr(self.work, target_field, self.book.title)
        # 2. Haupttitel nur befüllen, wenn absolut nichts drinsteht
        if not self.work.title:
            self.work.title = self.book.title

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

    @staticmethod
    def get_works_by_authors(authors: list, series_index: Optional[int] = None) -> list:
        if not authors: return []

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Wir filtern primär nach dem Nachnamen (wegen der j-k / joanne-k Problematik)
        lastnames = [ln for fn, ln in authors if ln]
        if not lastnames:
            conn.close()
            return []

        placeholders = ",".join(["?"] * len(lastnames))

        # Basis-Abfrage
        sql = f"""SELECT DISTINCT w.title FROM works w
                  JOIN work_to_author wa ON w.id = wa.work_id
                  JOIN authors a ON wa.author_id = a.id
                  WHERE a.lastname IN ({placeholders})"""

        params = list(lastnames)

        # ZUSÄTZLICHER FILTER: Seriennummer
        # Ich nehme an, die Spalte heißt 'series_index' oder 'volume' in deiner 'works' Tabelle
        if series_index is not None and series_index > 0:
            sql += " AND w.series_index = ?"
            params.append(series_index)

        sql += " ORDER BY w.title ASC"

        cursor.execute(sql, params)
        res = [str(r[0]) for r in cursor.fetchall() if r[0]]
        conn.close()
        return res

    # --- SERIES ---
    def get_series_details(self, identifier: Union[int, str]) -> SerieTData:
        conn = sqlite3.connect(DB_PATH);
        conn.row_factory = sqlite3.Row
        if isinstance(identifier, int):
            row = conn.execute("SELECT * FROM series WHERE id = ?", (identifier,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM series WHERE name=? OR name_de=? OR name_en=? LIMIT 1",
                               (identifier,) * 3).fetchone()
        conn.close()
        return SerieTData(**dict(row)) if row else SerieTData(name=str(identifier))

    def find_best_serie_match(self, name: str, lang: Optional[str] = None) -> Optional[int]:
        """
        Sucht eine Serie nach Namen (auch übersetzt) und gibt die ID zurück.
        Berücksichtigt optional eine spezifische Sprache.
        """
        if not name: return None
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Wenn eine Sprache angegeben ist, suchen wir primär in dieser Spalte
        if lang in ['de', 'en', 'fr', 'it', 'es']:
            col = f"name_{lang}"
            cursor.execute(f"SELECT id FROM series WHERE {col}=? LIMIT 1", (name,))
            res = cursor.fetchone()
            if res:
                conn.close()
                return res[0]

        # Fallback: Suche über alle gängigen Namens-Varianten
        sql = "SELECT id FROM series WHERE name=? OR name_de=? OR name_en=? LIMIT 1"
        cursor.execute(sql, (name, name, name))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    @staticmethod
    def get_prioritized_series(authors: list) -> list:
        conn = sqlite3.connect(DB_PATH)
        slugs = [slugify(f"{fn} {ln}") for fn, ln in authors if (fn or ln)]
        try:
            if not slugs:
                res = conn.execute("SELECT DISTINCT name FROM series WHERE name != '' ORDER BY name ASC").fetchall()
            else:
                p = ",".join(["?"] * len(slugs))
                # Wir zwingen im SQL schon alles zu TEXT, um Typ-Mix zu vermeiden
                sql = f"""SELECT DISTINCT CAST(name AS TEXT) FROM (
                                SELECT s.name, 1 as prio FROM series s 
                                JOIN works w ON s.id = w.series_id
                                JOIN work_to_author wa ON w.id = wa.work_id 
                                JOIN authors a ON wa.author_id = a.id 
                                WHERE a.slug IN ({p})
                                UNION 
                                SELECT name, 2 as prio FROM series WHERE name != ''
                              ) ORDER BY prio ASC, name ASC"""
                res = conn.execute(sql, slugs).fetchall()

            # Hier der Sicherheitsfilter: Alles zu String konvertieren
            final_list = [str(r[0]) for r in res if r[0] is not None]
            return final_list
        except Exception as e:
            print(f"❌ Fehler in get_prioritized_series: {e}")
            return []
        finally:
            conn.close()

    def get_series_id_by_name(self, name: str) -> Optional[int]:
        if not name:
            return None

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Spaltennamen ermitteln
        cursor.execute("PRAGMA table_info(series)")
        # Wir suchen alle Spalten, die mit 'name' anfangen
        name_cols = [row[1] for row in cursor.fetchall() if row[1].startswith('name')]

        # 2. SQL-Abfrage dynamisch bauen: "WHERE name=? OR name_de=? OR name_it=? ..."
        where_clause = " OR ".join([f"{col}=?" for col in name_cols])
        sql = f"SELECT id FROM series WHERE {where_clause}"

        # Wir übergeben den Namen so oft, wie wir Spalten haben
        cursor.execute(sql, (name,) * len(name_cols))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None

    # --- Ergänzung für Punkt 9: Serien-Sync ---
    def sync_serie_names(self, author_lang: str):
        """Synchronisiert den Seriennamen des Buches mit der Sprachspalte der Serie."""
        if not self.serie.id or not self.book.series_name:
            return

        # 1. Hauptname setzen, wenn Buch-Sprache der Autoren-Sprache entspricht
        if self.book.language == author_lang:
            self.serie.name = self.book.series_name

        # 2. Sprachspezifische Spalte dynamisch befüllen (de, en, it, fr, etc.)
        lang_code = (self.book.language or 'en').lower()[:2]  # Nur die ersten zwei Zeichen (z.B. 'it' von 'it-IT')

        target_field = f"name_{lang_code}"

        # Prüfen, ob das Feld in der SeriesData-Klasse existiert (z.B. name_it)
        if hasattr(self.serie, target_field):
            setattr(self.serie, target_field, self.book.series_name)
        else:
            # Falls das Feld nicht existiert (z.B. name_es), nutzen wir name_en als Fallback
            if not self.serie.name_en:
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
    # III. AUTHORS
    # ----------------------------------------------------------------------
    def get_author_language(self) -> str:
        if not self.book.authors: return 'en'
        conn = sqlite3.connect(DB_PATH)
        fn, ln = self.book.authors[0]
        res = conn.execute("SELECT language FROM authors WHERE firstname = ? AND lastname = ?", (fn, ln)).fetchone()
        conn.close()
        return res[0].lower() if res and res[0] else 'en'


    @staticmethod
    def reset_authors(new_authors, wid, cursor: sqlite3.Cursor):
        cursor.execute("DELETE FROM work_to_author WHERE work_id = ?", (wid,))
        for fn, ln in new_authors:
            a_slug = slugify(f"{fn} {ln}")
            cursor.execute("INSERT OR IGNORE INTO authors (firstname, lastname, slug) VALUES (?,?,?)", (fn, ln, a_slug))
            aid = cursor.execute("SELECT id FROM authors WHERE slug=?", (a_slug,)).fetchone()[0]
            cursor.execute("INSERT INTO work_to_author (work_id, author_id) VALUES (?,?)", (wid, aid))

    # ----------------------------------------------------------------------
    # Zustandsmanagement.
    # ----------------------------------------------------------------------
    @property
    def is_dirty(self) -> bool:
        """ Vergleicht den aktuellen Stand der Atome mit dem Snapshot beim Laden. """
        if not self.db_snapshot:
            return True

        # Wir normalisieren die Autoren zu reinen String-Tupeln für den Vergleich
        def normalize_authors(auth_list):
            if not auth_list: return []
            return [(str(fn).strip(), str(ln).strip()) for fn, ln in auth_list]

        current_authors = normalize_authors(self.book.authors)
        old_authors = normalize_authors(self.db_snapshot['authors'])

        current_state = (
            str(self.book.title).strip(),
            str(self.work.title).strip(),
            str(self.serie.name).strip(),
            current_authors
        )
        old_state = (
            str(self.db_snapshot['book'].title).strip(),
            str(self.db_snapshot['work'].title).strip(),
            str(self.db_snapshot['serie'].name).strip(),
            old_authors
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
    # IV. SAVE
    # ----------------------------------------------------------------------
    def save(self) -> bool:
        conn = sqlite3.connect(DB_PATH);
        cursor = conn.cursor()
        try:
            # 1. Serie
            if self.serie.name:
                self.serie.slug = slugify(self.serie.name)

                # ID-Validierung: Passt der Name noch zur ID?
                res = cursor.execute("SELECT id FROM series WHERE name = ?", (self.serie.name,)).fetchone()
                if res:
                    self.serie.id = res[0]
                else:
                    self.serie.id = None

                    # s_dict erstellen: Wir nehmen ALLES außer der ID
                s_dict = {k: v for k, v in asdict(self.serie).items() if k != 'id'}

                if self.serie.id:
                    # Hier der Fix: Wir nutzen COALESCE nur für Werte, die im s_dict wirklich leer/None sind.
                    # Wenn du aber etwas in die Form eingetragen hast, muss das ? diesen Wert binden.
                    cols = []
                    values = []
                    for k, v in s_dict.items():
                        # Wenn der neue Wert v existiert (nicht None/leer), direkt setzen.
                        # Wenn v leer ist, COALESCE nutzen, um den alten DB-Stand zu retten.
                        if v and str(v).strip():
                            cols.append(f"{k} = ?")
                            values.append(v)
                        else:
                            # Feld ist leer in der UI -> DB Wert behalten
                            cols.append(f"{k} = COALESCE({k}, '')")

                    if cols:
                        sql = f"UPDATE series SET {', '.join(cols)} WHERE id = ?"
                        cursor.execute(sql, (*values, self.serie.id))
                else:
                    # Komplett neuer Insert
                    cursor.execute(
                        f"INSERT INTO series ({', '.join(s_dict.keys())}) VALUES ({', '.join(['?'] * len(s_dict))})",
                        tuple(s_dict.values()))
                    self.serie.id = cursor.lastrowid

            # 2. Werk
            if self.work.title:
                self.work.series_id = self.serie.id if self.serie.id else None
                self.work.slug = slugify(self.work.title)

                # Check: Passt die ID zum Titel?
                res = cursor.execute("SELECT id FROM works WHERE title = ?", (self.work.title,)).fetchone()
                if res:
                    self.work.id = res[0]
                else:
                    self.work.id = None  # Neues Werk!

                w_dict = {k: v for k, v in asdict(self.work).items() if
                          not isinstance(v, (list, dict, set)) and k != 'id'}
                w_dict['keywords'] = ",".join(sorted(str(k) for k in self.work.keywords))
                w_dict['regions'] = ",".join(sorted(str(r) for r in self.work.regions))

                if self.work.id:
                    sql = f"UPDATE works SET {', '.join([f'{k}=COALESCE(NULLIF(?,\"\"), {k})' for k in w_dict.keys()])} WHERE id=?"
                    cursor.execute(sql, (*w_dict.values(), self.work.id))
                else:
                    # BEVOR wir ein ganz neues Werk anlegen:
                    # Datenmigration von verbundenen Büchern (optional, falls gewünscht)
                    cursor.execute(
                        f"INSERT INTO works ({', '.join(w_dict.keys())}) VALUES ({', '.join(['?'] * len(w_dict))})",
                        tuple(w_dict.values()))
                    self.work.id = cursor.lastrowid

            # 3. Buch
            if self.book.path:
                self.book.work_id = self.work.id
                # Nur einfache Typen für die DB-Abfrage (keine Listen/Sets)
                b_dict = {k: v for k, v in asdict(self.book).items() if
                          not isinstance(v, (list, dict, set)) and k != 'id'}
                # Sets manuell hinzufügen als String
                b_dict['keywords'] = ",".join(self.book.keywords) if self.book.keywords else ""
                b_dict['regions'] = ",".join(self.book.regions) if self.book.regions else ""

                if self.book.id:
                    cursor.execute(f"UPDATE books SET {', '.join([f'{k}=?' for k in b_dict.keys()])} WHERE id=?",
                                   (*b_dict.values(), self.book.id))
                else:
                    cursor.execute(
                        f"INSERT INTO books ({', '.join(b_dict.keys())}) VALUES ({', '.join(['?'] * len(b_dict))})",
                        tuple(b_dict.values()))
                    self.book.id = cursor.lastrowid

            # 4. Autoren
            if self.work.id and self.book.authors:
                self.reset_authors(self.book.authors, self.work.id, cursor)

            conn.commit();
            self.capture_db_state();
            return True
        except Exception as e:
            print(f"❌ Save Error: {e}");
            conn.rollback();
            return False
        finally:
            conn.close()

    # ----------------------------------------------------------------------
    # V. DELETE
    # ----------------------------------------------------------------------
    def delete_book(self) -> bool:
        if not self.book.id: return False
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM books WHERE id = ?", (self.book.id,))
        conn.commit();
        conn.close();
        return True