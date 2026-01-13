import os
import re
import shutil

LOG_FILE = r"D:\Bücher\report.txt"
BACKUP_BASE = r"\\Fredibox61\eBooks"
TARGET_BASE = r"D:\Bücher"


def normalize(text):
    """Entfernt alles, was kein Buchstabe oder Zahl ist, für den Vergleich."""
    return re.sub(r'\W+', '', text).lower()


def reverse_author_name(name):
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {' '.join(parts[:-1])}"
    return name


def find_best_match(directory, search_filename):
    """Sucht im Ordner nach einer Datei, die dem Namen ähnelt."""
    if not os.path.exists(directory):
        return None

    # Wir normalisieren den gesuchten Namen (ohne Endung und ohne Jahr)
    search_name = re.sub(r'\(\d{4}\)', '', search_filename)  # Jahr entfernen
    search_norm = normalize(os.path.splitext(search_name)[0])

    for f in os.listdir(directory):
        f_norm = normalize(os.path.splitext(f)[0])
        # Wenn der Kern-Name übereinstimmt (z.B. "mordsmäßigverliebt")
        if search_norm in f_norm or f_norm in search_norm:
            return f
    return None


def restore_from_backup():
    with open(LOG_FILE, "r", encoding="latin-1", errors="ignore") as f:
        full_text = f.read()

    # Wir suchen die Pfade im Log
    pattern = re.compile(r"Lösche korrupte Datei:.*?(D:.*?\.(?:epub|mobi))", re.IGNORECASE)
    source_paths = pattern.findall(full_text)

    print(f"🔍 {len(source_paths)} Pfade gefunden. Starte intelligente Suche...")

    restored = 0
    skipped_corrupt = 0

    for old_path in source_paths:
        p = old_path.strip().replace('/', '\\')
        parts = p.split('\\')
        if len(parts) < 6: continue

        sprache, buchstabe, author_vn, filename = parts[2], parts[3], parts[4], parts[-1]
        author_nn = reverse_author_name(author_vn)

        backup_dir = os.path.join(BACKUP_BASE, sprache, author_nn[0].upper(), author_nn)

        # Suche nach der Datei im Backup-Ordner
        match_file = find_best_match(backup_dir, filename)

        if match_file:
            backup_path = os.path.join(backup_dir, match_file)
            target_path = os.path.join(TARGET_BASE, sprache, buchstabe, author_vn, match_file)

            # Sicherheitscheck: Wenn wir wissen, dass die Datei auch im Backup korrupt ist
            # (Das müsstest du manuell entscheiden oder wir loggen es)

            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(backup_path, target_path)
                print(f"✅ Wiederhergestellt: {match_file}")
                restored += 1
            except Exception as e:
                print(f"❌ Fehler: {e}")
        else:
            pass  # Nicht gefunden

    print(f"\n--- FERTIG ---")
    print(f"Wiederhergestellt: {restored}")


if __name__ == "__main__":
    restore_from_backup()

def diagnose():
    if not os.path.exists(LOG_FILE):
        print("Datei nicht gefunden!")
        return

    # Wir lesen die Datei binär, um Encoding-Probleme zu sehen
    with open(LOG_FILE, "rb") as f:
        raw_data = f.read(2000)
        print(f"--- BINÄR-VORSCHAU ---\n{raw_data[:200]}\n")

        # Versuche verschiedene Encodings
        for enc in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
            try:
                text = raw_data.decode(enc)
                if "Lösche" in text or "Datei" in text:
                    print(f"✅ Erfolg mit Encoding: {enc}")
                    print(f"Text-Vorschau: {text[:300]}")
                    return
            except:
                continue
    print("❌ Kein bekanntes Wort in den ersten 2000 Zeichen gefunden.")




if __name__ == "__main__":
    restore_from_backup()
    # diagnose()