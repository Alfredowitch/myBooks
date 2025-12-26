"""
DATEI: check.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Kümmert sich um die Verarbeitung von Missmatch in Autoren oder Titel von filename und epub.
              Alle Missmatches werden in eine Datenstruktur geschrieben und können ausgegeben werden.
              Das erzeugte txt-File kann mit dem Book-Browser geladen werden.
"""
# file_utils.py (oder in deinem Hauptskript)
import re
import os


# Die normalize_text Funktion bleibt unverändert, da sie großartig ist
# für einen robusten, Fall-unabhängigen Textvergleich.
def normalize_text(text: str) -> str:
    """
    Bereinigt Text (Titel/Autorennamen) für einen robusten, Fall-unabhängigen Vergleich.
    """
    if not isinstance(text, str):
        return ""

    text = text.lower()
    # 1. Satzzeichen entfernen (insbesondere Punkte und Kommas)
    text = re.sub(r'[.,;\'"]', '', text)
    # 2. Bindestriche und extra Leerzeichen entfernen/ersetzen
    text = re.sub(r'[\s\-]+', ' ', text).strip()
    # 3. Einfache Akzent-Normalisierung
    text = text.replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
    text = text.replace('é', 'e').replace('á', 'a').replace('à', 'a').replace('ç', 'c')

    # Optional: Trenne Untertitel ab (z.B. Titel: Untertitel)
    text = text.split(':')[0].strip()

    return text


def normalize_author_tuple(author_tuple: tuple) -> tuple:
    """Bereinigt die Strings innerhalb eines (Vorname, Nachname) Tupels."""
    if not isinstance(author_tuple, tuple) or len(author_tuple) != 2:
        return ("", "")

    # Nutze die vorhandene normalize_text Funktion für die Reinigung
    firstname_normalized = normalize_text(author_tuple[0])
    lastname_normalized = normalize_text(author_tuple[1])

    return (firstname_normalized, lastname_normalized)


def check_for_mismatch(file_path: str, file_title: str, epub_title: str,
                       file_authors: list, epub_authors: list,
                       epub_series_name: str = None, epub_series_number: str = None) -> dict | None:
    """
        Für jedes Buch geben wir ein Dictionary zurück
            {
                'filename': 'Boris Gloger...epub',
                'full_path': 'D:\\Bücher\\Business\\Agile\\Boris Gloger...epub',
                'file_author': [('Gloger', 'Boris'), ('Rösner', 'Dieter')],
                'epub_author': [('Rösner Boris Gloger', 'Dieter')],
                'epub_series_name': None,
                'epub_series_number': None
            }
        Der Scanner baut daraus eine Liste von Dictionaries
        mismatch_list.append(neues_dict)
    """

    mismatch = {}
    filename = os.path.basename(file_path)

    # 1. AUTORENPRÜFUNG
    # Normalisieren
    norm_file = [normalize_author_tuple(a) for a in file_authors]
    norm_epub = [normalize_author_tuple(a) for a in epub_authors]

    # Sortieren der normalisierten Listen (komplette Tupel sortieren ist sicherer)
    sorted_file = sorted(norm_file)
    sorted_epub = sorted(norm_epub)

    # Vergleich
    if sorted_file != sorted_epub:
        # Check: Sind es vielleicht dieselben Nachnamen, aber einer hat keinen Vornamen?
        # Das verhindert Mismatches bei "Oetker" vs "Alexander Oetker"
        file_lasts = sorted([a[1] for a in norm_file if a[1]])
        epub_lasts = sorted([a[1] for a in norm_epub if a[1]])

        if file_lasts != epub_lasts:
            mismatch['file_author'] = file_authors
            mismatch['epub_author'] = epub_authors

    # 2. TITELPRÜFUNG
    if file_title and epub_title:
        n_file_title = normalize_text(file_title)
        n_epub_title = normalize_text(epub_title)

        # Wenn der eine Titel im anderen enthalten ist, ist das oft okay
        # (z.B. "Der Titel" vs "Der Titel: Ein Krimi")
        if n_file_title != n_epub_title:
            if n_file_title not in n_epub_title and n_epub_title not in n_file_title:
                mismatch['file_title'] = file_title
                mismatch['epub_title'] = epub_title
                if epub_series_name or epub_series_number:
                    mismatch['epub_series_name'] = epub_series_name
                    mismatch['epub_series_number'] = epub_series_number

    if mismatch:
        mismatch['filename'] = filename
        # NEU: Wir speichern den vollen, übergebenen Pfad ab
        mismatch['full_path'] = os.path.abspath(file_path)
        return mismatch

    return None
