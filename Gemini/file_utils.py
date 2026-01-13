import re
import html
import os
import platform
import unicodedata


# ----------------------------------------------------------------------
# KONFIGURATION & PFADE
# ----------------------------------------------------------------------
def get_paths():
    if platform.system() == 'Darwin':  # macOS
        return {
            'db_root': "/Volumes/eBooks",
            'ebook_src': "/Volumes/eBooks",
            'audio_src': "/Volumes/aBooks"
        }
    else:  # Windows
        return {
            'db_root': r"C:\DB",
            'ebook_src': "D:/Bücher",
            'audio_src': r"C:\DB"
        }


PATHS = get_paths()
DB_PATH = os.path.join(PATHS['db_root'], "books.db")
DB2_PATH = os.path.join(PATHS['db_root'], "audiobooks.db")

EBOOK_BASE = PATHS['ebook_src']
AUDIO_BASE = PATHS['audio_src']

EM_DASH = "—"  # \u2014


# ----------------------------------------------------------------------
# PFAD-WERKZEUGE
# ----------------------------------------------------------------------
def clean_path(p):
    if not p: return ""
    return unicodedata.normalize('NFC', p)


def sanitize_path(path: str) -> str:
    if not path: return ""
    path = clean_path(path)
    return os.path.normpath(path).replace('\\', '/')


# ----------------------------------------------------------------------
# BUCHFILE-WERKZEUGE (Zentral)
# ----------------------------------------------------------------------
def find_real_file(path):
    """Prüft, ob der Pfad existiert, oder ob die Datei mit einer anderen Endung vorliegt."""
    if not path or os.path.exists(path):
        return path

    base, old_ext = os.path.splitext(path)
    # Probiere die üblichen Verdächtigen
    for ext in ['.pdf', '.epub', '.mobi', '.azw3']:
        if ext.lower() == old_ext.lower():
            continue
        test_path = base + ext
        if os.path.exists(test_path):
            print(f"DEBUG: Datei-Rettung: {old_ext} -> {ext} gefunden!")
            return test_path

    return path  # We

def build_perfect_filename(book_data) -> str:
    """
    Zentrale Erzeugung des Dateinamens.
    Nutzt book_data.authors, .series_name, .series_number, .title, .year, .extension
    """
    # 1. Autoren String
    if book_data.authors:
        auth_str = " & ".join([f"{v} {n}".strip() for v, n in book_data.authors])
    else:
        auth_str = "Unbekannt"

    # 2. Serien Teil
    series_part = ""
    if book_data.series_name:
        # Führende Null bei Nummern < 10 (optional, aber schöner)
        num = str(book_data.series_number).zfill(2) if book_data.series_number else ""
        series_part = f"{book_data.series_name} {num}-"

    # 3. Jahr & Extension
    year_part = f" ({book_data.year})" if book_data.year else ""

    # Extension Logik: Nutze Feld im Objekt, sonst Extraktion aus Pfad
    ext = getattr(book_data, 'extension', None)
    if not ext and book_data.path:
        _, ext = os.path.splitext(book_data.path)
    if not ext:
        ext = ".epub"
    if not ext.startswith('.'):
        ext = f".{ext}"

    # 4. Titel
    title_part = book_data.title if book_data.title else "Unbekannter Titel"
    # Entfernt ' mobi' oder ' pdf' (case insensitive) vor der Klammer oder dem Punkt
    clean_title = re.sub(r'\s+(mobi|pdf)\b', '', title_part, flags=re.IGNORECASE)

    # 5. Zusammenbau
    filename = f"{auth_str} {EM_DASH} {series_part}{clean_title}{year_part}{ext}"

    # Reinigung verbotener Zeichen
    clean_name = re.sub(r'[:?*<>|"/\\\r\n]', '', filename)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()

    return unicodedata.normalize('NFC', clean_name)


def normalize_author_tuple(author_tuple: tuple) -> tuple:
    if not isinstance(author_tuple, tuple) or len(author_tuple) != 2:
        return ("", "")
    return (normalize_text(author_tuple[0]), normalize_text(author_tuple[1]))


# ----------------------------------------------------------------------
# TEXT-WERKZEUGE
# ----------------------------------------------------------------------
def normalize_text(text: str) -> str:
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'[.,;\'"]', '', text)
    text = re.sub(r'[\s\-]+', ' ', text).strip()
    # Vereinfachung für Vergleich (Umlaute/Akzente)
    replacements = {'ä': 'a', 'ö': 'o', 'ü': 'u', 'é': 'e', 'á': 'a', 'à': 'a', 'ç': 'c'}
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.split(':')[0].strip()


def clean_description(raw_text: str) -> str:
    if not raw_text: return ""
    clean = html.unescape(raw_text)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = re.sub(r'\r', '', clean)
    clean = re.sub(r'\n\s*\n+', '\n\n', clean)
    clean = re.sub(r'[ \t]+', ' ', clean)
    return clean.strip()