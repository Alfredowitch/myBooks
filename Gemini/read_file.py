"""
DATEI: read_file.py
PROJEKT: MyBook-Management (v1.2.0)
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

def _normalize_author_name(raw_name_string):
    """
    Normalisiert Autorennamen. Erkennt 'Vorname Nachname' und 'Nachname, Vorname'.
    Gibt (Vorname, Nachname) zurück.
    """
    if not isinstance(raw_name_string, str) or not raw_name_string.strip():
        return None

    raw_name = raw_name_string.strip()

    # Fall 1: Format "Nachname, Vorname" (erkannt durch das Komma)
    if "," in raw_name:
        parts = raw_name.split(",", 1) # Nur am ersten Komma splitten
        lastname = parts[0].strip()
        firstname = parts[1].strip() if len(parts) > 1 else ""
        return (firstname, lastname)

    # Fall 2: Format "Vorname Nachname" (oder nur ein Teil)
    parts = raw_name.split()

    if len(parts) >= 2:
        # Alles außer dem letzten Wort ist Vorname, das letzte ist Nachname
        firstname = " ".join(parts[:-1])
        lastname = parts[-1]
        return (firstname, lastname)
    elif len(parts) == 1:
        # Nur ein Teil (Nachname)
        return ("", parts[0])

    return None


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

def extract_info_from_filename(file_path):
    """
    Extrahiert Autoren, Serie, Seriennummer, Titel und das Jahr aus einem Dateipfad
    basierend auf der Konvention: Autoren — Serie [Nummer] — Titel (Jahr).

    Args:
        file_path (str): Der vollständige Pfad zur Datei.

    Returns:
        dict: Ein Dictionary mit den extrahierten Informationen.
    """

    filename = os.path.basename(file_path)

    # 1. Dateierweiterung entfernen
    name_without_ext, _ = os.path.splitext(filename)
    raw_info_string = name_without_ext.strip()

    # Initialisiere die Ergebnisse
    info = {
        'title': raw_info_string,  # Standard: Ganzer String
        'authors': [],  # NEU: Liste von (Vorname, Nachname) Tupeln
        'series_name': None,
        'series_number': None,
        'year': None
    }

    # --- 2. Autoren-Trennung (Prio 1) ---
    if '—' in raw_info_string:
        parts = raw_info_string.split('—', 1)
        authors_string = parts[0].strip()
        title_series_string = parts[1].strip()

        # 2a. Autoren-Normalisierung
        if authors_string:
            raw_author_names = [a.strip() for a in authors_string.split('&')]

            for raw_name in raw_author_names:
                normalized_tuple = _normalize_author_name(raw_name)
                if normalized_tuple:
                    info['authors'].append(normalized_tuple)

        raw_info_string = title_series_string

    # --- 3. Suche nach dem Jahr im Format (xxxx) ---
    match_year_end = re.search(r'\s\((19|20)\d{2}\)$', raw_info_string)

    if match_year_end:
        year_str = match_year_end.group(0).strip()[1:-1]
        info['year'] = year_str
        raw_info_string = re.sub(r'\s\((19|20)\d{2}\)$', '', raw_info_string).strip()

    match_year_start = re.match(r'^\((19|20)\d{2}\)-', raw_info_string)
    if match_year_start and not info['year']:  # Korrigiert: Jetzt 'year' prüfen
        year_str = match_year_start.group(0).strip()[1:-2]
        info['year'] = year_str  # Korrigiert: Zuweisung zu 'year'
        raw_info_string = re.sub(r'^\((19|20)\d{2}\)-', '', raw_info_string).strip()

    # --- 4. Suche nach Serie und Seriennummer ---
    # Muster: [Serienname] [Nummer]-[Titel]
    match_series = re.match(r'(.+?)\s+(\d{1,3})[\s\-](.+)', raw_info_string)

    if match_series:
        info['series_name'] = match_series.group(1).strip()
        info['series_number'] = match_series.group(2).strip()
        info['title'] = match_series.group(3).strip()
    else:
        info['title'] = raw_info_string.strip()

    # Die Ausnahme: [Nummer]-[Titel] am Anfang, z.B. "01-Signora Commissaria..."
    if not info['series_name'] and info['title'] and re.match(r'(\d{1,3})\-+(.+)', info['title']):
        match_only_number = re.match(r'(\d{1,3})\-+(.+)', info['title'])
        if match_only_number:
            info['series_number'] = match_only_number.group(1).strip()

            # --- 🚀 PRAGMATISCHE HEURISTIK HIER ANWENDEN ---
            # Der Titel ist aktuell: 'Signora Commissaria und die dunklen Geister'
            title_part = match_only_number.group(2).strip()
            title_words = title_part.split()

            if title_words:
                # Das erste Wort als potenziellen Seriennamen verwenden
                potential_series_name = title_words[0].strip()
                info['series_name'] = potential_series_name  # Setze 'Signora'

                # Der Titel muss nun den Rest des Strings sein
                # Wir behalten den bereinigten Titel, den wir aus dem Regex bekommen haben
                info['title'] = title_part
            else:
                # Nur Titel ohne Text (unwahrscheinlich)
                info['title'] = title_part

    # 5. Finaler Titel-Check: Wenn die Nummer/Serie am Ende stand (z.B. Titel [01]),
    # müssen wir sicherstellen, dass wir nicht den Titel versehentlich mit dem ersten Wort überschreiben.
    # Da dies durch die frühe Regex gelöst wird, ist der letzte Titel-Wert,
    # der gesetzt wurde, der reinste.

    return info


def derive_metadata_from_path(file_path):
    """
    Leitet Sprache, Region, Genre und Keywords aus der neuen Ordnerstruktur ab.
    """
    path_parts = os.path.normpath(file_path).split(os.sep)
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
        manual_genre = "Business & Sachbuch"

    # 3. Spezial-Ordner auswerten (Genre, Region, Sprache, Easy Reader)
    for i, part in enumerate(path_parts):

        # A) Genre aus _sortiertGenre/GenreName/Autor
        if part == '_byGenre':
            if i + 1 < len(path_parts):
                manual_genre = path_parts[i + 1]

        # B) Region aus _sortiertRegion/RegionName/Autor
        elif part == '_bytRegion':
            if i + 1 < len(path_parts):
                region = path_parts[i + 1]

        # C) Deutsch lernen / Sprache
        elif part == '_Sprache':
            manual_genre = 'Sprache'
            keywords.append('Deutsch lernen')

        # D) Easy Reader (z.B. A1 - 500 Wörter)
        elif part == '_Easy Reader':
            manual_genre = 'Easy Reader'
            if i + 1 < len(path_parts):
                # Das Niveau (A1 etc.) als Keyword speichern
                keywords.append(path_parts[i + 1])

    return language, region, manual_genre, keywords


import os


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