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


def slugify(text: str) -> str:
    """
    Erzeugt einen URL-freundlichen Slug.
    Wandelt Umlaute um, entfernt Sonderzeichen und ersetzt Leerzeichen durch Bindestriche.
    """
    if not text:
        return ""

    # 1. Umlaute manuell ersetzen (wichtig für deutsche Namen)
    replacements = {
        "ä": "ae", "ö": "oe", "ü": "ue",
        "Ä": "ae", "Ö": "oe", "Ü": "ue",
        "ß": "ss"
    }
    for search, replace in replacements.items():
        text = text.replace(search, replace)

    # 2. Kleinschreibung & Normalisierung
    text = text.lower()
    # NFKD zerlegt Zeichen (z.B. Akzente), encode('ascii', 'ignore') wirft sie weg
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

    # 3. Alle Nicht-Alphanumerischen Zeichen durch Bindestrich ersetzen
    text = re.sub(r'[^a-z0-9]+', '-', text)

    # 4. Mehrfache Bindestriche reduzieren und Ränder säubern
    text = re.sub(r'-+', '-', text).strip('-')

    return text
