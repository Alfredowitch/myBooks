"""
DATEI: D_Navigation/serie_bridge.py
BESCHREIBUNG der Bridge:
Hier wird entschieden, welche DB-Aktion welche Datei-Aktion auslöst.
    - merge_series, delete_series_safe, update_book_path_logic.
Navigation (view) kümmert sich nur um die Pixel und Benutzer-Interaktion.
Search Engine liefert die Daten
"""
import json
import pandas as pd
from Engineering.search_service import SearchService
from Engineering.book_service import BookService as Scotty

class SeriesBridge:
    def __init__(self):
        self.view = None
        self.full_df = pd.DataFrame()
        self.current_series_id = None

    def load_initial_data(self):
        """Holt alle Serien und schiebt sie in die View."""
        print("[DEBUG] Bridge: Starte load_initial_data...")

        # 1. Daten holen
        self.full_df = SearchService.find_all_series_summary_df()

        # 2. Prüfen, was zurückkam
        if self.full_df is None:
            print("[DEBUG] Bridge: FEHLER! SearchService hat None zurückgegeben.")
            return

        anzahl = len(self.full_df)
        print(f"[DEBUG] Bridge: {anzahl} Serien vom SearchService erhalten.")

        # 3. View benachrichtigen
        if self.view:
            print("[DEBUG] Bridge: Rufe view.update_series_list auf...")
            self.view.update_series_list(self.full_df)
        else:
            print("[DEBUG] Bridge: WARNUNG! Keine View in der Brücke registriert.")

    def filter_series(self, query):
        if self.full_df.empty: return

        if not query.strip():
            self.view.update_series_list(self.full_df)
            return

        # Wir suchen in 'name' und 'author_full' (NICHT author_main!)
        mask = (self.full_df['name'].str.contains(query, case=False, na=False) |
                self.full_df['author_full'].str.contains(query, case=False, na=False))

        self.view.update_series_list(self.full_df[mask])

    def select_series(self, s_id):
        """Wird aufgerufen, wenn links eine Serie angeklickt wird."""
        self.current_series_id = int(s_id)
        print(f"[BRIDGE] Lade Details für Serie-ID: {self.current_series_id}")

        # 1. Das "Atom" für die Mitte laden (SeriesTData)
        # Das Atom ist unser Daten-Objekt für den Editor
        series_atom = SearchService.find_series_by_id_as_atom(self.current_series_id)

        if series_atom:
            # Die View füllt nun die Entry-Felder (Name, Padding etc.)
            self.view.display_series_details(series_atom)

            # 2. Die Bücher für den rechten Tab laden (Tab: "Zugeordnete Bücher")
            books = SearchService.find_books_by_series_id(self.current_series_id)
            self.view.update_book_list(books)

            # 3. Den Dubletten-Check für den zweiten Tab rechts triggern
            # Wir suchen im ganzen System nach Serien mit gleichem Namen
            clones = SearchService.find_series_clones_by_name(series_atom.name, self.current_series_id)
            self.view.update_clone_list(clones)


    def save_series_changes(self, new_data):
        """
        Wird aufgerufen, wenn du im Editor auf 'Speichern' klickst.
        new_data enthält z.B. {'name': 'Perry Rhodan (Silberbände)', 'padding': '3'}
        """
        if not self.current_series_id:
            return

        # 1. Alle Bücher dieser Serie aus der DB holen
        # Wir brauchen die aktuellen Pfade, um sie physisch umzubenennen
        books_data = SearchService.find_books_by_series_id(self.current_series_id)

        print(f"[BRIDGE] Starte physisches Update für {len(books_data)} Dateien...")

        for book in books_data:
            # Wir bauen ein temporäres Package für Scotty
            # Scotty braucht: authors (als Liste), title, series_name, series_index, ext

            # Wichtig: Da Scotty im Scan JSON nutzt, müssen wir hier ggf. decodieren
            # oder die Atome nutzen.

            # 2. Scotty den Befehl zum Umbenennen geben
            # Scotty.smart_save erkennt, dass der Name nicht mehr zum 'Perfect Name'
            # passt (da der Serienname sich geändert hat) und benennt die Datei um.
            new_path = Scotty.smart_save(
                old_path=book['path'],
                new_metadata={
                    'series_name': new_data['name'],
                    'series_index': book['series_index'],
                    # Die anderen Daten bleiben gleich
                    'authors': self.current_series_authors,
                    'title': book['title'],
                    'ext': book['extension']
                }
            )

            # 3. Datenbank-Update für den Pfad
            if new_path != book['path']:
                SearchService.update_book_path(book['id'], new_path)

        # 4. Am Ende den Seriennamen selbst in der Datenbank ändern
        SearchService.update_series_name(self.current_series_id, new_data['name'])

        # UI aktualisieren
        self.load_initial_data()