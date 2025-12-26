import tkinter as tk
from tkinter import ttk
from get_db_audiobooks import get_languages, get_genres  # Angenommen, die Getter sind hier definiert

def edit_book(b):
    # Erstelle das Fenster
    win = tk.Tk()
    win.title(f"{b.get('firstname', '')} {b.get('lastname', '')}: {b.get('title', '-')}")

    # Holt die Sprachen und Genres aus der Datenbank
    languages = get_languages()
    genres = get_genres()

    # Textfeld für die Beschreibung
    initial_description = b.get('description', '...')
    header = tk.Label(win, text="Beschreibung:")
    header.grid(row=0, column=0, columnspan=5, padx=5, pady=5, sticky="w")
    inhalt = tk.Text(win, wrap='word', width=80, height=15)
    inhalt.insert(tk.END, initial_description)
    inhalt.grid(row=1, column=0, columnspan=5, padx=10, pady=10)  # Textfeld spannt über alle 5 Spalten

    # Zeile 2: Amazon Rating (als Entry-Feld) und Sprache
    amazon_rating_label = tk.Label(win, text="Amazon-Bewertung:")
    amazon_rating_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
    """
    sticky kann eine Kombination aus folgenden Himmelsrichtungen sein:
    "n" (North) → Oben ausrichten, "s" (South) → Unten ausrichten, "e" (East) → Rechts ausrichten, "w" (West) → Links ausrichten
    "nw" → Oben links
    sticky="w"	Label Text linksbündig
    """
    amazon_rating_value = tk.Entry(win, width=10, justify="center")  # Noch nicht readonly setzen!
    amazon_rating = b.get('official rating', 'Nicht bewertet')
    amazon_rating_value.insert(0, amazon_rating)  # Wert eintragen
    amazon_rating_value = tk.Entry(win, width=10, state="readonly", justify="center")  # Jetzt als Entry-Feld
    amazon_rating_value.grid(row=2, column=1, padx=5, pady=5)

    # Breite Spalte für Abstand (einmal setzen, für beide Zeilen)
    #tk.Label(win, text="", width=20).grid(row=2, column=2, rowspan=2)  # Platzhalter für beide Zeilen
    tk.Label(win, text="", width=20).grid(row=2, column=2)  # Platzhalter für beide Zeilen
    tk.Label(win, text="", width=20).grid(row=3, column=2)  # Platzhalter für beide Zeilen

    language_label = tk.Label(win, text="Sprache:")
    language_label.grid(row=2, column=3, padx=5, pady=5, sticky="w")
    selected_language = tk.StringVar(win, value=b.get('language', languages[0] if languages else ""))
    # Die StringVar ist direkt mit dem Combobox-Widget verknüpft. Sie wird auch ausgelesen!
    language_menu = ttk.Combobox(win, textvariable=selected_language, values=languages, width=20)  # Breiter machen
    language_menu.grid(row=2, column=4, padx=5, pady=5)

    # Zeile 3: Eigene Bewertung, Genre
    own_rating_label = tk.Label(win, text="Eigene Bewertung:")
    own_rating_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
    selected_rating = tk.StringVar(win, value=b.get('rating', ""))
    # Die StringVar ist direkt mit dem Combobox-Widget verknüpft. Sie wird auch ausgelesen!
    own_rating_entry = tk.Entry(win, textvariable=selected_rating, width=10)  # Schmäler machen
    own_rating_entry.grid(row=3, column=1, padx=5, pady=5)

    genre_label = tk.Label(win, text="Genre:")
    genre_label.grid(row=3, column=3, padx=5, pady=5, sticky="w")
    selected_genre = tk.StringVar(win, value=b.get('genre', genres[0] if genres else ""))
    # Die StringVar ist direkt mit dem Combobox-Widget verknüpft. Sie wird auch ausgelesen!
    genre_menu = ttk.Combobox(win, textvariable=selected_genre, values=genres, width=20)  # Breiter machen
    genre_menu.grid(row=3, column=4, padx=5, pady=5)

    # Button zum Speichern und Schließen
    save_button = tk.Button(win, text="Speichern und Schließen", command=lambda: win.quit())
    save_button.grid(row=4, column=0, columnspan=5, pady=10)
    """
    win.quit() beendet nur die mainloop()-Schleife, aber das Fenster bleibt offen.
    Nach der mainloop()-Schleife kann das Programm noch weiterlaufen und Daten verarbeiten.
    Das bedeutet, dass du erst nach mainloop() die Eingaben auslesen und speichern kannst.
    """
    # Der Event-Loop
    win.mainloop()

    # Speichern der geänderten Daten zurück in das Buchobjekt
    b["description"] = inhalt.get("1.0", tk.END).strip()
    b["language"] = selected_language.get()
    b["genre"] = selected_genre.get()
    b["rating"] = selected_rating.get() or None
    return b

# Beispielbuchobjekt
book = {
    "firstname": "Max",
    "lastname": "Mustermann",
    "title": "Beispielbuch",
    "language": "Deutsch",
    "genre": "Science Fiction",
    "description": "Dies ist eine Beispielbeschreibung.",
    "rating": "5",
    "official rating": "4.2"  # Amazon-Bewertung
}

# Aufruf der Funktion
book = edit_book(book)
