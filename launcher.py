import tkinter as tk
import sv_ttk
import subprocess
import os

from tkinter import ttk, messagebox

class UIManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root

    def character_limit(self, entry: tk.Entry, limit: int) -> None:
        char_count = len(entry.get())

        overlap = char_count - limit

        if overlap > 0:
            entry.delete(char_count - overlap, tk.END)

    def Heading(self, text: str) -> None:
        heading = ttk.Label(self.root, text=text, font=("Segoe UI", 18, "bold"))
        heading.pack(pady=(10, 5))

    def Subheading(self, text: str) -> None:
        subheading = ttk.Label(self.root, text=text, font=("Segoe UI", 14, "bold"))
        subheading.pack(pady=(0, 15))

    def Checkbox(self, heading: str, variable: tk.BooleanVar) -> None:
        line1 = ttk.Frame(self.root)
        line1.pack(fill='x', pady=5)

        label1 = ttk.Label(line1, text=heading)
        label1.pack(side='left', padx=(10, 0))

        # Add some horizontal padding before checkbox
        checkbox = ttk.Checkbutton(line1, variable=variable)
        checkbox.pack(side='left', padx=(10, 0))

    def TextInput(self, heading: str, initial_value: str, disabled: bool = False, limit: int = 0) -> object:
        """Returns the function to get the value in the text entry"""

        line2 = ttk.Frame(self.root)
        line2.pack(fill='x', pady=5)

        label2 = ttk.Label(line2, text=heading)
        label2.pack(side='left', padx=(10, 0))

        if disabled:
            state = "readonly"
        else:
            state = "normal"

        entry = ttk.Entry(line2)
        entry.pack(side='left', fill='x', expand=True, padx=(10, 10))

        entry.insert(0, initial_value)
        entry.configure(state=state)

        if limit > 0:
            entry.bind("<KeyRelease>", lambda x: self.character_limit(entry, limit))

        return entry.get

    def Button(self, heading: str, button_text: str, command: object) -> None:
        line1 = ttk.Frame(self.root)
        line1.pack(fill='x', pady=5)

        label1 = ttk.Label(line1, text=heading)
        label1.pack(side='left', padx=(10, 0))

        # Add some horizontal padding before checkbox
        checkbox = ttk.Button(line1, text=button_text, command=command)
        checkbox.pack(side='left', padx=(10, 0))

class Launcher:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Shape Royale Launcher")
        self.root.geometry("400x600")

        self.get_name = lambda: "player"
        self.get_server_ip = lambda: "0.0.0.0"
        self.get_server_port = lambda: "31415"

        self.ui_mgr = UIManager(self.root)
        self.construct()

        sv_ttk.set_theme('dark', self.root)
        self.root.mainloop()

    def get_executable(self) -> str:
        files = os.listdir()

        if "ShapeRoyale.exe" in files:
            return os.path.abspath("ShapeRoyale.exe") # Windows
        elif "ShapeRoyale" in files:
            return os.path.abspath("ShapeRoyale") # Linux
        elif "main.py" in files:
            return os.path.abspath("pyrun.sh") # Python

        return ""

    def join_multiplayer(self) -> None:
        name = self.get_name()
        host = self.get_server_ip()
        port = self.get_server_port()

        if not port.isdigit():
            messagebox.showerror("Error", "Port needs to be a number!")
            return

        self.root.withdraw()
        proc = subprocess.Popen(
            [self.get_executable(), "join", host, port, name]
        )
        proc.wait()
        self.root.deiconify()

    def host_multiplayer(self) -> None:
        name = self.get_name()
        host = self.get_server_ip()
        port = self.get_server_port()

        if not port.isdigit():
            messagebox.showerror("Error", "Port needs to be a number!")
            return

        self.root.withdraw()
        proc = subprocess.Popen(
            [self.get_executable(), "host", host, port, name]
        )
        proc.wait()
        self.root.deiconify()
    
    def start_singleplayer(self) -> None:
        self.root.withdraw()
        proc = subprocess.Popen([self.get_executable()])
        proc.wait()
        self.root.deiconify()

    def construct(self) -> None:
        self.ui_mgr.Heading("SHAPE ROYALE (PRE-ALPHA)")

        self.get_name = self.ui_mgr.TextInput("NAME:", "player", limit=25)

        self.ui_mgr.Subheading("\nMULTIPLAYER")

        self.get_server_ip = self.ui_mgr.TextInput("SERVER IP:", "0.0.0.0")
        self.get_server_port = self.ui_mgr.TextInput("PORT:", "31415")

        self.ui_mgr.Button("", "JOIN MULTIPLAYER", self.join_multiplayer)
        self.ui_mgr.Button("", "HOST MULTIPLAYER", self.host_multiplayer)

        self.ui_mgr.Subheading("\nSINGLEPLAYER")

        self.ui_mgr.Button("", "START SINGLEPLAYER", self.start_singleplayer)

if __name__ == "__main__":
    Launcher()