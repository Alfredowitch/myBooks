"""
DATEI: read_epub.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Kümmert sich um das Auslesen von epub-Dateien
             Verwendet jetzt das BookData Model, dabei wird id= 0 und is_read = 0 gesetzt.
             Dies muss beim Speichern beachtet, bzw. ignoriert werden!
"""
import zipfile
import xml.etree.ElementTree as ET
import os
import re
import tempfile
import html # Oben zu den Imports
from typing import Dict, Any

try:
    from Apps.book_data import BookData
except ImportError:
    # Falls das Modul beim Standalone-Test nicht gefunden wird
    BookData = None

# Dublin Core und OPF Namespaces für XML-Parsing
NS_DC = {'dc': 'http://purl.org/dc/elements/1.1/'}
NS_OPF = {'opf': 'http://www.idpf.org/2007/opf'}
NS_OCF = {'ocf': 'urn:oasis:names:tc:opendocument:xmlns:container'}


# --- Hilfsfunktionen für das XML-Parsing ---

def _get_opf_root(zf, epub_path):
    """Liest die container.xml aus dem übergebenen ZipFile (zf) und gibt das Root-Element des OPF-Files zurück."""
    try:
        # 1. Finde OPF-Pfad über container.xml
        container_data = zf.read('META-INF/container.xml')
        root = ET.fromstring(container_data)

        # OPF-Pfad ermitteln
        opf_element = root.find('.//ocf:rootfile', NS_OCF)
        if opf_element is None:
            return None, None

        opf_path = opf_element.get('full-path')

        # 2. Lese OPF-Datei
        opf_data = zf.read(opf_path)
        opf_root = ET.fromstring(opf_data)
        return opf_root, opf_path

    except Exception:
        # Fehler beim Lesen oder Parsen
        return None, None


def clean_html(raw_html):
    if not raw_html: return ""
    # 1. HTML-Entities auflösen (z.B. &#8212; zu —)
    clean = html.unescape(raw_html)
    # 2. Ersetze Block-Elemente durch Zeilenumbrüche
    clean = re.sub(r'<(div|p|br|li|h1|h2)[^>]*>', '\n', clean)
    # 3. Alle restlichen HTML-Tags entfernen
    clean = re.sub(r'<[^>]+>', '', clean)
    # 4. Whitespace-Kosmetik
    clean = re.sub(r'[ \t]+', ' ', clean) # Tabulatoren/Doppel-Leerzeichen weg
    clean = re.sub(r'\n\s*\n+', '\n\n', clean).strip() # Max 2 Umbrüche
    return clean

def _get_dc_element(opf_root, tag_name):
    """Extrahiert den Text eines einzelnen Dublin Core Elements."""
    if opf_root is None: return None
    element = opf_root.find(f".//dc:{tag_name}", NS_DC)
    return element.text.strip() if element is not None and element.text else None


def _get_all_dc_elements(opf_root, tag_name):
    """Extrahiert alle Dublin Core Elemente (Liste)."""
    if opf_root is None: return []
    return [el.text.strip() for el in opf_root.findall(f".//dc:{tag_name}", NS_DC) if el.text]


def _get_cover_image_relative_path(opf_root, opf_path):
    """Sucht den relativen Pfad des Titelbildes innerhalb des EPUB-Containers."""
    if opf_root is None: return None

    # 1. Finde die Cover-ID im Metadaten-Bereich
    cover_meta = opf_root.find(".//opf:metadata/opf:meta[@name='cover']", NS_OPF)

    if cover_meta is not None:
        cover_id = cover_meta.get('content')

        # 2. Finde den Pfad (href) anhand der ID im Manifest
        cover_item = opf_root.find(f".//opf:manifest/opf:item[@id='{cover_id}']", NS_OPF)

        if cover_item is not None:
            relative_image_path = cover_item.get('href')

            # Wir müssen den Pfad relativ zum EPUB-Stammverzeichnis machen.
            opf_dir = os.path.dirname(opf_path)
            full_path = os.path.join(opf_dir, relative_image_path)

            # Auf Linux/Windows-Pfad-Konsistenz achten (EPUBs nutzen oft /)
            return full_path.replace('\\', '/')

    return None


def _extract_and_save_cover(zf, internal_cover_path):
    """
    Extrahiert das Coverbild aus dem ZipFile und speichert es temporär.
    Gibt den Pfad zur temporären Datei zurück oder None bei Fehler.
    """
    if not internal_cover_path:
        return None

    try:
        image_data = zf.read(internal_cover_path)
        _, ext = os.path.splitext(internal_cover_path)
        if not ext:
            ext = '.jpg'

        # Temporäre Datei erstellen und Daten speichern
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode='wb') as temp_file:
            temp_file.write(image_data)
            return temp_file.name

    except Exception as e:
        print(f"FEHLER beim Extrahieren des Covers {internal_cover_path}: {e}")
        return None


def _normalize_author_name(raw_name):
    """
    Normalisiert einen Autorennamen in das Tupel (Vorname, Nachname),
    unabhängig davon, ob er als 'Vorname Nachname' oder 'Nachname, Vorname' vorliegt.
    """
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None

    raw_name_processed = raw_name.strip()

    # Fall 1: 'Nachname, Vorname'
    if ',' in raw_name_processed:
        try:
            lastname_part, firstname_part = [part.strip() for part in raw_name_processed.split(',', 1)]
            return (firstname_part, lastname_part)
        except ValueError:
            pass

    # Fall 2: 'Vorname Nachname' (oder nur ein Name)
    parts = raw_name_processed.split()

    if len(parts) >= 2:
        firstname = " ".join(parts[:-1])
        lastname = parts[-1]
        return (firstname, lastname)
    elif len(parts) == 1:
        return ("", parts[0])

    return None


def _split_title_series(full_title):
    """
    Zerlegt einen vollen Titel, der eine Serie enthält, in die Teile:
    (reiner Titel, Serienname, Seriennummer)
    """
    if not full_title or not isinstance(full_title, str):
        return full_title, None, None

    title = full_title.strip()
    series_name = None
    series_number = None

    # Muster: [Serienname] [Nummer] - [Titel]
    match_series = re.match(r'(.+?)\s+(\d{1,3})\s*[—\-]\s*(.+)', title)

    if match_series:
        series_name = match_series.group(1).strip()
        series_number = match_series.group(2).strip()
        title = match_series.group(3).strip()
    else:
        # Suche nach Nummer am Ende: [Titel] [Nummer]
        match_number_at_end = re.search(r'\s(\d{1,3})$', title)
        if match_number_at_end:
            series_number = match_number_at_end.group(1).strip()
            title = re.sub(r'\s(\d{1,3})$', '', title).strip()

            title_words = title.split()
            if len(title_words) > 1:
                series_name = title_words[0].strip()
                title = " ".join(title_words[1:]).strip()

        # Suche nach Nummer am Anfang: [Nummer]-[Titel]
        elif re.match(r'(\d{1,3})\s*[—\-]\s*(.+)', title):
            match_only_number = re.match(r'(\d{1,3})\s*[—\-]\s*(.+)', title)
            if match_only_number:
                series_number = match_only_number.group(1).strip()
                title = match_only_number.group(2).strip()

                title_words = title.split()
                if title_words:
                    series_name = title_words[0].strip()

    return title, series_name, series_number


# --- Die Hauptfunktion für deinen Scan ---

def get_epub_metadata(epub_file_path) -> Dict[str, Any]:
    """
    Extrahiert alle priorisierten Metadaten aus einem EPUB und gibt sie
    in einem Dictionary gemäß dem finalen Schema der BookData-Klasse zurück.
    """
    try:
        with zipfile.ZipFile(epub_file_path, 'r') as zf:
            opf_root, opf_path = _get_opf_root(zf, epub_file_path)
            if opf_root is None:
                print(f"WARNUNG: Konnte Metadaten aus {epub_file_path} nicht lesen.")
                return {}

            # --- Metadaten-Rohdaten einlesen ---
            raw_title = _get_dc_element(opf_root, 'title')
            raw_description = _get_dc_element(opf_root, 'description')
            book_description = clean_html(raw_description) if raw_description else ""
            raw_authors = _get_all_dc_elements(opf_root, 'creator')
            keywords_epub = _get_all_dc_elements(opf_root, 'subject')
            raw_identifier = _get_dc_element(opf_root, 'identifier')
            raw_language = _get_dc_element(opf_root, 'language')

            # --- Cover-Pfad finden und BILD EXTRAHIEREN ---
            internal_cover_path = _get_cover_image_relative_path(opf_root, opf_path)
            image_path = _extract_and_save_cover(zf, internal_cover_path)

            # --- 1. Autoren-Normalisierung ---
            normalized_authors = []
            for raw_author_string in raw_authors:
                author_parts = re.split(r'[;]', raw_author_string)
                for part in author_parts:
                    normalized_tuple = _normalize_author_name(part.strip())
                    if normalized_tuple:
                        normalized_authors.append(normalized_tuple)

            # --- 2. Titel-Zerlegung (Serie, Nummer, Titel) ---
            title, series_name, series_number = _split_title_series(raw_title)

            # ISBN-Extraktion
            isbn = raw_identifier.split(':')[-1] if raw_identifier and ':' in raw_identifier else raw_identifier

            # --- 3. Erstellung des BookData-Objekts (Wurzel-Korrektur) ---
            # Wenn BookData verfügbar ist, geben wir ein Objekt zurück, sonst ein sauberes Dict
            data_content = {
                'path': epub_file_path,  # Geändert von file_path auf path
                'title': title or "Unbekannter Titel",
                'authors': normalized_authors,
                'isbn': isbn,
                'year': _get_dc_element(opf_root, 'date')[:4] if _get_dc_element(opf_root, 'date') else None,
                'language': raw_language,
                'series_name': series_name,
                'series_number': series_number,
                'description': book_description,
                'keywords': keywords_epub,
                'image_path': image_path,  # Mapping auf Attributname in BookData
                'is_read': 0
            }
            # --- FINAL: Dictionary MAPPING AUF BOOKMETADATA-SCHLÜSSEL ---
            return data_content


    except zipfile.BadZipFile:
        print(f"FEHLER: '{epub_file_path}' ist keine gültige Zip-Datei (EPUB).")
        return {}
    except Exception as e:
        print(f"Kritischer Fehler in get_epub_metadata: {e}")
        return {}

# --- Beispiel-Aufruf (zum Testen) ---
# if __name__ == '__main__':
#     # ... (deine Apps-Logik)