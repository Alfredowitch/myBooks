import tkinter as tk

def on_close(parameter):
    """
    Diese Funktion wird aufgerufen, wenn das Fenster geschlossen wird. Sie speichert
    die Eingabedaten (Parameter) und beendet das Programm.
    """
    print(f"Fenster wird geschlossen. Parameter: {parameter}")
    root.quit()  # Beendet das Tkinter-Fenster

def start_window():
    """
    Diese Funktion erstellt das Tkinter-Fenster und ermöglicht dem Benutzer die Eingabe.
    Wenn das Fenster geschlossen wird, wird der eingegebene Text gespeichert.
    """
    global root
    root = tk.Tk()  # Erstellt das Fenster

    # Erstellen einer StringVar für die Eingabe
    entry_value = tk.StringVar()

    # Eingabefeld (breiteres Fenster)
    entry = tk.Entry(root, textvariable=entry_value, width=40)  # width erhöht
    entry.pack(padx=10, pady=10)  # padding für ein wenig Abstand

    # Done Variable
    done = tk.BooleanVar()

    # Button zum Schließen und Speichern
    button = tk.Button(root, text="Speichern und Schließen", command=lambda: done.set(True))
    button.pack(pady=10)

    # Wenn das Fenster geschlossen wird, rufen wir on_close auf und übergeben den Wert des Eingabefelds
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(entry_value.get()))

    # Waitet, bis die done-Variable auf True gesetzt wird
    root.wait_variable(done)

    # Hier kannst du den Wert nach dem Schließen des Fensters weiter verwenden
    print(f"Der Benutzer hat eingegeben: {entry_value.get()}")

if __name__ == "__main__":
    # Beispielaufruf
    # Startet das Fenster
    start_window()
