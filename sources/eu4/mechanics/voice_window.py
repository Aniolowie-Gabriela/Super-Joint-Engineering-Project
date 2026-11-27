"""Okno Windows dla asystenta głosowego działającego w zasobniku."""

from queue import Empty, SimpleQueue
import threading
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk


class VoiceWindow:
    def __init__(self, app, statuses, colors, icon):
        self.app = app
        self.statuses = statuses
        self.colors = colors
        self.events = SimpleQueue()
        self.last_state = None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Asystent głosowy EU4")
        self.root.geometry("520x420")
        self.root.minsize(420, 370)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.icon = ImageTk.PhotoImage(icon, master=self.root)
        self.root.iconphoto(True, self.icon)

        self.status_text = tk.StringVar(master=self.root, value=self.statuses["idle"])
        self.transcripts = {
            "user": tk.StringVar(master=self.root, value="…"),
            "agent": tk.StringVar(master=self.root, value="…"),
        }
        self.error = tk.StringVar(master=self.root)

        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Hint.TLabel", foreground="#475569")
        style.configure("Error.TLabel", foreground="#a21d29")
        style.configure("Hold.TButton", font=("Segoe UI", 12, "bold"), padding=(14, 12))

        frame = ttk.Frame(self.root, padding=(22, 18))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Asystent głosowy EU4", style="Title.TLabel").pack(anchor="w")

        status_row = ttk.Frame(frame)
        status_row.pack(fill="x", pady=(10, 16))
        self.status_dot = tk.Canvas(status_row, width=14, height=14, highlightthickness=0, relief="flat")
        self.status_dot.pack(side="left", padx=(0, 6))
        self.dot = self.status_dot.create_oval(2, 2, 12, 12, width=0)
        ttk.Label(status_row, textvariable=self.status_text, style="Section.TLabel").pack(side="left")
        self.disconnect = ttk.Button(status_row, text="Rozłącz", command=self.request_disconnect)
        self.disconnect.pack(side="right")

        self.hold = ttk.Button(frame, text="Przytrzymaj, aby mówić", style="Hold.TButton")
        self.hold.pack(fill="x")
        self.hold.bind("<ButtonPress-1>", self.press)
        self.hold.bind("<ButtonRelease-1>", self.release)
        self.hold.bind("<KeyPress-space>", self.press)
        self.hold.bind("<KeyRelease-space>", self.release)
        self.hold.bind("<FocusOut>", self.release)
        ttk.Label(
            frame, text=f"Możesz też przytrzymać {app.hotkey_text}. Puść po zadaniu pytania.", style="Hint.TLabel",
        ).pack(anchor="w", pady=(7, 14))
        ttk.Separator(frame).pack(fill="x")

        wrapped = []
        for field, title in (("user", "Twoje pytanie"), ("agent", "Odpowiedź")):
            ttk.Label(frame, text=title, style="Section.TLabel").pack(anchor="w", pady=(10, 2))
            label = ttk.Label(frame, textvariable=self.transcripts[field], justify="left", wraplength=460)
            label.pack(anchor="w", fill="x")
            wrapped.append(label)
        label = ttk.Label(frame, textvariable=self.error, style="Error.TLabel", justify="left", wraplength=460)
        label.pack(anchor="w", fill="x", pady=(8, 0))
        wrapped.append(label)
        frame.bind("<Configure>", lambda event: self.resize_text(wrapped, event.width))

    def resize_text(self, labels, width):
        for label in labels:
            label.configure(wraplength=max(width - 44, 1))

    def press(self, event):
        self.hold.focus_set()
        if event.type == tk.EventType.ButtonPress:
            self.hold.grab_set()
        self.app.set_talking("button", True)
        return "break"

    def release(self, _event=None):
        if self.hold.grab_current() == self.hold:
            self.hold.grab_release()
        self.app.set_talking("button", False)
        return "break"

    def request_disconnect(self):
        threading.Thread(target=self.app.end_conversation, daemon=True).start()

    def post(self, event, text=None):
        self.events.put((event, text))

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        self.release()
        self.root.withdraw()

    def refresh(self):
        if not self.app.running:
            self.root.destroy()
            return
        state = self.app.current_state()
        if state != self.last_state:
            self.last_state = state
            self.status_text.set(self.statuses[state])
            self.status_dot.itemconfigure(self.dot, fill="#%02x%02x%02x" % self.colors[state])
            self.hold.state(["pressed"] if state == "listening" else ["!pressed"])
            self.hold.configure(text="Puść, gdy skończysz" if state == "listening" else "Przytrzymaj, aby mówić")
            self.disconnect.state(["!disabled"] if self.app.conversation is not None else ["disabled"])
            if state == "listening":
                self.error.set("")
        while True:
            try:
                event, text = self.events.get_nowait()
            except Empty:
                break
            if event == "show":
                self.show()
            elif event == "error":
                self.error.set(text)
            else:
                self.transcripts[event].set(text)
        self.root.after(100, self.refresh)

    def run(self, show_window):
        if show_window:
            self.show()
        self.refresh()
        self.root.mainloop()
