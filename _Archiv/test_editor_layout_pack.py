import tkinter as tk
from tkinter import ttk


def edit_book(b):
    initial_description = b.get('description', '...')
    amazon_rating = b.get('official rating', '')
    title = f"{b.get('firstname', '')} {b.get('lastname', '')}: {b.get('title', '-')} "
    print(title)
    print(initial_description)
    print(amazon_rating)

    win = tk.Tk()
    win.title(title)

    # Frame für die Textarea
    frame_text = tk.Frame(win)
    frame_text.pack(padx=10, pady=10, fill=tk.X)  # füllt den gesamten horizontalen Platz

    # Textfeld für die Beschreibung
    header = tk.Label(frame_text, text="Beschreibung:")
    header.pack(anchor="w")
    inhalt = tk.Text(frame_text, wrap='word', width=120, height=30)
    inhalt.insert(tk.END, initial_description)
    inhalt.pack(padx=10, pady=5)
    """
    inhalt.insert(tk.END, db_description)  # Erst die gespeicherte Beschreibung aus der Datenbank
    inhalt.insert(tk.END, "\n\n")  # Eine Leerzeile für bessere Lesbarkeit
    inhalt.insert(tk.END, scraped_description)  # Dann die neu gefundene Amazon-Beschreibung
    insert("1.0", ...) → Text kommt an den Anfang.
    """

    # Amazon-Bewertung und Sprache
    # Der Frame ist wie eine weitere Zeile unterhalb des Textfensters.
    frame_1stline = tk.Frame(win)
    frame_1stline.pack(padx=10, pady=5, fill=tk.X)

    amazon_rating_label = tk.Label(frame_1stline, text="Amazon-Bewertung:")
    amazon_rating_label.pack(side="left", padx=5)
    amazon_rating_text = tk.Entry(frame_1stline, width=10)
    amazon_rating_text.insert(0, amazon_rating)
    amazon_rating_text.pack(side="left", padx=5)

    # Sprache Dropdown
    selected_language = tk.StringVar(value=b.get('language', ''))
    languages = ['Deutsch', 'Englisch', 'Französisch', 'Spanisch']  # Beispielsprachen
    language_menu = ttk.Combobox(frame_1stline, textvariable=selected_language, values=languages, width=20)
    language_menu.pack(side="right", padx=5)
    language_label = tk.Label(frame_1stline, text="Sprache:")
    language_label.pack(side="right", padx=10)

    # Eigene Bewertung und Genre.
    # Jetzt setzen wir einen weiteren Frame, d.h. eine weitere Zeile
    frame_2ndline = tk.Frame(win)
    frame_2ndline.pack(padx=10, pady=5, fill=tk.X)
    """
    padx=10: Fügt links und rechts einen Abstand von 10 Pixeln zum umgebenden Widget hinzu.
    pady=5: Fügt oben und unten einen Abstand von 5 Pixeln hinzu.
    fill=tk.X: Sorgt dafür, dass frame_genre_rating die gesamte Breite des Eltern-Widgets (hier win) einnimmt.
    Ohne fill=tk.X würde das Frame nur so breit sein wie seine Inhalte.
    """

    # Eigene Bewertung
    own_rating_label = tk.Label(frame_2ndline, text="Eigene Bewertung:   ")
    own_rating_label.pack(side="left", padx=5)
    own_rating_entry = tk.Entry(frame_2ndline, width=10)
    own_rating_entry.insert(0, b.get('rating', ''))
    own_rating_entry.pack(side="left", padx=5)

    # Genre Dropdown
    selected_genre = tk.StringVar(value=b.get('genre', ''))
    genres = ['Krimi', 'Romantik', 'Fantasy', 'Science Fiction']  # Beispielgenres
    genre_menu = ttk.Combobox(frame_2ndline, textvariable=selected_genre, values=genres, width=20)
    genre_menu.pack(side="right", padx=5)
    genre_label = tk.Label(frame_2ndline, text="Genre:")
    genre_label.pack(side="right", padx=5)


    # Speichern-Button
    save_button = tk.Button(win, text="Speichern und Schließen", command=lambda: win.quit())
    save_button.pack(pady=10)

    win.mainloop()
    # Speichern der geänderten Daten zurück in das Buchobjekt
    b["description"] = inhalt.get("1.0", tk.END).strip()
    b["language"] = selected_language.get()
    b["genre"] = selected_genre.get()
    b["rating"] = own_rating_entry.get() or None
    return b

# Beispiel-Daten
book = {
    'firstname': 'John',
    'lastname': 'Doe',
    'title': 'Das Buch der Bücher',
    'description': 'Dies ist eine Buchbeschreibung.',
    'official rating': '4.5',
    'language': 'Deutsch',
    'genre': 'Krimi',
    'rating': '4.0'
}

edit_book(book)
