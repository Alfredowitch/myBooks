"""
DATEI: scan_file.py
PROJEKT: MyBook-Management (v1.3.1)
BESCHREIBUNG: Extrahiert Metadaten aus Pfad- und Dateinamen.
              Unterstützt die neue REAL-Typisierung für Serien-Indizes.
"""
import re
import os
from Zoom.utils import EM_DASH, sanitize_path

CURRENT_SCANNER_VERSION = "1.3.1"

# ----------------------------------------------------------------------
# Analysiere den Pfad
# ----------------------------------------------------------------------
def derive_metadata_from_path(file_path):
    """
    Leitet Sprache, Region, Genre und Keywords aus der Ordnerstruktur ab.
    """
    clean_p = sanitize_path(file_path)
    path_parts = clean_p.split('/')
    region = None
    manual_genre = None
    keywords = set()  # Direkt als Set für Typsicherheit in BookTData

    # 1. Sprache erkennen
    language = get_final_language(file_path)

    # 2. Themen-Pfad für Business-Bücher (als Keywords)
    if 'Business' in path_parts:
        idx = path_parts.index('Business')
        topic_parts = path_parts[idx + 1:-1]
        if topic_parts:
            keywords.update(topic_parts)
        manual_genre = "Sachbuch"

    # 3. Spezial-Ordner auswerten
    # Wir nutzen eine Schleife oder gezielte Abfragen für die Pfad-Segmente
    if 'Reisen' in path_parts:
        idx = path_parts.index('Reisen')
        manual_genre = 'Reisebericht'
        region_parts = path_parts[idx + 1: -1]
        if region_parts:
            region = " / ".join(region_parts)
            keywords.update(region_parts)

    elif '_byGenre' in path_parts:
        idx = path_parts.index('_byGenre')
        if idx + 1 < len(path_parts):
            manual_genre = path_parts[idx + 1]
            keywords.add(manual_genre)

    elif '_byRegion' in path_parts:  # Korrigiert: Tippfehler entfernt
        idx = path_parts.index('_byRegion')
        if idx + 1 < len(path_parts):
            region = path_parts[idx + 1]
            keywords.add(region)

    elif '_Sprache' in path_parts:
        manual_genre = 'Sprachbuch'
        keywords.add('Sprache lernen')

    elif '_Easy Reader' in path_parts:
        manual_genre = 'Easy Reader'
        idx = path_parts.index('_Easy Reader')
        if idx + 1 < len(path_parts):
            keywords.add(f"Niveau: {path_parts[idx + 1]}")

    # Dubletten in Region bereinigen (z.B. "Frankreich / Frankreich")
    if region and " / " in region:
        r_parts = [p.strip() for p in region.split('/')]
        region = " / ".join(dict.fromkeys(r_parts))

    return {
        'language': language,
        'region': region,
        'genre': manual_genre,
        'keywords': keywords
    }

# ----------------------------------------------------------------------
# Analysiere den Filename
# ----------------------------------------------------------------------
def extract_info_from_filename(file_path):
    filename = os.path.basename(file_path)
    remaining, extension = os.path.splitext(filename)
    remaining = remaining.strip()

    info = {
        'authors': [],
        'series_name': None,
        'series_index': 0.0,
        'year': None,
        'title': "",
        'file_path': file_path,
        'ext': extension.lower()
    }

    # A. Autoren isolieren (via EM-DASH)
    if EM_DASH in remaining:
        parts = remaining.split(EM_DASH, 1)
        authors_raw = parts[0].strip()
        remaining = parts[1].strip()
        if authors_raw:
            for a in re.split(r'[&;]| et ', authors_raw):
                info['authors'].append(_normalize_author_name(a.strip()))

    # B. Jahr isolieren (bevor wir uns an die Bindestriche wagen)
    year_match = re.search(r'\((\d{4})\)', remaining)
    if year_match:
        year_str = year_match.group(1)
        if year_str != "0101":
            info['year'] = year_str
        remaining = remaining.replace(year_match.group(0), "").strip()

    # C. Serie & Titel Logik (Die "Zahl am Trenner"-Logik)
    # Wir suchen den ersten verfügbaren Bindestrich (normaler Dash oder En-Dash)
    # Erlaubt Formate wie: "Serie 01-Titel", "Serie01-Titel", "Serie-Titel"
    match = re.search(r'^(.+?)\s?[-–—]\s?(.*)$', remaining)

    if match:
        potential_series_part = match.group(1).strip()
        potential_title = match.group(2).strip()

        # Prüfung: Endet der erste Teil auf eine Zahl?
        # Diese Regex findet eine Zahl am Ende des Strings, optional mit Präfixen wie # oder Nr.
        series_num_match = re.search(r'(.*?)(?:[\s#]|Nr\.|No\.)*(\d+(?:[.,]\d+)?)$', potential_series_part)

        if series_num_match:
            # Wir haben eine Serie!
            info['series_name'] = series_num_match.group(1).strip()
            raw_num = series_num_match.group(2).replace(',', '.')
            try:
                info['series_index'] = float(raw_num)
            except ValueError:
                info['series_index'] = 0.0
            info['title'] = potential_title
        else:
            # Kein Treffer für eine Zahl am Ende -> Es war wohl kein Serien-Bindestrich
            info['title'] = remaining
    else:
        # Gar kein Bindestrich gefunden -> Alles ist Titel
        info['title'] = remaining

    return info

# ----------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------
def clean_file_names(root_directory):
    """ Ersetzt normale Bindestriche durch lange Gedankenstriche zur Trennung von Autoren. """
    short_dash_with_spaces = " - "
    short_dash_suffix = " -"
    long_dash_with_spaces = f" {EM_DASH} "
    i = 0

    for root, dirs, files in os.walk(root_directory):
        for filename in files:
            new_filename = None
            if short_dash_with_spaces in filename:
                new_filename = filename.replace(short_dash_with_spaces, long_dash_with_spaces, 1)
            elif short_dash_suffix in filename:
                new_filename = filename.replace(short_dash_suffix, long_dash_with_spaces, 1)

            if new_filename:
                old_path = os.path.join(root, filename)
                new_path = os.path.join(root, new_filename)
                try:
                    os.rename(old_path, new_path)
                    i += 1
                except OSError as e:
                    print(f"⚠️ Fehler beim Umbenennen von {filename}: {e}")
    return i

def get_final_language(file_path, api_lang=None):
    """ Erzwingt Sprachregeln basierend auf Pfad-Priorität. """
    path_lower = file_path.lower()
    mapping = {
        "deutsch": "de", "english": "en", "french": "fr",
        "franz": "fr", "italien": "it", "spanisch": "es"
    }
    for key, code in mapping.items():
        if key in path_lower:
            return code

    allowed = {'de', 'en', 'fr', 'it', 'es'}
    if api_lang:
        clean_api = str(api_lang).lower()[:2]
        if clean_api in allowed:
            return clean_api
    return "de"

def _normalize_author_name(raw_name):
    """ Wandelt Namen in (Vorname, Nachname) Tupel um. """
    if not raw_name:
        return ("", "Unbekannt")

    if "," in raw_name:
        parts = raw_name.split(",", 1)
        return (parts[1].strip(), parts[0].strip())

    parts = raw_name.split()
    if len(parts) >= 2:
        return (" ".join(parts[:-1]), parts[-1])

    return ("", raw_name)

def extract_topic_from_path(file_path, anchor="Business"):
    """ Extrahiert Ordnerhierarchie ab einem Anker. """
    normalized_path = os.path.normpath(file_path)
    parts = normalized_path.split(os.sep)
    if anchor in parts:
        idx = parts.index(anchor)
        topic_parts = parts[idx + 1:-1]
        if topic_parts:
            return os.sep.join(topic_parts)
    return None

def detect_real_extension(file_path):
    """ Header-basierte Formaterkennung. """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(100)
            if header.startswith(b'PK\x03\x04'): return '.epub'
            if b'BOOKMOBI' in header[60:100] or b'TEXtREAd' in header[60:100]: return '.mobi'
            if header.startswith(b'%PDF'): return '.pdf'
    except:
        pass
    return None

def is_mobi_readable(file_path):
    """ Validiert MOBI-Header. """
    try:
        if not os.path.exists(file_path): return False
        with open(file_path, 'rb') as f:
            header = f.read(100)
            return b'BOOKMOBI' in header[60:100] or b'TEXtREAd' in header[60:100]
    except Exception as e:
        print(f"⚠️ Header-Fehler ({file_path}): {e}")
        return False

# --- Test-Sektion ---
if __name__ == '__main__':
    test_paths = [
        'D:/Books/Autor/Star Wars — 03 - Die Rache der Sith (2005).epub',
        'D:/Books/Autor/(1997)-Standalone Buch.epub',
        'D:/Bücher/Deutsch/_byGenre/Krimi/Alexander Hartung — Jan Tommen 02 - Bis alle Schuld beglichen (2015).epub'
    ]
    for p in test_paths:
        print(f"\nPath: {os.path.basename(p)}")
        print(f"Info: {extract_info_from_filename(p)}")
        print(f"Meta: {derive_metadata_from_path(p)}")