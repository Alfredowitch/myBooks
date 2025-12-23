import fitz  # PyMuPDF
from PIL import Image
import io


def get_book_cover(file_path):
    if file_path.lower().endswith('.epub'):
        # Hier bleibt dein bisheriger funktionierender Code für EPUB
        pass

    elif file_path.lower().endswith('.pdf'):
        try:
            # PDF öffnen
            doc = fitz.open(file_path)
            # Erste Seite laden
            page = doc.load_page(0)
            # Seite als Bild (Pixmap) rendern
            pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))  # 0.5 für schnellere Vorschau/kleineres Bild

            # Pixmap in PIL Image umwandeln (damit dein Editor es anzeigen kann)
            img_data = pix.tobytes("png")
            return Image.open(io.BytesIO(img_data))

        except Exception as e:
            print(f"Fehler beim PDF-Cover-Extrakt: {e}")
            return None  # Oder ein Standard-Platzhalterbild

    return None