import tkinter as tk

def edit_description_and_rating(initial_description, amazon_rating):
    root = tk.Tk()
    root.title("Beschreibung & Bewertung bearbeiten")

    # Hier speichern wir die Benutzereingaben
    result = {"description": initial_description, "rating": None}

    # Beschreibungstextfeld
    tk.Label(root, text="Beschreibung:").pack()
    description_text = tk.Text(root, height=10, width=50)
    description_text.insert("1.0", initial_description)
    description_text.pack()

    # Anzeige der Amazon-Bewertung
    tk.Label(root, text=f"Amazon-Bewertung: {amazon_rating}").pack()

    # Eingabefeld für eigene Bewertung
    tk.Label(root, text="Eigene Bewertung:").pack()
    own_rating_entry = tk.Entry(root)
    own_rating_entry.pack()

    def on_close():
        """Speichert die Eingaben und schließt das Fenster."""
        result["description"] = description_text.get("1.0", tk.END).strip()
        result["rating"] = own_rating_entry.get().strip() or None
        print(result["description"], result["rating"])  # Debugging
        root.destroy()

    # Speichern & Schließen-Button
    save_button = tk.Button(root, text="Speichern und Schließen", command=on_close)
    save_button.pack(pady=10)

    # Enter-Taste als Shortcut zum Speichern
    root.bind("<Return>", lambda event: on_close())

    # Schließen-Event abfangen
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Warten, bis done = True ist
    root.mainloop()


    return result["description"], result["rating"]

# Apps-Aufruf

root = tk.Tk()
root.geometry('900x400')

#frame_top = tk.Frame(win)
#frame_top.pack()

#frame_custom = tk.Frame(win)
#frame_custom.pack()
tk.Label(root, text="Titel").pack()

#tk.Label(frame_top, text="Titel").pack()
button = tk.Button(root, text="Ich fliege")
button.place(x=100, y=200)
save_button = tk.Button(root, text="Close", command=lambda: root.quit())
save_button.place(x=400, y=200)
# Der Event-Loop
root.mainloop()


# new_desc, own_rating = edit_description_and_rating("Alte Beschreibung", "4.5 Sterne")
# print("Neue Beschreibung:", new_desc)
# print("Eigene Bewertung:", own_rating)
