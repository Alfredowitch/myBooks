import sqlite3
db_path = 'M://audiobooks.db'

def get_languages():
    """Holt eine Liste aller vorhandenen Sprachen aus der Datenbank."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT language FROM audiobooks WHERE language IS NOT NULL AND language != '' ORDER BY language")
        return [row[0] for row in cur.fetchall()]  # Extrahiert nur die Strings

def get_genres():
    """Holt eine Liste aller vorhandenen Genres aus der Datenbank."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT genre FROM audiobooks WHERE genre IS NOT NULL AND genre != '' ORDER BY genre")
        return [row[0] for row in cur.fetchall()]  # Extrahiert nur die Strings

def get_audiobooks(limit=0,offset=0):
    """Liest TOP 12 Audiobooks aus der Datenbank und gibt sie als Liste zurück."""
    conn = sqlite3.connect(db_path) # Erstellt eine Verbindung zur SQLite-Datenbank
    conn.row_factory = sqlite3.Row  # Um das Dictionary-Verhalten zu aktivieren - sonst werden Tuple zurückgegeben

    # Ein Cursor ist ein Objekt, das verwendet wird, um SQL-Befehle in einer Datenbank auszuführen und Ergebnisse abzurufen.
    # Er ist keine direkte Instanz der Datenbank, sondern eine Art Steuermechanismus für Abfragen.
    cursor = conn.cursor() # Erstellt einen Cursor, um SQL-Befehle auszuführen

    # SQL-Abfrage, um die Audiobooks mit den Autorennamen zu verknüpfen
    if limit == 0:
        query = query = """
                            SELECT 
                                audiobooks.id,
                                audiobooks.title,
                                authors.firstname,
                                authors.lastname,
                                audiobooks.language,
                                audiobooks.description,   -- Neue Attribute
                                audiobooks.rating         -- Neue Attribute
                                audiobooks.official_rating
                            FROM
                                audiobooks
                            LEFT JOIN 
                                authors 
                            ON 
                                audiobooks.author_id = authors.id;
                        """
        cursor.execute(query)  # Führt die SQL-Abfrage aus
    elif offset == 0:
        query = f"""SELECT 
            *
            FROM audiobooks
            LEFT JOIN authors ON audiobooks.author_id = authors.id
            WHERE audiobooks.language = "Business"
            LIMIT {limit};
        """
        cursor.execute(query)  # Führt die SQL-Abfrage aus
    else:
        query = """ SELECT 
                        audiobooks.id, audiobooks.title, 
                        authors.firstname, authors.lastname, audiobooks.language, 
                        audiobooks.description, audiobooks.rating, audiobooks.official_rating  
                    FROM audiobooks
                    LEFT JOIN authors ON audiobooks.author_id = authors.id
                    LIMIT ? OFFSET ?;
                """
        cursor.execute(query,(limit, offset))  # Führt die SQL-Abfrage mit Parameter aus

    audiobooks = [dict(row) for row in cursor]
    #audiobooks = cursor.fetchall() # Holt alle Ergebnisse aus der Abfrage
    # audiobooks ist eine Liste von <class 'sqlite3.Row'>
    # audiobooks = [dict(row) for row in cursor.fetchall()]
    # würde zwar das gleiche Ergebnis liefern, aber zunächst würde Pythen erst alles in cursor.fetchall speichern.
    conn.close() # Schließt die Datenbankverbindung

    return audiobooks


if __name__ == "__main__":
    books = get_audiobooks(5,0)
    print(type(books))
    print(type(books[0]))
    #print(books)

    for book in books:
        #b = dict(book) nicht mehr nötig!
        #print(book['id'])
        print(f"ID:{book['id']}, Titel: {book['title']}, Autor: {book['firstname'] + " " + book['lastname']}, Language: {book['language']}")

    # ohne conn.row_factory = sqlite3.Row werden die Ergenisse als Liste von Tuples zurückgegeben
    # dann hätte man die books anders auslesen müssen:
    # print(f"Titel: {book[1]}, Autor: {book[2] + " " + book[3]}, Language: {book[4]}")


    """
    Titel: Aperitivo Mortale, Autor: Alessandra Felici Puccetti, Language: IT
    Titel: Compagni di viaggio, Autor: Alessandra Felici Puccetti, Language: IT
    Titel: Sinfonia Siciliana, Autor: Alessandra Felici Puccetti, Language: IT

    Titel: Blausäure, Autor: Agatha Christie, Language: De
    Titel: Da waren es nur noch neun, Autor: Agatha Christie, Language: De
    Titel: 1920-Das Fehlende Glied In Der Kette, Autor: Agatha Christie, Language: De
    Titel: 1923-Der Mord auf dem Golfplatz, Autor: Agatha Christie, Language: De
    Titel: Hercule Poirot - Das Haus an der Düne, Autor: Agatha Christie, Language: De
    Titel: Akif Pirincci - Felidae 1, Autor: Akif Pirincci, Language: De
    Titel: Lacroix 01 - und die Toten vom Pont Neuf, Autor: Alex Lépic, Language: De
    Titel: Jan Tommen 04-Die Erinnerung so kalt, Autor: Alexander Hartung, Language: De
    Titel: 03-Winteraustern (Luc Verlain), Autor: Alexander Oetker, Language: De
    Titel: Monalbano06-Der Kavalier der späten Stunde, Autor: Andrea Camilleri, Language: De
    Titel: Code Genesis02-Sie werden dich jagen (2020), Autor: Andreas Gruber, Language: De

    Titel: Die Inselkommissarin 03-Die alte Dame am Meer, Autor: Anna Johannsen, Language: De
    Titel: Antonio Manzini - Rocco Schiavone 01 - Der Gefrierpunkt des Blutes, Autor: Antonio Manzini, Language: De
    Titel: Kommissar Erlendur07-Frostnacht, Autor: Arnaldur Indriðason, Language: De
    Titel: Arno Strobel -2020- Die APP, Autor: Arno Strobel, Language: De

    Titel: Flg. 10 - Die perfekte Welle, Autor: Unbekannt, Language: De
    Titel: Peter Grant 01 - Die Flüsse von London, Autor: Ben Aaronovitch, Language: De
    Titel: C. J. Lyons - Caitlyn Tierney 2 - Schweig still, mein totes Herz, Autor: C J Lyons, Language: De
    Titel: Bücher1-Der Schatten des Windes (2001), Autor: Carlos Ruiz Zafón, Language: De
    Titel: 02-Spanischer Totentanz, Autor: Catalina Ferrera, Language: De

    """