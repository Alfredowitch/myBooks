import re
import os
import logging

# Universelle Konstante lokal definiert für maximale Unabhängigkeit
EM_DASH = "—"


def process_local_source(clean_path: str) -> dict:
    """Kombiniert Pfad- und Filename-Analyse."""
    path_info = _extract_from_path(clean_path)
    logging.debug(f"   Path-Scan: {path_info}")
    file_info = _extract_from_filename(clean_path)
    logging.debug(f"   File-Scan: {file_info}")
    # Verschmelzen: Dateiname hat Vorrang vor Pfad-Keywords
    result = {**path_info, **file_info}
    logging.debug(f"   Matching: {result}")
    return result


def _extract_from_filename(path: str) -> dict:
    """Extrahiert Autoren, Serie, Index, Jahr und Titel aus dem Dateinamen."""
    filename = os.path.basename(path)
    remaining, extension = os.path.splitext(filename)
    remaining = remaining.strip()

    info = {
        'authors': set(),
        'series_name': None,
        'series_number': 0.0,
        'year': None,
        'title': "",
        'ext': extension.lower()
    }

    # 1. Autoren isolieren
    if EM_DASH in remaining:
        parts = remaining.split(EM_DASH, 1)
        authors_raw = parts[0].strip()
        remaining = parts[1].strip()
        # Listen und Tuple sind veränderlich, daher in der Extraktion sind sie Tuple:
        if authors_raw:
            for a in re.split(r'[&;]| et ', authors_raw):
                # Da author_data garantiert ein Tupel ist (laut Definition)
                author_data = _normalize_author_name(a.strip())
                # Ein Set hat kein append, weil es keine feste Reihenfolge gibt.
                info['authors'].add(author_data)

    # 2. Jahr isolieren
    year_match = re.search(r'\((\d{4})\)', remaining)
    if year_match:
        info['year'] = year_match.group(1)
        remaining = remaining.replace(year_match.group(0), "").strip()

    # 3. Serie & Titel Logik (Anker: Strich mit Ziffer davor)
    # Erläuterung des neuen Patterns:
    # ^          -> Anfang des verbleibenden Strings
    # (.*?)      -> Gruppe 1: Serie (alles bis zur Nummer)
    # (\d+(?:[.,]\d+)?) -> Gruppe 2: Die Nummer (muss direkt vor dem Trenner stehen)
    # \s*[-–—]\s* -> Der Anker: Ein Bindestrich/Gedankenstrich, optional von Leerzeichen umgeben
    # (.*)       -> Gruppe 3: Der Titel (Rest des Strings)
    pattern_with_anchor = r'^(.*?)(\d+(?:[.,]\d+)?)\s*[-–—]\s*(.*)$'

    m = re.search(pattern_with_anchor, remaining)

    if m:
        series_raw = m.group(1).strip()
        number_str = m.group(2)
        title_raw = m.group(3).strip()

        # Zuweisung der Nummer
        info['series_number'] = number_str
        info['series_index'] = float(number_str.replace(',', '.'))
        info['title'] = title_raw

        # Logik für den Seriennamen
        if series_raw:
            info['series_name'] = series_raw
        else:
            # Fall "04-Vector" -> Serie wird Nachname des Autors
            if info['authors']:
                author_list = list(info['authors'])
                first_author = author_list[0]  # Das ist jetzt ein Tuple (Vorname, Nachname)

                if len(first_author[0]) >= 2 or len(first_author[1]) >= 2:
                    info['series_name'] = first_author[1]  # Nachname
                else:
                    info['series_name'] = first_author[0]  # Vorname/Einzelname
    else:
        # Fall: Kein Muster "Zahl - Titel" gefunden
        info['title'] = remaining
        info['series_name'] = None
        info['series_index'] = 0.0

    return info


def _extract_from_path(path: str) -> dict:
    """Analysiert die Ordnerstruktur mit Deep-Scan für _byGenre."""
    path_parts = path.split('/')

    region = None
    manual_genre = "Krimi"  # Default
    keywords = set()

    # 1. Sprache erkennen
    language = _get_final_language(path)

    # 2. Spezial-Ordner Logik (Priorisiert)
    if 'Business' in path_parts:
        manual_genre = "Sachbuch"
        idx = path_parts.index('Business')
        topic_parts = path_parts[idx + 1:-1]
        keywords.update(topic_parts)

    elif 'Reisen' in path_parts:
        manual_genre = 'Reisebericht'
        idx = path_parts.index('Reisen')
        region_parts = path_parts[idx + 1: -1]
        if region_parts:
            region = " / ".join(region_parts)
            keywords.update(region_parts)

    elif '_EasyReader' in path_parts:
        manual_genre = "Sprachbuch"
        keywords.add("Easy Reader")

    elif '_byGenre' in path_parts:
        idx = path_parts.index('_byGenre')
        # SF (direkt nach _byGenre)
        if idx + 1 < len(path_parts):
            manual_genre = path_parts[idx + 1]
            # Alles danach sind Sub-Keywords (Star Trek, Voyager, etc.)
            sub_parts = path_parts[idx + 2: -1]  # Bis zum vorletzten (letztes ist die Datei)
            keywords.update(sub_parts)

    elif '_byRegion' in path_parts:
        idx = path_parts.index('_byRegion')
        if idx + 1 < len(path_parts):
            region = path_parts[idx + 1]
            sub_regions = path_parts[idx + 2: -1]
            if sub_regions:
                keywords.update(sub_regions)

    return {
        'language': language,
        'region': region,
        'genre': manual_genre,
        'keywords': keywords
    }


def _normalize_author_name(raw_name: str) -> tuple:
    """Wandelt Namen in (Vorname, Nachname) um."""
    if not raw_name: return ("", "Unbekannt")
    name = re.sub(r'[\(\[].*?[\)\]]', '', raw_name).strip().replace('  ', ' ')

    if "," in name:
        parts = name.split(",", 1)
        return (parts[1].strip(), parts[0].strip())

    parts = name.strip().split()
    if len(parts) >= 2:
        return (" ".join(parts[:-1]), parts[-1])
    return ("", name if name else "Unbekannt")


def _get_final_language(path: str) -> str:
    path_lower = path.lower()
    mapping = {"deutsch": "de", "english": "en", "french": "fr", "italien": "it", "spanisch": "es"}
    for key, code in mapping.items():
        if key in path_lower: return code
    return "de"


if __name__ == "__main__":
    file = "Kommissar Erlendur01-Menschensöhne"
    info = _extract_from_filename(file)
    print(f"Pfad: {file}")
    print(f"Titel: {info['title']}")
    print(f"Serie: {info['series_name']}")
    print(f"Nr: {info['series_number']}")
    print(f"Autoren: {info['authors']}")

