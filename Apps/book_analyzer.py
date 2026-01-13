"""
DATEI: book_analyzer.py
PROJEKT: MyBook-Management (v1.3.0)
BESCHREIBUNG: Analysiert die Daten in der Datenbank.
              Zentrales Refresh-System für additive Filter und Code-Anzeige.
"""
import logging
import os
import platform
import tkinter as tk
from tkinter import messagebox, ttk
import pandas as pd
import sqlite3

from Apps.book_browser import BookBrowser
from Gemini.file_utils import DB_PATH, sanitize_path

# Logger Setup (Nutzt den Ordner der DB)
LOG_FILE = os.path.join(os.path.dirname(DB_PATH), 'analyzer.log')
logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LibraryAnalyzer')

class LibraryAnalyzer:
    def __init__(self, master):
        self.master = master
        self.db_path = DB_PATH
        self.master.title("Library Analyzer - Statistik & Analyse")
        self.master.geometry("1200x850")

        # Zustands-Speicher (Das "Gedächtnis" für die Filter)
        self.current_view = "snapshot"
        self.current_lang = "Alles"
        self.browser_instance = None
        self.df = self.load_data()

        # UI Layout
        self.left_panel = tk.Frame(self.master, width=250, padx=10, pady=10, bg="#f0f0f0")
        self.left_panel.pack(side="left", fill="y")
        self.right_panel = tk.Frame(self.master, padx=10, pady=10)
        self.right_panel.pack(side="right", fill="both", expand=True)

        self.create_widgets()

        # Events
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Start-Anzeige
        if not self.df.empty:
            self.refresh_data()

    def load_data(self):
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                    SELECT b.*, a.firstname, a.lastname
                    FROM books b
                             LEFT JOIN book_authors ba ON b.id = ba.book_id
                             LEFT JOIN authors a ON ba.author_id = a.id
                    """
            df = pd.read_sql_query(query, conn)
            conn.close()
            df['full_author'] = (df['firstname'].fillna('') + ' ' + df['lastname'].fillna('Unbekannt')).str.strip()
            # Pfade normalisieren (wichtig für Mismatch-Suche)
            df['path'] = df['path'].apply(lambda x: sanitize_path(x) if x else "")
            return df

        except Exception as e:
            logger.error(f"Fehler beim Laden: {e}")
            return pd.DataFrame()

    def create_widgets(self):
        # --- TOP BAR (PANDAS CODE) ---
        self.top_bar = tk.Frame(self.right_panel, bg="#333", padx=5, pady=5)
        self.top_bar.pack(side="top", fill="x")
        tk.Label(self.top_bar, text="Pandas Code:", fg="#00ff00", bg="#333", font=("Consolas", 10, "bold")).pack(side="left")
        self.code_label = tk.Label(self.top_bar, text="df", fg="white", bg="#333", font=("Consolas", 10), wraplength=800, justify="left")
        self.code_label.pack(side="left", padx=10)

        # --- FILTER BAR ---
        filter_frame = tk.Frame(self.right_panel, pady=5)
        filter_frame.pack(side="top", fill="x")
        tk.Label(filter_frame, text="Globaler Sprachfilter:").pack(side="left", padx=5)
        self.lang_var = tk.StringVar(value="Alles")
        langs = ["Alles", "de", "en", "es", "it", "fr"]
        self.lang_dropdown = tk.OptionMenu(filter_frame, self.lang_var, *langs, command=self.apply_language_filter)
        self.lang_dropdown.pack(side="left", padx=5)

        # --- BUTTONS (LINKS) ---
        tk.Label(self.left_panel, text="Bibliothek Analyse", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)

        actions = [
            ("Snapshot", self.show_snapshot, "#d1e7dd"),
            ("Top 30 Autoren", self.show_top_authors, None),
            ("Bottom 30 Autoren", self.show_bottom_authors, None),
            ("Genre-Statistik", self.show_genre_stats, None),
            ("Regionen-Statistik", self.show_region_stats, None),
            ("Serien-Statistik", self.show_top_series, None)
        ]
        for text, cmd, color in actions:
            tk.Button(self.left_panel, text=text, width=25, command=cmd, bg=color).pack(pady=2)

        tk.Label(self.left_panel, text="Health-Report", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=(15, 5))
        tk.Button(self.left_panel, text="Doppelte Titel", width=25, bg="#ffcc00", command=self.show_double_titles).pack(pady=2)
        tk.Button(self.left_panel, text="Ähnliche Autoren (Punkt)", width=25, bg="#ffcc00", command=self.show_fuzzy_authors).pack(pady=2)

        tk.Button(self.left_panel, text="Verwaiste Autoren", width=25, bg="#f8d7da", command=self.show_orphaned_authors).pack(pady=2)
        tk.Button(self.left_panel, text="Ungültige Autorennamen", width=25, bg="#f8d7da", command=self.show_bad_author_names).pack(pady=2)
        tk.Button(self.left_panel, text="Bücher: Fehlende Daten", width=25, bg="#f8d7da", command=self.show_missing_book_data).pack(pady=2)

        tk.Label(self.left_panel, text="Tools", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=(15, 5))
        tk.Button(self.left_panel, text="Browser öffnen", width=25, bg="#ffc107", command=self.open_in_browser).pack(pady=2)
        tk.Button(self.left_panel, text="Aus DB löschen", width=25, bg="#f8d7da", fg="#721c24", command=self.delete_selected_records).pack(pady=2)

        tk.Button(self.left_panel, text="Beenden", width=25, command=self.master.quit, bg="#6c757d", fg="white").pack(side="bottom", pady=20)

        # --- TREEVIEW ---
        tree_frame = tk.Frame(self.right_panel)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame)
        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

    # ----------------------------------------------------------------------
    # ZENTRALE LOGIK (DER MOTOR)
    # ----------------------------------------------------------------------
    def refresh_data(self):
        if self.df.empty: return

        # 1. Schritt: Sprachfilter (Das Fundament)
        if self.current_lang == "Alles":
            df_work = self.df
            l_code = "df"
        else:
            df_work = self.df[self.df['language'] == self.current_lang]
            l_code = f"df[df['language'] == '{self.current_lang}']"

        # 2. Schritt: Ansicht (Die Analyse)
        final_code = ""
        result = pd.DataFrame()

        if self.current_view == "snapshot":
            res_data = {
                'Kategorie': ['Bücher', 'Autoren', 'Gelesen'],
                'Wert': [len(df_work), df_work['full_author'].nunique(),
                        len(df_work[df_work['is_read']==1]) if 'is_read' in df_work.columns else 0]
            }
            result = pd.DataFrame(res_data)
            final_code = f"{l_code}.agg({{'id':'count', 'full_author':'nunique'}})"
        elif self.current_view == "top_authors":
            result = df_work.groupby('full_author')['id'].count().reset_index()
            result.columns = ['Autor', 'Bücher']
            result = result.sort_values(by='Bücher', ascending=False).head(30)
            final_code = f"{l_code}.groupby('full_author')['id'].count().sort_values(ascending=False).head(30)"
        elif self.current_view == "bottom_authors":
            result = df_work.groupby('full_author')['id'].count().reset_index()
            result.columns = ['Autor', 'Bücher']
            result = result.sort_values(by='Bücher', ascending=False).tail(30)
            final_code = f"{l_code}.groupby('full_author')['id'].count().sort_values(ascending=False).head(30)"
        elif self.current_view == "genre":
            result = df_work['genre'].value_counts().reset_index()
            result.columns = ['Genre', 'Menge']
            final_code = f"{l_code}['genre'].value_counts()"
        elif self.current_view == "region":
            # NEU: Regionen-Statistik
            result = df_work[df_work['region'].notna()]['region'].value_counts().reset_index()
            result.columns = ['Region', 'Menge']
            final_code = f"{l_code}['region'].value_counts()"
        elif self.current_view == "double_titles":
            result = df_work[df_work.duplicated(subset=['title'], keep=False)]
            result = result.sort_values(by='title')[['id', 'title', 'full_author', 'language', 'path']]
            final_code = f"{l_code}[{l_code}.duplicated(subset=['title'], keep=False)]"

        elif self.current_view == "fuzzy_authors":
            # Trick: Wir entfernen Punkte temporär für den Vergleich
            df_work = df_work.copy()
            df_work['clean_name'] = df_work['full_author'].str.replace('.', '', regex=False)
            duplicates = df_work[df_work.duplicated(subset=['clean_name'], keep=False)]
            result = duplicates.sort_values(by='clean_name')[['id', 'full_author', 'title']]
            final_code = f"{l_code}[{l_code}['full_author'].str.replace('.','').duplicated(keep=False)]"
            # ... (nach fuzzy_authors in der if-elif Kette ergänzen)

        elif self.current_view == "orphaned_authors":
            # Autoren, die in der Autorenliste stehen, aber keinem Buch zugeordnet sind
            # Da dein 'df' über einen LEFT JOIN geladen wird, müssen wir hier
            # ggf. eine separate Abfrage machen oder die Liste abgleichen.
            # Einfacher Ansatz über SQL (da df nur verknüpfte Daten enthält):
            try:
                conn = sqlite3.connect(self.db_path)
                query = "SELECT id, firstname, lastname FROM authors WHERE id NOT IN (SELECT author_id FROM book_authors)"
                result = pd.read_sql_query(query, conn)
                conn.close()
                result['full_author'] = (
                            result['firstname'].fillna('') + ' ' + result['lastname'].fillna('')).str.strip()
                final_code = "SQL: SELECT * FROM authors WHERE id NOT IN (SELECT author_id FROM book_authors)"
            except:
                result = pd.DataFrame(columns=['id', 'full_author'])

        elif self.current_view == "bad_author_names":
            # Filter nach Platzhaltern wie " ", "Kein Autor", "Unknown"
            bad_patterns = ['', ' ', 'Kein Autor', 'Unknown', 'Unbekannt']
            result = df_work[df_work['full_author'].isin(bad_patterns)]
            result = result[['id', 'title', 'full_author', 'path']]
            final_code = f"{l_code}[{l_code}['full_author'].isin({bad_patterns})]"

        elif self.current_view == "missing_book_data":
            # Filter nach: Kein Pfad, kein Rating (0 oder NaN), keine Beschreibung (NaN oder leer)
            mask = (
                    (df_work['path'].isna()) | (df_work['path'] == '') |
                    (df_work['rating'].isna()) | (df_work['rating'] <= 0) |
                    (df_work['comments'].isna()) | (df_work['comments'] == '')
            )
            result = df_work[mask][['id', 'title', 'full_author', 'rating', 'path']]
            final_code = f"{l_code}[(df['path'].isna()) | (df['rating'] <= 0) | (df['comments'].isna())]"

        elif self.current_view == "top_series":
            # Wir nutzen SQL für die Top 30 Serien mit Nummern-Check
            try:
                conn = sqlite3.connect(self.db_path)
                # GROUP_CONCAT hilft uns, die vorhandenen Nummern direkt zu sehen
                query = """
                            SELECT series_name, COUNT(id) as Menge, 
                                   GROUP_CONCAT(DISTINCT series_number) as Bände, language
                            FROM books 
                            WHERE series_name IS NOT NULL AND series_name != ''
                        """
                if self.current_lang != "Alles":
                    query += f" AND language = '{self.current_lang}'"

                query += " GROUP BY series_name, language ORDER BY Menge DESC LIMIT 30"
                result = pd.read_sql_query(query, conn)
                conn.close()
                final_code = "SQL: GROUP BY series_name ORDER BY count DESC"
            except Exception as e:
                logger.error(f"Serien-Fehler: {e}")
                result = pd.DataFrame()

        # 3. Schritt: UI Update
        self.code_label.config(text=final_code)
        self.display_in_tree(result)

    # --- Button-Steuerung ---
    def apply_language_filter(self, selection):
        self.current_lang = selection
        self.refresh_data()

    def show_snapshot(self): self.current_view = "snapshot"; self.refresh_data()
    def show_top_authors(self): self.current_view = "top_authors"; self.refresh_data()
    def show_bottom_authors(self): self.current_view = "bottom_authors"; self.refresh_data()
    def show_genre_stats(self): self.current_view = "genre"; self.refresh_data()
    def show_region_stats(self): self.current_view = "region"; self.refresh_data() # (In refresh_data ergänzbar)
    def show_double_titles(self): self.current_view = "double_titles"; self.refresh_data()
    def show_fuzzy_authors(self): self.current_view = "fuzzy_authors"; self.refresh_data()

    def show_orphaned_authors(self): self.current_view = "orphaned_authors"; self.refresh_data()
    def show_bad_author_names(self): self.current_view = "bad_author_names"; self.refresh_data()
    def show_missing_book_data(self): self.current_view = "missing_book_data"; self.refresh_data()

    def show_top_series(self): self.current_view = "top_series"; self.refresh_data()

    # ----------------------------------------------------------------------
    # HILFSFUNKTIONEN (BLEIBEN FAST GLEICH)
    # ----------------------------------------------------------------------
    def display_in_tree(self, dataframe):
        self.tree.delete(*self.tree.get_children())
        cols = list(dataframe.columns)
        self.tree["columns"] = cols
        self.tree["show"] = "headings"
        for col in cols:
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=100 if col=='id' else 250)
        for _, row in dataframe.iterrows():
            self.tree.insert("", "end", values=[str(v) for v in list(row)])

    def get_selected_ids(self):
        items = self.tree.selection()
        if not items:
            print("Debug: Keine Zeile im Tree markiert.")
            return []
        cols = list(self.tree["columns"])
        if 'id' in cols:
            idx = cols.index('id')
            ids = [int(self.tree.item(i)['values'][idx]) for i in items]
            print(f"Debug: Rohwert aus Spalte 'id': {ids[0]} (Typ: {type(ids[0])})")
            return ids
        return []

    def get_all_visible_ids(self):
        # Holt alle IDs, die aktuell im Treeview angezeigt werden
        items = self.tree.get_children()
        """
        # Wir schauen uns die Spaltenüberschriften an (case-insensitive)
        cols = [c.lower() for c in list(self.tree["columns"])]

        if 'id' in cols:
            idx = cols.index('id')
            ids = []
            for i in items:
                values = self.tree.item(i)['values']
                if values:
                    try:
                        # Sicherstellen, dass wir einen Integer bekommen
                        val = float(values[idx])
                        ids.append(int(val))
                    except (ValueError, IndexError):
                        continue
            return ids

        print(f"Fehler: Spalte 'id' nicht gefunden. Vorhanden sind: {cols}")
        return []
        """
        cols = list(self.tree["columns"])
        if 'id' in cols:
            idx = cols.index('id')
            return [int(self.tree.item(i)['values'][idx]) for i in items]
        return []

    # ----------------------------------------------------------------------
    # TOOLS & BROWSER-INTEGRATION
    # ----------------------------------------------------------------------
    def open_in_browser(self):
        # 1. Auswahl im Treeview prüfen
        items = self.tree.selection()
        if not items:
            items = self.tree.get_children()  # Fallback: Alle sichtbaren

        if not items:
            messagebox.showwarning("Hinweis", "Keine Einträge zum Öffnen gefunden.")
            return

        cols = list(self.tree["columns"])
        path_list = []

        # --- LOGIK-WEICHE JE NACH ANSICHT ---
        # FALL A: Serien-Ansicht (Top 30 Serien)
        if 'series_name' in cols:
            idx_series = cols.index('series_name')
            idx_lang = cols.index('language') if 'language' in cols else None

            # Wir sammeln alle markierten Seriennamen (und Sprachen, falls vorhanden)
            for i in items:
                vals = self.tree.item(i)['values']
                s_name = vals[idx_series]
                s_lang = vals[idx_lang] if idx_lang is not None else None

                # Filter auf das Haupt-DF anwenden
                mask = (self.df['series_name'] == s_name)
                if s_lang and s_lang != "Alles":
                    mask &= (self.df['language'] == s_lang)

                # Pfade holen und nach Seriennummer sortieren, damit die Reihenfolge im Browser stimmt
                paths = self.df[mask].sort_values(by='series_number')['path'].tolist()
                path_list.extend([p for p in paths if p])

        # FALL B: IDs vorhanden (Snapshots, Doppelte Titel, etc.)
        elif 'id' in cols:
            idx_id = cols.index('id')
            ids = [int(self.tree.item(i)['values'][idx_id]) for i in items]
            path_list = self.df[self.df['id'].isin(ids)]['path'].tolist()

        # FALL C: Autoren (Top 30 Autoren)
        elif 'Autor' in cols or 'full_author' in cols:
            col_name = 'Autor' if 'Autor' in cols else 'full_author'
            idx_auth = cols.index(col_name)
            selected_authors = [self.tree.item(i)['values'][idx_auth] for i in items]

            mask = self.df['full_author'].isin(selected_authors)
            if self.current_lang != "Alles":
                mask &= (self.df['language'] == self.current_lang)

            path_list = self.df[mask]['path'].tolist()
        else:
            print("Keine IDs, Autoren oder Serien zur Identifikation gefunden.")
            return

        # --- BROWSER STARTEN / AKTUALISIEREN ---
        path_list = list(dict.fromkeys(path_list))  # Dubletten entfernen (erhält Reihenfolge)

        if path_list:
            if self.browser_instance is not None and hasattr(self.browser_instance,
                                                             'win') and self.browser_instance.win.winfo_exists():
                self.browser_instance.win.lift()
                if hasattr(self.browser_instance, 'load_new_list'):
                    self.browser_instance.load_new_list(path_list)
            else:
                top = tk.Toplevel(self.master)
                self.browser_instance = BookBrowser(top, initial_list=path_list)
                top.transient(self.master)
        else:
            messagebox.showwarning("Hinweis", "Keine gültigen Dateipfade für diese Auswahl gefunden.")

    def delete_selected_records(self):
        """Löscht Datensätze sicher aus der DB."""
        ids = self.get_selected_ids()

        if not ids:
            items = self.tree.selection()
            if not items: return
            cols = list(self.tree["columns"])
            if 'Autor' in cols:
                idx = cols.index('Autor')
                selected_authors = [self.tree.item(i)['values'][idx] for i in items]
                ids = self.df[self.df['full_author'].isin(selected_authors)]['id'].tolist()

        if not ids:
            logger.warning("Keine Datensätze zum Löschen identifiziert.")
            return

        if not messagebox.askyesno("Löschen", f"Sollen {len(ids)} Datensätze wirklich gelöscht werden?"):
            return

        try:
            # Verbindung manuell öffnen
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # SQLite mitteilen, dass wir Foreign Keys berücksichtigen (sicher ist sicher)
            cursor.execute("PRAGMA foreign_keys = ON;")
            # Wir bauen einen String für die SQL-Abfrage: (?, ?, ?)
            placeholders = ','.join(['?'] * len(ids))

            # 1. SCHRITT: Zuerst die Einträge in der Link-Tabelle löschen
            # (Die "Kinder" in der Buch-Autor-Verknüpfung)
            cursor.execute(f"DELETE FROM book_authors WHERE book_id IN ({placeholders})", ids)
            logger.debug(f"Links für IDs {ids} aus book_authors entfernt.")
            # 2. SCHRITT: Jetzt die eigentlichen Bücher löschen
            cursor.execute(f"DELETE FROM books WHERE id IN ({placeholders})", ids)
            logger.debug(f"Bücher mit IDs {ids} aus books entfernt.")
            # 3. SCHRITT: Die Änderungen festschreiben und Verbindung ZU
            conn.commit()
            conn.close()

            # 4. SCHRITT: Daten im Programm neu laden
            # Wir holen uns den Stand FRISCH von der Platte, nicht nur aus dem Speicher
            self.df = self.load_data()
            self.refresh_data()
            logger.info(f"Erfolgreich {len(ids)} Datensätze gelöscht.")
            messagebox.showinfo("Erfolg", f"{len(ids)} Datensätze wurden dauerhaft gelöscht.")

        except Exception as e:
            logger.error(f"Löschfehler: {e}")
            messagebox.showerror("Fehler", f"Löschfehler beim Zugriff auf die DB: {e}")

    def on_tree_double_click(self, event):
        item = self.tree.selection()
        if not item: return

        values = self.tree.item(item[0])['values']
        cols = list(self.tree["columns"])

        # Fall A: Wir haben eine ID (direkter Buch-Zugriff)
        if 'id' in cols:
            book_id = values[cols.index('id')]
            # Vielleicht willst du hier direkt den Browser öffnen?
            # Oder einfach das eine Buch im Tree isolieren:
            subset = self.df[self.df['id'] == book_id]

        # Fall B: Wir haben einen Autor (Drill-Down auf alle Bücher des Autors)
        elif 'Autor' in cols or 'full_author' in cols:
            col_name = 'Autor' if 'Autor' in cols else 'full_author'
            name = values[cols.index(col_name)]
            subset = self.df[self.df['full_author'] == name]

        # Fall C: Wir haben ein Genre (Drill-Down auf alle Bücher des Genres)
        elif 'Genre' in cols:
            genre_name = values[cols.index('Genre')]
            subset = self.df[self.df['genre'] == genre_name]
        else:
            return

        # Ergebnis anzeigen (wechselt meistens die Ansicht auf eine Buchliste)
        if not subset.empty:
            self.display_in_tree(subset[['id', 'title', 'full_author', 'language', 'path']])
            # Wir setzen den View-Status intern zurück, damit refresh_data weiß, wo wir sind
            self.current_view = "custom_drilldown"


    def get_top_series(self, lang=None):
        query = """
            SELECT series_name, COUNT(id), language
            FROM books
            WHERE series_name IS NOT NULL AND series_name != ''
        """
        params = []
        if lang:
            query += " AND language = ?"
            params.append(lang)

        query += " GROUP BY series_name, language ORDER BY COUNT(id) DESC LIMIT 30"
        return self.db.execute_query(query, params)


if __name__ == "__main__":
    root = tk.Tk()
    app = LibraryAnalyzer(root)
    root.mainloop()