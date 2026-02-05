import tkinter as tk
from tkinter import ttk  # Hier importierst du ttk
from PIL import Image, ImageTk
import io
from get_db_audiobooks import get_languages,get_genres

def edit_book(b):
    # Hier speichern wir die Benutzereingaben
    print(type(b))
    initial_description = b.get('description', '...') or '...'
    # Wenn der Key 'description' in b nicht vorhanden ist, gib '...' zurück
    # Wenn der Key vorhanden aber None ist, dann geht es in den or Zweig!
    amazon_rating = b.get('official rating', '')
    title = f"{b.get('firstname', '')} {b.get('lastname', '')}: {b.get('title', '-')} "
    print(title)
    print(initial_description)
    print(amazon_rating)
    result = {"description": initial_description, "rating": None}

    language = b.get('language', '...') or '...'
    genre = b.get('genre', '') or ''
    print(language)
    print(genre)
    # Vorhandene Werte aus der Datenbank abrufen
    languages = get_languages()  # Liste der bekannten Sprachen
    genres = get_genres()  # Liste der bekannten Genres
    #print(languages)
    #print(genres)
    # Standardwerte setzen, falls vorhanden
    #selected_language = tk.StringVar(value=b.get('language', ""))
    #selected_genre = tk.StringVar(value=b.get('genre', ""))

    # Erstelle das Fenster
    win = tk.Tk()
    win.title(title)

    # Frame für die Textarea
    frame_text = tk.Frame(win)
    frame_text.pack(padx=10, pady=10, fill=tk.X)  # füllt den gesamten horizontalen Platz

    # Textfeld für die Beschreibung
    header = tk.Label(frame_text, text="Beschreibung:")
    header.pack(anchor="w")
    cover_blob = b.get('cover_blob', None) or None
    if cover_blob:
        imgO = Image.open(io.BytesIO(cover_blob))
        img = imgO.resize((160, 160))
        photo = ImageTk.PhotoImage(img)

        # 👉 Neues Unter-Frame für Bild + Text nebeneinander
        content_frame = tk.Frame(frame_text)
        content_frame.pack(fill=tk.X)
        bild_label = tk.Label(content_frame, image = photo, anchor="nw")
        bild_label.image = photo
        bild_label.pack(side="left", padx=10)
        inhalt = tk.Text(content_frame, wrap='word', width=70, height=30)
        inhalt.insert(tk.END, initial_description)
        inhalt.pack(side="left", padx=10, pady=5)
    else:
        inhalt = tk.Text(frame_text, wrap='word', width=120, height=30)
        inhalt.insert(tk.END, initial_description)
        inhalt.pack(padx=10, pady=5)
    """
    inhalt.insert(tk.END, db_description)  # Erst die gespeicherte Beschreibung aus der Datenbank
    inhalt.insert(tk.END, "\n\n")  # Eine Leerzeile für bessere Lesbarkeit
    inhalt.insert(tk.END, scraped_description)  # Dann die neu gefundene Amazon-Beschreibung
    insert("1.0", ...) → Text kommt an den Anfang.
    
    # Alternative ohne Frame:
    # Textfeld für die Beschreibung
    header = tk.Label(win, text="Beschreibung:")
    header.pack(pady=(10, 0))
    inhalt = tk.Text(win, wrap='word', width=120, height=30)
    inhalt.insert(tk.END, initial_description)
    inhalt.pack(padx=10, pady=10)
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
    # Die StringVar ist direkt mit dem Combobox-Widget verknüpft. Sie wird auch ausgelesen!
    selected_rating = tk.StringVar(win, value=b.get('rating', "") or "0")
    own_rating_entry = tk.Entry(frame_2ndline, textvariable=selected_rating, width=10)  # Schmäler machen
    # own_rating_entry = tk.Entry(frame_2ndline, width=10)
    # own_rating_entry.insert(0, b.get('rating', ''))
    own_rating_entry.pack(side="left", padx=5)

    # Genre Dropdown
    # Wegen der Orientierung nach rechts, müssten Feld und Label in umgekehrter Reihenfolge definiert werden.
    selected_genre = tk.StringVar(value=b.get('genre', ''))
    genres = ['Krimi', 'Romantik', 'Fantasy', 'Science Fiction']  # Beispielgenres
    genre_menu = ttk.Combobox(frame_2ndline, textvariable=selected_genre, values=genres, width=20)
    genre_menu.pack(side="right", padx=5)
    genre_label = tk.Label(frame_2ndline, text="Genre:")
    genre_label.pack(side="right", padx=5)


    # Speichern-Button
    save_button = tk.Button(win, text="Speichern und Schließen", command=lambda: win.quit())
    save_button.pack(pady=10)
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
    # b["rating"] = own_rating_entry.get() or None
    win.destroy()

    return b

    # Alternative Schließen-Events
    # ENTER kann zum Schließen führen. Hier nicht sinnvoll, weil ich ENTER im Text benutzen will.
    # win.bind("<Return>", lambda event: on_close())

    # Schließen-Event X-Close des Fensters aus GUI abfangen und ruft on_close auf.
    # Dadurch wird der Set-Change eingeleitet - dies muss vor dem Start des Fensters passieren!
    # win.protocol("WM_DELETE_WINDOW", on_close)

    # Damit wird das Fenster und die Event-Loop gestartet.
    # Der primäre Event-Loop von Tkinter ist
    # win.mainloop()
    # d.h. dass das Fenster bleibt offen und alle Interaktionen werden abgefangen.
    # Damit würde auch die Set-Change Interaktion abgefangen, bzw. blockiert.

    # Wenn wir auf die Änderung warten wollen, müssen wir stattdessen die Loop mit:
    # win.wait_variable(done)
    # starten. Andere Events werden auch damit abgefangen, aber auf set-change wird reagiert.


if __name__ == "__main__":
    # Beispielaufruf
    book = {'title': 'Apps-Titel',
            'official rating': '4 von 5 Sternen',
            'firstname': 'Alfred',
            'language': 'IT',
            'genre': 'neu',
            'description': 'Dies ist eine lange Beschreibung des Hörbuchs mit allgemeinen Informationen.'}
    book = edit_book(book)
    print(f"Die bearbeitete Beschreibung lautet: {book.get('description')}")
    print(f"Deine Bewertung: {book.get('rating')}")
