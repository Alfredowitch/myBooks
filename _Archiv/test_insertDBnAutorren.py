import sqlite3
from save_db_ebooks import insert_book_with_authors


# Beispiel-Buch mit mehreren Autoren
title = "Ein Beispielbuch"
file_url = "/path/to/book.epub"
cover_image_url = "/path/to/cover_image.jpg"

# Autorenliste mit mehreren Vornamen und Nachnamen
authors = [
    ("Johann Wolfgang von", "Goethe"),
    ("E.T.A.", "Hoffmann"),
    ("Vorname3", "Nachname3")
]

# Buch mit Autoren in die Datenbank einfügen
insert_book_with_authors(title, file_url, cover_image_url, authors)
print("Buch und Autoren erfolgreich eingefügt.")
