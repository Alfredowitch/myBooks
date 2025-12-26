from scan_ebooks import scan_ebooks
from save_db_ebooks import save_book_with_authors

# Pfad zu deinem Bücherverzeichnis auf BigDaddy
base_path = 'D:\\Bücher\\Wedding'
# Pfad zu deinem Bücherverzeichnis auf der Synology
# base_path = "B:\\Deutsch"
scan_ebooks(base_path, "Wedding")

