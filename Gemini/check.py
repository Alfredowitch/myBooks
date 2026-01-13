"""
DATEI: check.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Kümmert sich um die Verarbeitung von Missmatch in Autoren oder Titel von filename und epub.
              Alle Missmatches werden in eine Datenstruktur geschrieben und können ausgegeben werden.
              Das erzeugte txt-File kann mit dem Book-Browser geladen werden.
"""
import os

from Apps.book_data import BookData
from Gemini.file_utils import normalize_text, normalize_author_tuple, sanitize_path

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

    # Vergleich
    if sorted(norm_file) != sorted(norm_epub):
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
        mismatch['full_path'] = sanitize_path(file_path)
        return mismatch
    return None


class Book_Analyser:
    @staticmethod
    def check_and_cleanup_paths():
        """
        Prüft alle Einträge in der DB auf Existenz im Filesystem.
        Verschiebt verwaiste Pfade in die Notizen und leert das Pfad-Feld.
        Gibt einen Report über alle Änderungen zurück.
        """
        report = []
        # Alle Bücher aus der DB laden
        # Wir nutzen search(), um alle Objekte zu erhalten
        all_books = BookData.search()

        print(f"Starte Prüfung von {len(all_books)} Einträgen...")

        updated_count = 0

        for book in all_books:
            # Falls das Feld bereits leer ist, überspringen
            if not book.path:
                continue

            # Pfad-Existenz prüfen
            # os.path.exists funktioniert dank deiner Normalisierung im __post_init__
            if not os.path.exists(book.path):
                old_path = book.path

                # 1. Notiz erstellen / ergänzen
                missing_note = f"File fehlt: {old_path}"
                if book.notes:
                    book.notes = f"{book.notes}\n{missing_note}"
                else:
                    book.notes = missing_note

                # 2. Pfad-Feld leeren
                book.path = ""

                # 3. In den Report aufnehmen
                report.append({
                    "id": book.id,
                    "title": book.title,
                    "old_path": old_path,
                    "status": "Pfad entfernt, in Notizen verschoben"
                })

                # 4. Objekt speichern
                if book.save():
                    updated_count += 1
                else:
                    print(f"Fehler beim Update von Buch ID {book.id}")

        print(f"Prüfung abgeschlossen. {updated_count} Einträge korrigiert.")
        return report

    @staticmethod
    def print_report(report):
        """Gibt den Report sauber formatiert aus."""
        if not report:
            print("Alles in Ordnung. Keine verwaisten Pfade gefunden.")
            return

        print(f"{'ID':<5} | {'Titel':<30} | {'Status'}")
        print("-" * 60)
        for entry in report:
            title_short = (entry['title'][:27] + '...') if len(entry['title']) > 30 else entry['title']
            print(f"{entry['id']:<5} | {title_short:<30} | {entry['status']}")