"""
DATEI: scan_file.py
PROJEKT: MyBook-Management (v1.3.0)
BESCHREIBUNG: Kümmert sich um das Auslesen der Daten aus dem Pfadnamen und Filenamen..
              Bücher sind durch den Pfad sauber in Deutch, French, English, Italienisch und Spanisch getrennt.
              Es gibt eine thematische Sortierung unter Business, diese Pfad-Teile werden in Keywords abgespeichert
              Es gibt eine Sortierung _byGenre und _byRegion woraus die Region und Gene gefüllt werden.
              Und des gibt _Easy Reader und _Sprache wo Bücher für den Spracherwerb sortiert sind.

              Die Filenamen folgen der Ordnung:  vorname1 nachname2 & vorname2 nachname2 -- Serienname Seriennummer-Titel (Jahr).suffix
              -- ist ein langer Gedankenstrich em-
              vorname kann vornamea vornameb v. sein.
"""
import re
import os

from Gemini.file_utils import EM_DASH, sanitize_path, normalize_author_tuple
CURRENT_SCANNER_VERSION = "1.3.1"  # Dein neuer Versionsstempel

# ----------------------------------------------------------------------
# Analysiere den Pfad
# ----------------------------------------------------------------------
def derive_metadata_from_path(file_path):
    """
    Leitet Sprache, Region, Genre und Keywords aus der neuen Ordnerstruktur ab.
    """
    clean_p = sanitize_path(file_path)
    path_parts = clean_p.split('/')
    region = None
    manual_genre = None
    keywords = []

    # 1. Sprache erkennen (Deutsch oder Englisch)
    language = get_final_language(file_path)

    # 2. Themen-Pfad für Business-Bücher (als Keywords)
    # Falls der Pfad über "Business" läuft, extrahieren wir die Hierarchie
    if 'Business' in path_parts:
        idx = path_parts.index('Business')
        # Alles nach 'Business' bis vor den Dateinamen
        topic_parts = path_parts[idx + 1:-1]
        if topic_parts:
            keywords.append(os.sep.join(topic_parts))
        manual_genre = "Sachbuch"

    # 3. Spezial-Ordner auswerten (Genre, Region, Sprache, Easy Reader)
    for i, part in enumerate(path_parts):
        if 'Reisen' in path_parts:
            idx = path_parts.index('Reisen')
            manual_genre = 'Reisebericht'
            region_parts = path_parts[idx + 1: -1]  # Alles danach bis zum File
            if region_parts:
                region = " / ".join(region_parts)
                keywords.extend(region_parts)
        elif '_byGenre' in path_parts:
            idx = path_parts.index('_byGenre')
            manual_genre = path_parts[idx + 1] if idx + 1 < len(path_parts) else None
            if manual_genre: keywords.append(manual_genre)
        elif '_bytRegion' in path_parts:
            idx = path_parts.index('_bytRegion')
            region = path_parts[idx + 1] if idx + 1 < len(path_parts) else None
            if region: keywords.append(region)
        elif '_Sprache' in path_parts:
            manual_genre = 'Sprachbuch'
            keywords.append('Sprache lernen')
        # Easy Reader (z.B. A1 - 500 Wörter)
        elif '_Easy Reader' in path_parts:
            manual_genre = 'Easy Reader'
            if i + 1 < len(path_parts):
                # Das Niveau (A1 etc.) als Keyword speichern
                keywords.append(f"Niveau: {path_parts[i + 1]}")
        # BUSINESS (Der allgemeine Auffang-Topf für Sachbücher)
        elif 'Business' in path_parts:
            manual_genre = "Sachbuch"
            idx = path_parts.index('Business')
            # Da Reisen oben schon abgefangen wurde, sind das hier nur Themen
            topic_parts = path_parts[idx + 1: -1]
            if topic_parts:
                keywords.extend(topic_parts)
    # Rückgabe als Dictionary für BookData.from_dict
    final_region = region
    if region and " / " in region:
        # Falls durch einen Fehler 'Frankreich / Frankreich' entstanden wäre:
        r_parts = [p.strip() for p in region.split('/')]
        final_region = " / ".join(dict.fromkeys(r_parts))  # Behält Reihenfolge, entfernt Dubletten
    return {
        'language': language,
        'region': final_region,
        'genre': manual_genre,
        'keywords': list(set(keywords))
    }

# ----------------------------------------------------------------------
# Analysiere den Filename IN SCHRITTEN
# ----------------------------------------------------------------------
def extract_info_from_filename(file_path):
    filename = os.path.basename(file_path)
    # Startpunkt: Der komplette Name ohne Endung
    remaining, extension = os.path.splitext(filename)
    remaining = remaining.strip()
    # print(f"\nDEBUG SCAN START: '{remaining}'")
    info = {
        'authors': [],
        'series_name': None,
        'series_number': None,
        'year': None,
        'title': "",
        'file_path': file_path,
        'extension': extension.lower()
    }

    # A. Autoren isolieren & entfernen
    # Beispiel: "Alexander Hartung — Jan Tommen10-An einem dunklen Ort"
    separators = [EM_DASH, " – ", " - "]
    for sep in separators:
        if sep in remaining:
            parts = remaining.split(sep, 1)
            authors_raw = parts[0].strip()
            remaining = parts[1].strip()  # Hier wird der String gekürzt!
            if authors_raw:
                for a in re.split(r'[&;]| et ', authors_raw):
                    info['authors'].append(_normalize_author_name(a.strip()))
            # print(f"DEBUG nach Autor:  '{remaining}'")
            break

    # B. Jahr isolieren & entfernen
    year_match = re.search(r'\((\d{4})\)', remaining)
    if year_match:
        info['year'] = year_match.group(1)
        if info['year'] == "0101":
            info['year'] = None
        remaining = remaining.replace(year_match.group(0), "").strip()
        # print(f"DEBUG nach Jahr:   '{remaining}'")

    # C. Serie isolieren & entfernen
    # Sucht: (Serie)(Zahl) - (Titel) ODER (Serie) (Zahl)-(Titel)
    # Erkennt jetzt: #, Nr., No., T, Tome, Vol. vor der Zahl
    # series_match = re.search(r'^(.+?)(\d+)\s*-\s*(.*)$', remaining)
    series_match = re.search(r'^(.+?)(?:[\s#]|Nr\.|No\.|T\.|Tome|T|Vol\.)*(\d+)\s*-\s*(.*)$', remaining)

    if series_match:
        info['series_name'] = series_match.group(1).strip()
        info['series_number'] = series_match.group(2).strip()
        info['title'] = series_match.group(3).strip()
    else:
        # NUR WENN KEINE SERIE GEFUNDEN WURDE:
        # Wir säubern noch führende/hängende Bindestriche vom restlichen String
        info['title'] = re.sub(r'^[\s\-\–\—]+|[\s\-\–\—]+$', '', remaining).strip()

    return info

# ----------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------
def clean_file_names(root_directory):
    # Definition der Zeichen (kurzer Bindestrich vs. langer Gedankenstrich/En-Dash)
    short_dash_with_spaces = " - "
    short_dash_suffix = " -"
    long_dash_with_spaces = " – "  # Das ist der längere En-Dash (–)
    i = 0

    for root, dirs, files in os.walk(root_directory):
        for filename in files:
            new_filename = None
            # 1. Priorität: Suche nach " - "
            if short_dash_with_spaces in filename:
                new_filename = filename.replace(short_dash_with_spaces, long_dash_with_spaces, 1)
            # 2. Priorität: Falls " - " nicht da, suche nach " -"
            elif short_dash_suffix in filename:
                new_filename = filename.replace(short_dash_suffix, long_dash_with_spaces, 1)
            if new_filename:
                old_path = os.path.join(root, filename)
                new_path = os.path.join(root, new_filename)
                i = i + 1
                try:
                    os.rename(old_path, new_path)
                    # print(f"Umbernannt: {filename} -> {new_filename}")
                except OSError as e:
                    print(f"Fehler beim Umbenennen von {filename}: {e}")
    return i

# ----------------------------------------------------------------------
# Language
# ----------------------------------------------------------------------
def get_final_language(file_path, api_lang=None):
    """Erzwingt deine Sprachregeln."""
    path_lower = file_path.lower()
    # 1. Priorität: Der Ordnername
    if "deutsch" in path_lower: return "de"
    if "english" in path_lower: return "en"
    if "french" in path_lower or "franz" in path_lower: return "fr"
    if "italien" in path_lower: return "it"
    if "spanisch" in path_lower: return "es"

    # 2. Priorität: API/EPUB Mapping (nur die erlaubten)
    allowed = {'de', 'en', 'fr', 'it', 'es'}
    if api_lang:
        clean_api = str(api_lang).lower()[:2]  # nur erste zwei Zeichen (en-us -> en)
        if clean_api in allowed:
            return clean_api
    return "de"  # Fallback

# ----------------------------------------------------------------------
# Normalise Auther
# ----------------------------------------------------------------------
def _normalize_author_name(raw_name):
    """Wandelt 'Nachname, Vorname' oder 'Vorname Nachname' in (Vorname, Nachname) um."""
    if not raw_name:
        return ("", "Unbekannt")

    # Fall 1: Nachname, Vorname
    if "," in raw_name:
        parts = raw_name.split(",", 1)
        return (parts[1].strip(), parts[0].strip())

    # Fall 2: Vorname Nachname (wir nehmen das letzte Wort als Nachname)
    parts = raw_name.split()
    if len(parts) >= 2:
        return (" ".join(parts[:-1]), parts[-1])

    return ("", raw_name)

# ----------------------------------------------------------------------
# SINGLE SCAN IN SCHRITTEN
# ----------------------------------------------------------------------
def extract_topic_from_path(file_path, anchor="Business"):
    """
    Extrahiert die Ordnerstruktur ab einem Anker-Verzeichnis.
    Beispiel: 'D:\\Bücher\\Business\\IT-Bücher\\Python\\Buch.epub'
    -> 'IT-Bücher\\Python'
    """
    normalized_path = os.path.normpath(file_path)
    parts = normalized_path.split(os.sep)

    if anchor in parts:
        idx = parts.index(anchor)
        # Nimm alles nach dem Anker bis vor den Dateinamen
        topic_parts = parts[idx + 1:-1]
        if topic_parts:
            # Wir geben es als String mit Backslashes zurück
            return os.sep.join(topic_parts)
    return None


def detect_real_extension(file_path):
    """Erkennt das wahre Format an den Datei-Headern."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(100)

            # EPUBs sind ZIP-Archive und starten mit 'PK'
            if header.startswith(b'PK\x03\x04'):
                return '.epub'

            # MOBI/AZW3 haben 'BOOKMOBI' ab Byte 60
            if b'BOOKMOBI' in header[60:100] or b'TEXtREAd' in header[60:100]:
                return '.mobi'

            # PDFs starten immer mit %PDF
            if header.startswith(b'%PDF'):
                return '.pdf'
    except:
        pass
    return None

def is_mobi_readable(file_path):
    """
    Prüft, ob eine MOBI/AZW3-Datei lesbar ist, indem die Magic Bytes
    an der korrekten Position im Header validiert werden.
    """
    try:
        if not os.path.exists(file_path):
            return False

        with open(file_path, 'rb') as f:
            # Wir lesen die ersten 100 Bytes.
            # MOBI-Dateien sind PalmDB-basiert.
            # Der Identifikator 'BOOKMOBI' steht ab Byte 60.
            header = f.read(100)

            # Prüfung auf gängige Kindle-Identifikatoren
            is_mobi = b'BOOKMOBI' in header[60:100]
            is_palm_text = b'TEXtREAd' in header[60:100]  # Älteres Palm-Format

            return is_mobi or is_palm_text
    except Exception as e:
        print(f"⚠️ Fehler beim Lesen des MOBI-Headers ({file_path}): {e}")
        return False

# Beispiel für die Verwendung:
if __name__ == '__main__':
    path1 = 'D:/Books/Autor/Star Wars - 03 - Die Rache der Sith (2005).epub'
    print(f"File 1: {extract_info_from_filename(path1)}")

    path2 = 'D:/Books/Autor/(1997)-Standalone Buch.epub'
    print(f"File 2: {extract_info_from_filename(path2)}")

    path3 = 'D:/Books/Autor/Titel ohne alles.epub'
    print(f"File 3: {extract_info_from_filename(path3)}")

    # Pfad hier anpassen (z.B. "C:/MeinOrdner" oder ein relativer Pfad ".")
    target_path = r"D:\Bücher\Brain-Teasers"
    res = clean_file_names(target_path)
    print(f" {res} Gedankenstriche ersetzt")