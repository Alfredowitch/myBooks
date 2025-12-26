import sqlite3

def save_book_with_authors(book, authors):
    """ Funktion zum Einfügen eines eBuches und seiner Autoren
        Die Datenbank besteht aus drei relevanten Tabellen:
        books ----  book_authors  ----- authors

        Diese Struktur erlaubt, dass ein Buch von mehreren Autoren geschrieben wird.
        Natürlich kan ein Autor auch mehrere Bücher geschrieben haben.
    """
    title = book.get('title','default')
    file_url = book.get('path',"")
    cover_image_url = book.get('cover_image_url',"")

    # 0. Verbindung zur bestehenden SQLite-Datenbank herstellen
    db_path = 'D://Bücher//books_metadata.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Buch einfügen - falls nicht schon vorhanden
    cursor.execute("SELECT id FROM books WHERE title = ?", (title,))
    res = cursor.fetchone()
    print(res)

    if not res:
        columns = []
        values = []
        params = []

        for key, value in book.items():
            if value is not None:
                columns.append(key)
                values.append("?")
                params.append(value)

        sql = f'''
        INSERT INTO books ({", ".join(columns)})
        VALUES ({", ".join(values)})
        '''
        cursor.execute(sql, params)
        book_id = cursor.lastrowid
        print("book inserted")
    else:
        book_id = res[0]

    # 2. Autoren in Vor- und Nachnamen zerlegen, suchen bwz. einfügen
    # Autoren sind Listen aus Tuplen von Vor- und Nachnamen: authors = [("Johann Wolfgang von", "Goethe"),("E.T.A.", "Hoffmann")]
    for author in authors:
        firstname, lastname = author  # Entpacken des Autor-Tupel
        cursor.execute('''
            SELECT id FROM authors WHERE firstname = ? AND lastname = ? 
            ''',(firstname, lastname))
        res = cursor.fetchone()
        if not res:
            cursor.execute('''
            INSERT INTO authors (firstname, lastname)
            VALUES (?, ?)
            ''', (firstname, lastname))
            author_id = cursor.lastrowid
            print("author inserted")
        else:
            author_id = res[0]

        # 3. Für jeden Autor müssen Autor und Buch in der Verknüpfungstabelle angelegt werden
        #     Falls nicht schon vorhanden!
        cursor.execute('''
            SELECT * FROM book_authors WHERE book_id = ? AND author_id = ? 
            ''',(book_id, author_id))
        res = cursor.fetchone()
        if not res:
            cursor.execute('''
            INSERT INTO book_authors (book_id, author_id)
            VALUES (?, ?)
            ''',(book_id, author_id))
            print("link table updated")

    # 4. Verbindung schließen
    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Beispielaufruf
    book = {
        'title': 'Un vero motivo (A1)',
        'language': 'IT'
        #'description': 'Eine spannende Geschichte',
        #'url': 'http://example.com',
        #'official_rating': 4.5,
        #'rating': 4.2,
        #'genre': 'Thriller',
        #'new_attribute': 'Zusätzliche Info'  # Ein neu hinzugefügtes Attribut
    }
    authors = [('Alessandra Felici','Puccetti')]

    save_book_with_authors(book,authors)

