"""
DATEI: check.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Validiert Mismatches zwischen Dateinamen und EPUB-Metadaten.
              Bietet Tools zur Bereinigung verwaister Pfade in der Datenbank.
"""
import os
from typing import Optional, List, Dict, Any

from Audio.book_data import BookData
from Zoom.utils import normalize_text, normalize_author_tuple, sanitize_path


def check_for_mismatch(file_path: str, file_title: str, epub_title: str,
                       file_authors: list, epub_authors: list,
                       epub_series_name: str = None, epub_series_number: str = None) -> Optional[Dict[str, Any]]:
    """
    Vergleicht Dateinamen-Metadaten mit EPUB-Tags und gibt bei Abweichungen
    ein Dictionary für die mismatch_list zurück.
    """
    mismatch = {}
    filename = os.path.basename(file_path)

    # 1. AUTORENPRÜFUNG
    # Normalisieren der Tupel (Vorname, Nachname)
    norm_file = [normalize_author_tuple(a) for a in file_authors]
    norm_epub = [normalize_author_tuple(a) for a in epub_authors]

    if sorted(norm_file) != sorted(norm_epub):
        # Defensiver Check: Vergleiche nur Nachnamen (ignoriert Initialen-Unterschiede)
        file_lasts = sorted([a[1] for a in norm_file if a[1]])
        epub_lasts = sorted([a[1] for a in norm_epub if a[1]])

        if file_lasts != epub_lasts:
            mismatch['file_author'] = file_authors
            mismatch['epub_author'] = epub_authors

    # 2. TITELPRÜFUNG
    if file_title and epub_title:
        n_file_title = normalize_text(file_title)
        n_epub_title = normalize_text(epub_title)

        # Mismatch nur, wenn keiner den anderen beinhaltet (Sub-Titel Ignoranz)
        if n_file_title != n_epub_title:
            if n_file_title not in n_epub_title and n_epub_title not in n_file_title:
                mismatch['file_title'] = file_title
                mismatch['epub_title'] = epub_title
                if epub_series_name or epub_series_number:
                    mismatch['epub_series_name'] = epub_series_name
                    mismatch['epub_series_number'] = epub_series_number

    if mismatch:
        mismatch['filename'] = filename
        mismatch['full_path'] = sanitize_path(file_path)
        return mismatch

    return None


class Book_Analyser:
    @staticmethod
    def check_and_cleanup_paths() -> List[Dict[str, Any]]:
        """
        Prüft alle Einträge in der DB auf Existenz im Filesystem.
        Verschiebt verwaiste Pfade in die Notizen des Book-Atoms.
        """
        report = []
        # Lädt alle BookData-Manager-Instanzen aus der DB
        all_managers = BookData.search()

        print(f"Starte Prüfung von {len(all_managers)} Einträgen...")
        updated_count = 0

        for manager in all_managers:
            # Zugriff auf das Book-Atom
            b = manager.book

            if not b.path:
                continue

            # Pfad-Existenz prüfen
            if not os.path.exists(b.path):
                old_path = b.path

                # 1. Notiz im Book-Atom erstellen
                missing_note = f"File fehlt: {old_path}"
                if b.notes:
                    b.notes = f"{b.notes}\n{missing_note}"
                else:
                    b.notes = missing_note

                # 2. Pfad-Feld leeren (Datei existiert nicht mehr)
                b.path = ""
                # is_complete zurücksetzen, da das File weg ist
                b.is_complete = 0

                # 3. Report-Eintrag
                report.append({
                    "id": b.id,
                    "title": b.title,
                    "old_path": old_path,
                    "status": "Pfad entfernt, in Notizen verschoben"
                })

                # 4. Gesamten Manager (Aggregat) speichern
                if manager.save():
                    updated_count += 1
                else:
                    print(f"⚠️ Fehler beim Update von Buch ID {b.id}")

        print(f"Prüfung abgeschlossen. {updated_count} Einträge korrigiert.")
        return report

    @staticmethod
    def print_report(report: List[Dict[str, Any]]):
        """Formatiert die Ausgabe der verwaisten Pfade."""
        if not report:
            print("✅ Alles in Ordnung. Keine verwaisten Pfade gefunden.")
            return

        print(f"\n{'ID':<5} | {'Titel':<35} | {'Status'}")
        print("-" * 75)
        for entry in report:
            title_short = (entry['title'][:32] + '...') if len(entry['title']) > 35 else entry['title']
            print(f"{entry['id']:<5} | {title_short:<35} | {entry['status']}")