import sqlite3

# Verbindung zur bestehenden SQLite-Datenbank herstellen
db_path = 'D://Bücher//books_metadata.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# SQL-Abfrage, um alle Bücher aus der Tabelle zu holen
cursor.execute('SELECT * FROM books')

# Alle Ergebnisse abrufen
books = cursor.fetchall()

# Ergebnisse anzeigen
n = 0
for book in books:
    #print(book)
    n += 1

print(f"Es gibt {n} Bücher in der Datenbank.")
# Verbindung schließen
conn.close()
