import sqlite3

# Verbindung zur bestehenden SQLite-Datenbank herstellen
db_path = 'D://Bücher//books_metadata.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Beispiel-Daten zum Einfügen
author_firstname = "Jean-Luc"
author_lastname = "Bannalec"
series_number = "1"
title = "Bretonische Verhältnisse"
file_url = "/path/to/ebook.epub"
cover_image_url = "/path/to/cover_image.jpg"

# SQL-Befehl zum Einfügen der Daten
cursor.execute('''
INSERT INTO books (author_firstname, author_lastname, series_number, title, file_url, cover_image_url)
VALUES (?, ?, ?, ?, ?, ?)
''', (author_firstname, author_lastname, series_number, title, file_url, cover_image_url))

# Änderungen speichern
conn.commit()

# Verbindung schließen
conn.close()

print("Daten erfolgreich eingefügt.")
