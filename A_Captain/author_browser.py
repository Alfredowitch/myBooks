# author_browser.py
# author_browser.py
import tkinter as tk
from D_Navigation.author_view import AuthorView
from Bridge.author_bridge import AuthorBridge


class AuthorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enterprise - Author Master Control")

        # Die Brücke verbindet UI und Engineering
        self.bridge = AuthorBridge()

        # Die View baut das 3-spaltige Layout
        self.view = AuthorView(self.root, self.bridge)
        self.bridge.view = self.view

        # Start-Modus: Author Browsing
#        self.switch_mode("BROWSE_AUTHORS")



if __name__ == "__main__":
    app = AuthorApp()
    app.root.mainloop()