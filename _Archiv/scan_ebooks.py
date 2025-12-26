import os
import re
import zipfile
from save_db_ebooks import save_book_with_authors


# Liste für problematische Dateien, falls der Autor nicht übereinstimmt
mismatch_list = []

# Funktion zum Extrahieren von Autoren und Titeln aus dem Dateinamen
def extract_metadata_from_filename(filename):
    # Entferne die Dateiendung
    filename_no_ext = os.path.splitext(filename)[0]

    # Regex-Muster für mehrere Autoren (getrennt durch "&")
    authors_and_title_pattern = r'(.+?) [-—] (.+)'

    # Suche nach dem Muster
    match = re.match(authors_and_title_pattern, filename_no_ext)

    if not match:
        #print("ACHTUNG: ")
        print(filename_no_ext)
        m = re.search("-", filename_no_ext)
        if m:
            parts = filename_no_ext.split(', ')
            print(parts, len(parts))
            if len(parts) == 1:
                title = parts[0].strip()
                authors_str = "no Author"
            else:
                authors_str = parts[0].strip()
                title = parts[1].strip()
        else:
            return None, None
    else:
        # Extrahiere den Autorenteil und den Titelteil
        authors_str = match.group(1).strip()
        title = match.group(2).strip()

    # Falls mehrere Autoren vorhanden sind (mit '&' getrennt)
    authoren = [author.strip() for author in authors_str.split('&')]
    #print("Authors: ", authoren)

    # Liste, um die aufgesplitteten Vornamen und Nachnamen zu speichern
    authors_list = []

    # Gehe durch jeden Autor
    for author in authoren:
        # Überprüfe, ob der es ein Komma gibt, d.h. Nachname, Vorname
        match = re.search(r',', author)
        if match:
            # d.h. Nachname, Vorname1 Vorname2
            author_name_parts = author.split(', ')
            # Der Nachname ist das erste Element
            lastname = author_name_parts[0].strip()
            firstname = author_name_parts[1].strip()
        else:
            # Vorname1 Vorname2 Nachname
            author_name_parts = author.split()
            # Der Nachname ist das letzte Element
            lastname = author_name_parts[-1]
            # Alle anderen Teile sind die Vornamen
            firstname = " ".join(author_name_parts[:-1])

        # Sonderfall: Autoren mit abgekürzten Vornamen wie "E.T.A."
        # Das behandelt Initialen als Vornamen
        if re.match(r'([A-Z]\.)+', firstname):
            firstname = firstname.replace(" ", "")

        # Füge den Vor- und Nachnamen zur Liste hinzu
        authors_list.append((firstname, lastname))

    # Rückgabe der extrahierten Daten: Liste der Autoren und der Titel
    #print(authors_list, title)
    return authors_list, title

# Funktion zum Auslesen des Autors aus der OPF-Datei in der EPUB-Datei
def extract_author_from_epub(epub_path):
    #vor = ""
    try:
        with zipfile.ZipFile(epub_path, 'r') as epub:
            # Suche nach der OPF-Datei (content.opf)
            for file in epub.namelist():
                if file.endswith('.opf'):
                    opf_data = epub.read(file).decode('utf-8')
                    # Suche den Autor in der OPF-Datei
                    # <dc:creator opf:file-as="Attanasio, A. A." opf:role="aut">A. A. Attanasio</dc:creator>
                    author_pattern = re.search(r'<dc:creator.*?>(.*?)</dc:creator>', opf_data)
                    if author_pattern:
                        author = author_pattern.group(1).strip()
                        #if vor != author:
                            #print(author)
                        #vor = author
                        # Sicherstellen, dass re.search nicht fehlschlägt
                        match = re.search(r',', author)
                        if match:
                            if match.start() > 0:
                                return author
                        else:
                            names = re.split(r'\s', author)
                            if len(names) > 1:
                                n = names[0]
                                for i in range(1, len(names) - 1):
                                    n = n + " " + names[i]
                                return names[len(names) - 1] + ", " + n
                            elif len(names) == 1:
                                return names[1] + ", " + names[0]
                            else:
                                return names[0]
        return None
    except Exception as e:
        with open(os.path.join(base_path, 'Probleme.txt'), 'w', encoding="utf-8") as file:

            file.write(f"{epub_path} - Fehler beim Auslesen des Autors:  {e} \n")
            #print(epub_path)
            # os.remove(epub_path)
            # print("D://Bücher//NEU/" + file)
            # os.rename(epub_path, "D://Bücher//NEU/" + file)
            return None


def scan_ebooks(base, sp, genre='Krimi'):
    # Durchlaufe das Verzeichnis und überprüfe den Autor
    for root, dirs, files in os.walk(base):
        for file in files:
            file_path = os.path.join(root, file)

            if file.endswith(('.epub', '.pdf', '.mobi')):  # Unterstützte Dateiformate
                print(file)
                authors, title = extract_metadata_from_filename(file)
                book = {'title': title, 'language': sp, 'path': genre}
                #print("extracted..")
                #print(authors, title)

                if file.endswith('.epub'):
                    epub_author = extract_author_from_epub(file_path)
                    if authors is None:
                        authors = epub_author
                    else:
                        # Überprüfen, ob der Autor im Dateinamen mit dem in den Metadaten übereinstimmt
                        if epub_author:
                            author_fullname = f"{authors[0][1]}, {authors[0][0]}".strip()
                            author_fullname = author_fullname.replace(".","").strip()
                            epub_author = epub_author.replace(".", "").strip()
                            if epub_author.lower() != author_fullname.lower():
                                mismatch_list.append({
                                    'filename': file,
                                    'file_author': author_fullname,
                                    'epub_author': epub_author
                                })
                else:
                    if authors is None:
                        authors = [("no","author")]

                # Buch mit Autoren in die Datenbank einfügen
                save_book_with_authors(book, authors)

    # Ausgabe der Liste von Dateien mit Problemen
    if mismatch_list:
        print("Folgende Dateien haben abweichende Autor-Informationen:")
        f = os.path.join(base_path, 'Report.txt')
        with (open(f, 'w', encoding="utf-8") as file):
            for mismatch in mismatch_list:
                try:
                    print(f"Datei: {mismatch['filename']}")
                    print(f"Autor im Dateinamen: {mismatch['file_author']}")
                    print(f"Autor in den Metadaten: {mismatch['epub_author']}")
                    print("-" * 40)
                    file.write(f"Datei {mismatch['filename']}: {mismatch['file_author']} vs. {mismatch['epub_author']} \n")
                except Exception as e:
                    file.write(f"{type(e).__name__} at line {e.__traceback__.tb_lineno} of {__file__}: {e}")
                    file.write(f"Datei {mismatch['filename']}")
                    file.write("-" * 40)
    else:
        print("Alle Autoren stimmen überein.")

if __name__ == "__main__":
    # Beispielaufruf
    def save_book_with_authors(book, authors):
       for author in authors:
           print(f'Autoren: {author}')
       for key in book:
           print(f' {key} = {book.get(key)}')
       print("____________")

    """
    # Beispielhafte Dateinamen testen
    filenames = [
        "Johann Wolfgang von Goethe - Faust.epub",
        "E.T.A. Hoffmann - Der Sandmann.epub",
        "Vorname1 Nachname1 & Vorname2 Nachname2 & Vorname3 Nachname3 - Ein Mehrautorenbuch.epub"
    ]

    for filename in filenames:
        authors, title = extract_metadata_from_filename(filename)
        print(f"Dateiname: {filename}")
        print(f"Autoren: {authors}")
        print(f"Titel: {title}")
        print("-" * 50)
    """

    # Pfad zu deinem Bücherverzeichnis auf BigDaddy
    base_path = 'D:\\Bücher\\Business\\Biographien'
    # Pfad zu deinem Bücherverzeichnis auf der Synology
    # base_path = "B:\\Deutsch"
    scan_ebooks(base_path, "DE", "Bio")