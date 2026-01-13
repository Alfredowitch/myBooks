import os
import re

LOG_FILE = r"D:\Bücher\report.txt"
BACKUP_BASE = r"\\Fredibox61\eBooks"
TARGET_BASE = r"D:\Bücher"


def is_valid_ebook(file_path):
    if not file_path or not os.path.exists(file_path): return False
    try:
        with open(file_path, 'rb') as f:
            header = f.read(100)
            # Validierung: EPUB (ZIP), MOBI oder PDF
            if header.startswith(b'PK\x03\x04'): return True
            if b'BOOKMOBI' in header[60:100]: return True
            if header.startswith(b'%PDF'): return True
    except:
        pass
    return False


def reverse_author_name(name):
    parts = name.strip().split()
    return f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) >= 2 else name


def normalize(text):
    return re.sub(r'\W+', '', text).lower()


def find_in_backup(p):
    """Findet die entsprechende Datei im Backup, falls vorhanden."""
    p = p.strip().replace('/', '\\')
    is_mirror = any(x in p for x in ["Business", "_sortiertGenre", "byRegion", "byGenre"])

    if is_mirror:
        rel_path = p.replace(TARGET_BASE, "").lstrip('\\')
        backup_dir = os.path.join(BACKUP_BASE, os.path.dirname(rel_path))
        filename = os.path.basename(p)
    else:
        parts = p.split('\\')
        if len(parts) < 6: return None
        sprache, author_vn, filename = parts[2], parts[4], parts[-1]
        author_nn = reverse_author_name(author_vn)
        backup_dir = os.path.join(BACKUP_BASE, sprache, author_nn[0].upper(), author_nn)

    if not os.path.exists(backup_dir): return None

    # Suche im Ordner (unscharf)
    search_norm = normalize(os.path.splitext(re.sub(r'\(\d{4}\)', '', filename))[0])
    for f in os.listdir(backup_dir):
        if search_norm in normalize(os.path.splitext(f)[0]):
            return os.path.join(backup_dir, f)
    return None


def cleanup_corrupt_restorations():
    with open(LOG_FILE, "r", encoding="latin-1", errors="ignore") as f:
        full_text = f.read()

    # Alle Pfade aus dem Report extrahieren
    pattern = re.compile(r"Lösche korrupte Datei:.*?(D:.*?\.(?:epub|mobi))", re.IGNORECASE)
    original_paths = list(set(pattern.findall(full_text)))

    print(f"⚠️  Prüfe {len(original_paths)} Pfade auf D: gegen das Backup...")

    deleted_count = 0

    for p in original_paths:
        clean_p = p.strip().replace('/', '\\')

        # Wir schauen, ob wir die Datei (unter irgendeinem Namen) auf D: im Zielordner finden
        # Da wir sie vorhin kopiert haben, könnte sie jetzt dort liegen
        dir_on_d = os.path.dirname(clean_p)
        base_name_on_d = os.path.basename(clean_p)

        # Wir prüfen alle Dateien im Zielordner auf D:, die so ähnlich heißen
        if os.path.exists(dir_on_d):
            for f_on_d in os.listdir(dir_on_d):
                # Wenn die Datei auf D: dem Namen aus dem Report entspricht (unscharf)
                if normalize(os.path.splitext(base_name_on_d)[0]) in normalize(f_on_d):
                    full_path_d = os.path.join(dir_on_d, f_on_d)

                    # JETZT DER GEGEN-CHECK: Ist das Backup dazu heil?
                    backup_file = find_in_backup(clean_p)

                    if not backup_file or not is_valid_ebook(backup_file):
                        # Backup ist Schrott oder weg -> Datei auf D: muss weg!
                        try:
                            os.remove(full_path_d)
                            print(f"🗑️  GELÖSCHT (da Backup korrupt/fehlt): {f_on_d}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"❌ Fehler beim Löschen von {f_on_d}: {e}")

    print(f"\n--- BEREINIGUNG ABGESCHLOSSEN ---")
    print(f"Vom Laufwerk D: entfernte korrupte Dateien: {deleted_count}")


import os
import zipfile


def repair_french_extensions(root_path):
    count_renamed = 0

    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.lower().endswith(".epub"):
                full_path = os.path.join(root, file)

                # Prüfen, ob es ein echtes Epub (ZIP) ist
                is_valid_epub = False
                try:
                    with zipfile.ZipFile(full_path, 'r') as z:
                        # Ein minimaler Check auf die Struktur
                        if 'mimetype' in z.namelist():
                            is_valid_epub = True
                except:
                    # Wenn zipfile fehlschlägt, ist es kein echtes Epub
                    is_valid_epub = False

                if not is_valid_epub:
                    new_path = full_path.rsplit('.', 1)[0] + ".mobi"

                    # Falls die Zieldatei schon existiert, hängen wir ein Kürzel an
                    if os.path.exists(new_path):
                        new_path = full_path.rsplit('.', 1)[0] + "_fixed.mobi"

                    try:
                        os.rename(full_path, new_path)
                        print(f"Renamed: {file} -> .mobi")
                        count_renamed += 1
                    except Exception as e:
                        print(f"Error renaming {file}: {e}")

    print(f"\nFertig! Insgesamt {count_renamed} Dateien korrigiert.")



if __name__ == "__main__":
    # cleanup_corrupt_restorations()
    repair_french_extensions("D:/Bücher/French")