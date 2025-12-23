
import logging
import os
import tkinter as tk
import pandas as pd
import sqlite3

from book_browser import BookBrowser

DB_PATH = r'M:/books.db'

# Logger konfigurieren
LOG_FILE = os.path.join(os.path.dirname(DB_PATH), 'analyzer.log')
logger = logging.getLogger('LibraryAnalyzer')
logger.setLevel(logging.DEBUG)
# File Handler (Überschreibt die Datei bei jedem Start: mode='w')
fh = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
fh.setLevel(logging.DEBUG)
# Console Handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# Formatierung
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

logger.info("Analyzer gestartet. Logfile: " + LOG_FILE)

class LibraryAnalyzer:
    def __init__(self, master, db_path):
        self.master = master
        self.db_path = db_path
        self.master.title("Library Analyzer - Statistik & Analyse")
        self.master.geometry("1100x700")

        # Style für fette Überschriften definieren
        style = tk.ttk.Style()
        # 'treestyle' ist nur ein Name, wir ändern das Heading-Element
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))


        # Layout
        self.left_panel = tk.Frame(self.master, width=250, padx=10, pady=10, bg="#f0f0f0")
        self.left_panel.pack(side="left", fill="y")

        self.right_panel = tk.Frame(self.master, padx=10, pady=10)
        self.right_panel.pack(side="right", fill="both", expand=True)

        self.create_widgets()
        # App reagiert auf Doppelklick auf den TreeView und started die CAllbak-Funktion
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Daten aus dem SQL-Laden!
        self.df = self.load_data()

        # Snapshot direkt beim Start anzeigen
        if not self.df.empty:
            self.show_snapshot()


    # ----------------------------------------------------------------------
    # GUI-ERSTELLUNG (UNVERÄNDERT)
    # ----------------------------------------------------------------------
    def create_widgets(self):
        tk.Label(self.left_panel, text="Bibliothek Analyse", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)

        tk.Button(self.left_panel, text="Snapshot (Übersicht)", width=25, command=self.show_snapshot,
                  bg="#d1e7dd").pack(pady=5)
        tk.Button(self.left_panel, text="Top 10 Autoren", width=25, command=self.show_top_authors).pack(pady=5)
        tk.Button(self.left_panel, text="Genre-Statistik", width=25, command=self.show_genre_stats).pack(pady=5)
        tk.Button(self.left_panel, text="Alle gelesenen Bücher", width=25, command=self.show_read_books).pack(pady=5)

        tk.Label(self.left_panel, text="System", font=("Arial", 10, "italic"), bg="#f0f0f0").pack(pady=(20, 5))
        tk.Button(self.left_panel, text="Beenden", width=25, command=self.master.quit).pack(pady=5)

        tree_frame = tk.Frame(self.right_panel)
        tree_frame.pack(fill="both", expand=True)

        self.tree = tk.ttk.Treeview(tree_frame)
        scrollbar_y = tk.ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        tk.Label(self.left_panel, text="Diagnose", font=("Arial", 10, "italic"), bg="#f0f0f0").pack(pady=(20, 5))
        tk.Button(self.left_panel, text="Logfile anzeigen", width=25, command=self.show_logfile, bg="#fff3cd").pack(
            pady=5)
        tk.Button(self.left_panel, text="Browser",
                  width=25, bg="#ffc107", command=self.open_in_browser).pack(pady=10)

        tk.Label(self.left_panel, text="Datenpflege", font=("Arial", 10, "italic"), bg="#f0f0f0").pack(pady=(20, 5))
        tk.Button(self.left_panel, text="Anzeige aus DB löschen",
                  width=25, bg="#f8d7da", fg="#721c24",  # Rötliche Warnfarbe
                  command=self.delete_selected_records).pack(pady=5)


    # ----------------------------------------------------------------------
    # BÜCHER AUS DER DB IN DATENFRAME LADEN
    # ----------------------------------------------------------------------
    def load_data(self):
        logger.info("Starte Ladevorgang aus der Datenbank...")
        try:
            conn = sqlite3.connect(self.db_path)
            # SQL mit JOIN wie besprochen
            query = """
                    SELECT b.*, a.firstname, a.lastname
                    FROM books b
                             LEFT JOIN book_authors ba ON b.id = ba.book_id
                             LEFT JOIN authors a ON ba.author_id = a.id \
                    """
            df = pd.read_sql_query(query, conn)
            conn.close()

            # Namen aufbereiten
            df['full_author'] = (df['firstname'].fillna('') + ' ' + df['lastname'].fillna('Unbekannt')).str.strip()

            logger.info(f"Daten erfolgreich geladen. Zeilen im DataFrame: {len(df)}")
            logger.debug(f"Verfügbare Spalten: {df.columns.tolist()}")

            # Hier loggen wir stichprobenartig Alexander Oetker, um zu sehen was passiert
            oetker_check = df[df['full_author'].str.contains('Oetker', case=False, na=False)]
            logger.debug(f"Oetker Check: {len(oetker_check)} Einträge gefunden.")

            return df
        except Exception as e:
            logger.error(f"Kritischer Fehler beim Laden der DB: {e}", exc_info=True)
            return pd.DataFrame()

    # ----------------------------------------------------------------------
    # HILFS-FUNKTIONEN
    # ----------------------------------------------------------------------
    def _get_author_col(self):
        """Gibt den Namen der Autoren-Spalte zurück, mit Fallback-Sicherheit."""
        # 1. Unser Standardname
        if 'full_author' in self.df.columns:
            return 'full_author'

        # 2. Falls wir mal eine andere Liste (z.B. Rohdaten) anzeigen
        for col in ['author', 'authors', 'authors_raw']:
            if col in self.df.columns:
                return col

        # 3. Letzter Ausweg: Die erste Spalte nehmen (verhindert Absturz)
        return self.df.columns[0] if not self.df.empty else None

    def on_tree_double_click(self, event):
        """Wechselt von der Statistik zur Einzelansicht der Bücher dieses Autors."""
        selected_item = self.tree.selection()
        if not selected_item:
            return

        values = self.tree.item(selected_item)['values']
        columns = list(self.tree["columns"])

        # Wenn wir in der Statistik sind, heißt die Spalte oft 'Autor'
        author_col = None
        for col in ['autor', 'author', 'full_author']:
            if col in columns:
                author_col = columns.index(col)
                break

        if author_col is not None:
            author_name = values[author_col]
            # Jetzt filtern wir das gesamte DataFrame nach diesem Namen
            # Und zeigen die Einzel-Buch-Liste an (mit IDs!)
            subset = self.df[self.df['full_author'] == author_name]

            # Wichtig: Wir nehmen die ID mit in die Anzeige
            display_cols = ['id', 'title', 'full_author', 'series_name', 'path']
            available = [c for c in display_cols if c in subset.columns]

            self.display_in_tree(subset[available])
            logger.info(f"Drill-down für Autor: {author_name}")

    def get_selected_ids(self):
        selected_items = self.tree.selection()
        if not selected_items:
            # Wenn nichts markiert ist: Alle IDs zurückgeben
            return self.df['id'].tolist()

        columns = list(self.tree["columns"])
        item_id = selected_items[0]
        values = self.tree.item(item_id)['values']

        mask = None
        # Die bekannte Logik
        if 'id' in columns:
            idx = columns.index('id')
            mask = (self.df['id'] == int(values[idx]))
        elif 'Autor' in columns:
            idx = columns.index('Autor')
            mask = (self.df['full_author'] == values[idx])
        elif 'Genre' in columns:
            idx = columns.index('Genre')
            mask = (self.df['genre'] == values[idx])

        if mask is not None:
            return self.df[mask]['id'].tolist()
        return []

    # ----------------------------------------------------------------------
    # Anzeige-FUNKTIONEN
    # ----------------------------------------------------------------------

    def show_snapshot(self):
        """Erzeugt eine kurze Zusammenfassung der Datenbank."""
        if self.df.empty: return

        total_books = len(self.df)
        author_col = self._get_author_col()
        total_authors = self.df[author_col].nunique()

        # Wir erstellen ein kleines DataFrame für die Anzeige
        snapshot_data = pd.DataFrame({
            'Kategorie': ['Bücher Gesamt', 'Autoren Gesamt', 'Gelesene Bücher', 'Ungelesen'],
            'Wert': [
                total_books,
                total_authors,
                self.df[self.df['is_read'] == 1].shape[0] if 'is_read' in self.df.columns else "N/A",
                self.df[self.df['is_read'] != 1].shape[0] if 'is_read' in self.df.columns else "N/A"
            ]
        })
        self.display_in_tree(snapshot_data)

    def show_top_authors(self):
        if self.df.empty:
            return

        # Wir gruppieren nach dem Namen und zählen die Buch-IDs
        # Damit verhindern wir, dass IDs angezeigt werden.
        top_stats = self.df.groupby('full_author')['id'].count().reset_index()

        # Spalten benennen
        top_stats.columns = ['Autor', 'Anzahl Bücher']

        # Sortieren: Höchste Anzahl zuerst, dann alphabetisch
        top_stats = top_stats.sort_values(by=['Anzahl Bücher', 'Autor'], ascending=[False, True])

        # Die besten 10 nehmen
        top_10 = top_stats.head(10)

        self.display_in_tree(top_10)

    def show_genre_stats(self):
        if 'genre' in self.df.columns:
            stats = self.df['genre'].value_counts().reset_index()
            stats.columns = ['Genre', 'Menge']
            self.display_in_tree(stats)

    def show_read_books(self):
        if 'is_read' in self.df.columns:
            # Filtern nach gelesenen Büchern
            read_df = self.df[self.df['is_read'] == 1].copy()

            # Nur die Spalten auswählen, die wir sehen wollen
            display_cols = ['id','title', 'full_author', 'series_name', 'series_number']
            # Sicherstellen, dass sie existieren (falls Spalten in der DB fehlen)
            existing_cols = [c for c in display_cols if c in read_df.columns]

            self.display_in_tree(read_df[existing_cols])

    def display_in_tree(self, dataframe):
        """Zeigt Daten an und sorgt dafür, dass die ID-Spalte für Löschvorgänge bereitsteht."""
        self.tree.delete(*self.tree.get_children())

        columns = list(dataframe.columns)
        self.tree["columns"] = columns
        self.tree["show"] = "headings"

        for col in columns:
            self.tree.heading(col, text=col, anchor="w")

            # Spezialbehandlung für die ID-Spalte
            if col.lower() == 'id':
                self.tree.column(col, width=50, anchor="center")  # Schön schmal
            else:
                self.tree.column(col, width=250, anchor="w")

        for _, row in dataframe.iterrows():
            self.tree.insert("", "end", values=[str(v) for v in list(row)])

        logger.info(f"Tabelle aktualisiert. Spalten: {columns}")

    def show_books_without_author(self):
        # Filtert auf Einträge, wo der Nachname 'Unbekannt' oder leer ist
        # Je nachdem, wie dein load_data die Felder füllt
        mask = (self.df['full_author'].str.contains('Unbekannt', na=True)) | (self.df['full_author'] == "")
        bad_books = self.df[mask]
        self.display_in_tree(bad_books)
        logger.info(f"Filter aktiv: {len(bad_books)} Bücher ohne Autor gefunden.")

    def show_logfile(self):
        """Öffnet ein Fenster und zeigt den aktuellen Inhalt des Logfiles."""
        log_window = tk.Toplevel(self.master)
        log_window.title("System Logfile")
        log_window.geometry("800x500")

        text_area = tk.Text(log_window, wrap='none', bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        text_area.pack(fill="both", expand=True)

        # Scrollbars für das Log
        sy = tk.Scrollbar(text_area, command=text_area.yview)
        sy.pack(side="right", fill="y")
        sx = tk.Scrollbar(text_area, orient="horizontal", command=text_area.xview)
        sx.pack(side="bottom", fill="x")
        text_area.config(yscrollcommand=sy.set, xscrollcommand=sx.set)

        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                text_area.insert('1.0', content)
                text_area.config(state='disabled')  # Nur Lesen
                text_area.see(tk.END)  # Zum Ende scrollen
        except Exception as e:
            text_area.insert('1.0', f"Fehler beim Lesen des Logfiles: {e}")


    # ----------------------------------------------------------------------
    # FUNKTIONEN für den Aufruf des Browsers
    # ----------------------------------------------------------------------
    def open_in_browser(self):
        # 1. Wir holen die IDs der markierten Zeile (z.B. alle IDs eines Autors)
        selected_ids = self.get_selected_ids()

        if selected_ids:
            # Wir haben eine Auswahl -> Filtere Pfade basierend auf diesen IDs
            # self.df['id'].isin(selected_ids): Pandas geht die Spalte "id" durch und markiert jede Zeile mit True, deren ID in deiner Liste der ausgewählten IDs vorkommt.
            # self.df[...]: Das äußere Gehäuse nimmt nur diese "True"-Zeilen (das Filtern).
            # ['path']: Von diesen gefilterten Zeilen nehmen wir nur den Wert aus der Spalte "path"
            path_list = self.df[self.df['id'].isin(selected_ids)]['path'].tolist()
            logger.info(f"Browser mit Auswahl gestartet ({len(path_list)} Bücher).")
        else:
            # 2. KEINE Auswahl -> Wir nehmen einfach ALLES
            path_list = self.df['path'].tolist()
            logger.info(f"Nichts markiert. Browser mit allen {len(path_list)} Pfaden gestartet.")

        # 3. Übergabe an den Browser
        if path_list:
            browser_window = tk.Toplevel(self.master)
            BookBrowser(browser_window, initial_list=path_list)


    # ----------------------------------------------------------------------
    # FUNKTIONEN für die Datenbankpflege
    # ----------------------------------------------------------------------
    def delete_selected_records(self):
        del_ids = self.get_selected_ids()

        if not del_ids:
            return

        # Ab hier dein SQL-Batch-Delete (wie oben besprochen)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                id_params = [(i,) for i in del_ids]

                # Erst Links, dann Bücher
                cursor.executemany("DELETE FROM book_authors WHERE book_id = ?", id_params)
                cursor.executemany("DELETE FROM books WHERE id = ?", id_params)
                conn.commit()

            # Speicher bereinigen & UI Refresh
            self.df = self.df[~self.df['id'].isin(del_ids)]
            self.show_snapshot()
            logger.info(f"{len(del_ids)} Bücher gelöscht.")

        except Exception as e:
            logger.error(f"Batch-Delete Fehler: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = LibraryAnalyzer(root, DB_PATH)
    root.mainloop()