import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any

# Namespaces für EPUB-Metadaten
NS_DC = {'dc': 'http://purl.org/dc/elements/1.1/'}
NS_OPF = {'opf': 'http://www.idpf.org/2007/opf'}
NS_OCF = {'ocf': 'urn:oasis:names:tc:opendocument:xmlns:container'}


def get_epub_metadata(epub_file_path: str) -> Dict[str, Any]:
    """
    Extrahiert Metadaten aus einem EPUB.
    Wichtig: Diese Funktion ist jetzt 'dumm' – sie normalisiert nicht,
    sondern liefert nur, was sie im XML findet.
    """
    if not zipfile.is_zipfile(epub_file_path):
        return {}

    try:
        with zipfile.ZipFile(epub_file_path, 'r') as zf:
            # 1. OPF Datei finden und parsen
            opf_root, _ = _get_opf_root(zf)
            if opf_root is None:
                return {}

            # 2. Daten extrahieren
            # Wir sammeln hier die Roh-Listen für Autoren und Subjects
            raw_title = _get_dc_element(opf_root, 'title')
            raw_authors = _get_all_dc_elements(opf_root, 'creator')
            raw_subjects = _get_all_dc_elements(opf_root, 'subject')
            raw_description = _get_dc_element(opf_root, 'description')
            raw_language = _get_dc_element(opf_root, 'language')

            # ISBN Suche in allen Identifiers
            all_ids = _get_all_dc_elements(opf_root, 'identifier')
            isbn = None
            for id_str in all_ids:
                clean_id = re.sub(r'[^\dX]', '', id_str.upper())
                if len(clean_id) in [10, 13]:
                    isbn = clean_id
                    break

            # Jahr extrahieren
            raw_date = _get_dc_element(opf_root, 'date')
            clean_year = None
            if raw_date:
                match = re.search(r'\d{4}', raw_date)
                if match: clean_year = match.group(0)

            # 3. Ergebnis-Paket (Rohdaten)
            return {
                'title': raw_title,
                'authors_raw': raw_authors,  # Wir geben die Roh-Strings zurück
                'keywords': raw_subjects,  # subjects wandern in Keywords
                'description': raw_description,
                'isbn': isbn,
                'year': clean_year,
                'language': raw_language
            }

    except Exception:
        return {}


# --- Interne Helfer (ohne Scotty-Abhängigkeit) ---

def _get_opf_root(zf):
    try:
        container_data = zf.read('META-INF/container.xml')
        root = ET.fromstring(container_data)
        opf_element = root.find('.//ocf:rootfile', NS_OCF)
        if opf_element is None: return None, None

        opf_path = opf_element.get('full-path')
        opf_data = zf.read(opf_path)
        return ET.fromstring(opf_data), opf_path
    except:
        return None, None


def _get_dc_element(opf_root, tag_name):
    el = opf_root.find(f".//dc:{tag_name}", NS_DC)
    return el.text.strip() if el is not None and el.text else None


def _get_all_dc_elements(opf_root, tag_name):
    return [el.text.strip() for el in opf_root.findall(f".//dc:{tag_name}", NS_DC) if el.text]