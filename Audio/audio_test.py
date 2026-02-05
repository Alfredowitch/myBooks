import os
import re
import sqlite3
from Zoom.utils import AUDIO_BASE, DB_PATH, sanitize_path
from Audio.book_data import BookData  # Angenommen, dein Code liegt in models.py


def parse_series_logic(dir_name, author_name):
    # Nutzt die universelle Funktion
    s_name, s_idx, title = match_series_pattern(dir_name, fallback_name=author_name)

    # Für dein Audiobook-Skript brauchst du nur den Namen
    return s_name if s_name else None


def match_series_pattern(text, fallback_name="Unbekannt"):
    """
    Universelle Logik für: 'Serienname 01.5 - Titel'
    Funktioniert für E-Book Filenames und Audiobook Verzeichnisse.
    """
    # 1. Vorab-Reinigung (Autor-Trenner bei E-Books entfernen)
    if " — " in text:
        text = text.split(" — ")[-1]

    # 2. Suche nach dem Trenner-Bindestrich
    # Wir suchen den ERSTEN Bindestrich, der nach einer Zahl kommt
    match = re.search(r'^(.+?)\s?[-–—]\s?(.*)$', text)

    if match:
        potential_series_part = match.group(1).strip()
        title_part = match.group(2).strip()

        # 3. Zahl am Ende des ersten Teils extrahieren (Float-sicher)
        num_match = re.search(r'(.*?)\s*(\d+(?:[.,]\d+)?)$', potential_series_part)

        if num_match:
            series_name = num_num_match.group(1).strip()
            raw_idx = num_match.group(2).replace(',', '.')
            try:
                series_index = float(raw_idx)
            except ValueError:
                series_index = 0.0

            # Falls nur eine Nummer da war (z.B. "01 - Titel"),
            # ist der Serienname der fallback_name (der Autor)
            return (series_name or fallback_name, series_index, title_part)

    # Kein Serien-Muster erkannt -> Alles ist Titel
    return (None, 0.0, text)


def scan_audiobook_series(base_path):
    mgr = BookData()
    results = []

    if not os.path.exists(base_path):
        print(f"Pfad nicht gefunden: {base_path}")
        return

    # Ebene 1: Autoren
    for author_dir in os.listdir(base_path):
        author_path = os.path.join(base_path, author_dir)
        if not os.path.isdir(author_path):
            continue

        # Ebene 2 durchsuchen
        for l2_name in os.listdir(author_path):
            l2_path = os.path.join(author_path, l2_name)
            if not os.path.isdir(l2_path):
                continue

            # Prüfen auf Files in Ebene 2
            files_l2 = [f for f in os.listdir(l2_path) if f.lower().endswith('.mp3')]

            detected_series = None

            if not files_l2:
                # Ebene 2 hat keine Files -> Es ist eine Serie (Fall a)
                # (Spezialfall Perry Rhodan Ebene 3 Ignorieren wird durch die Struktur abgefangen)
                detected_series = l2_name
            else:
                # Ebene 2 hat Files -> Checke auf Zahlen im Namen (Fall b & c)
                detected_series = parse_series_logic(l2_name, author_dir)

            if detected_series:
                # Abgleich mit DB über deinen Manager
                db_id = mgr.find_best_serie_match(detected_series)
                db_name = "KEIN TREFFER"
                if db_id:
                    # Lade echten Namen aus der DB für die Anzeige
                    db_serie = mgr.get_series_details(db_id)
                    db_name = db_serie.name if db_serie.name else db_serie.name_de

                results.append(f"{author_dir} - {detected_series} - {db_name}")

    # Ausgabe der Liste
    print("Autor - Serie - Erkannte Serie aus der DB")
    print("-" * 60)
    for line in sorted(list(set(results))):
        print(line)


if __name__ == "__main__":
    target_path = sanitize_path(r"M:\Hörbuch-De")
    scan_audiobook_series(target_path)