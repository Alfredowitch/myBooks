import os
import pandas as pd
from Enterprise.database import Database
from Engineering.search_service import SearchService
from Engineering.author_service import AuthorService
from tkinter import messagebox


class AuthorBridge:
    def __init__(self, view=None):
        self.view = view
        self.current_author_atom = None  # Speichert das aktive Autoren-Objekt
        self.full_df = pd.DataFrame()

    def set_view(self, view):
        self.view = view

    def get_author_df(self):
        """Lädt die Autoren-Übersicht für die linke Liste."""
        if self.full_df.empty:
            # Nutzt den SearchService für die Zusammenfassung (IDs, Namen, Zähler)
            self.full_df = SearchService.find_authors_summary_df()
        return self.full_df

    def search_authors(self, query):
        """Filtert die Liste basierend auf der Sucheingabe."""
        # Wir filtern direkt im geladenen DataFrame für bessere Performance
        df = self.get_author_df()
        if query:
            filtered = df[df['display_name'].str.contains(query, case=False, na=False)]
            self.view.load_authors(filtered)
        else:
            self.view.load_authors(df)

    def select_author(self, a_id):
        """Lädt einen spezifischen Autor und aktualisiert die UI-Mitte und Rechts."""
        try:
            # 1. Daten als 'Atom' (SimpleNamespace/Objekt) laden
            self.current_author_atom = SearchService.find_author_by_id_as_atom(int(a_id))

            if self.current_author_atom and self.view:
                # 2. View befüllen (Metadaten, Bild, Vita)
                self.view.display_author_master(self.current_author_atom)

                # 3. Sicherstellen, dass die Vita-Ansicht aktiv ist (nicht Merge)
                self.view.show_vita()
        except Exception as e:
            print(f"❌ Fehler beim Selektieren des Autors {a_id}: {e}")

    def update_author_full(self, a_id, data):
        """Speichert alle geänderten Stammdaten eines Autors."""
        try:
            # Hier rufen wir den AuthorService auf, der die DB-Updates macht
            # 'data' enthält: firstname, lastname, vita, aliases, urls...
            success = AuthorService.update_author_record(a_id, data)

            if success:
                # Cache leeren, damit die Liste bei Bedarf neu geladen wird
                self.full_df = pd.DataFrame()
                messagebox.showinfo("Erfolg", "Autorendaten wurden gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {e}")

    def find_duplicates_for_current(self):
        """Sucht nach Namens-Dubletten für den aktuell gewählten Autor."""
        if not self.current_author_atom:
            messagebox.showwarning("Achtung", "Bitte wählen Sie erst einen Autor aus.")
            return

        master = self.current_author_atom
        # Nutzt die Logik aus dem Service (z.B. Normalisierung von Umlauten/Leerzeichen)
        target_key = AuthorService.generate_match_key(master.firstname, master.lastname)

        # Alle anderen Autoren laden (ID-Ausschluss des Masters)
        sql = "SELECT id, firstname, lastname FROM authors WHERE id != ?"
        others = Database.query_all(sql, [master.id])

        duplicates = []
        for row in others:
            key = AuthorService.generate_match_key(row['firstname'], row['lastname'])
            if key == target_key:
                # Werk-Anzahl ermitteln (für die Anzeige im Merge-Dialog wichtig)
                w_count_res = Database.query_one(
                    "SELECT COUNT(*) as c FROM work_to_author WHERE author_id=?", [row['id']]
                )
                duplicates.append({
                    'id': row['id'],
                    'name': f"{row['firstname']} {row['lastname']}",
                    'work_count': w_count_res['c'] if w_count_res else 0
                })

        if duplicates:
            self.view.show_merge_ui(duplicates)
        else:
            messagebox.showinfo("Dubletten-Check", "Keine weiteren Autoren mit diesem Namen gefunden.")

    def execute_merge(self, master_id, slave_id):
        """Führt die Zusammenführung zweier Autoren-Datensätze aus."""
        if AuthorService.interactive_authormerge(int(master_id), int(slave_id)):
            self.view.show_vita()  # UI zurück in Normalzustand
            self.full_df = pd.DataFrame()  # Cache ungültig machen
            self.view.load_authors()  # Linke Liste erneuern
            messagebox.showinfo("Merge", "Erfolgreich fusioniert.")

    def get_sample_path(self, author_id):
        """Holt einen Beispielpfad für das Kopieren/Anzeigen."""
        sql = """
            SELECT b.path FROM books b
            JOIN works w ON b.work_id = w.id
            JOIN work_to_author wta ON w.id = wta.work_id
            WHERE wta.author_id = ? LIMIT 1
        """
        res = Database.query_one(sql, [author_id])
        return os.path.normpath(res['path']) if res and res['path'] else "Kein Pfad gefunden."

    def get_authors_sorted_by_len(self):
        """Spezial-Sortierung für die Fehlersuche (z.B. sehr kurze Namen)."""
        df = self.get_author_df()
        if not df.empty:
            return df.assign(l=df['display_name'].str.len()).sort_values('l').drop('l', axis=1)
        return df

    def open_series_browser_for_author(self, a_id):
        """Schnittstelle zum Öffnen eines separaten Fensters (z.B. SeriesBrowser)."""
        print(f"🚀 Öffne Serien-Browser für Autor-ID: {a_id}")
        # Hier würde der Aufruf für den SeriesManager/View erfolgen

    def open_path_browser_for_author(self, a_id):
        """Holt alle Pfade für einen Autor und öffnet das Detail-Fenster."""
        sql = """
            SELECT DISTINCT b.path 
            FROM books b
            JOIN works w ON b.work_id = w.id
            JOIN work_to_author wta ON w.id = wta.work_id
            WHERE wta.author_id = ?
        """
        results = Database.query_all(sql, [a_id])
        paths = [os.path.normpath(r['path']) for r in results if r['path']]

        # Neues Fenster erstellen
        from D_Navigation.path_browser_view import PathBrowserView
        PathBrowserView(self.view.root, paths)