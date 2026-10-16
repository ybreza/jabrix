import asyncio
import queue
import sqlite3
import threading
import tkinter as tk
from datetime import datetime
from functools import partial
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import slixmpp
from slixmpp.exceptions import IqError, IqTimeout

APP_TITLE = "JabriX"
PLACEHOLDER = "Pilih teman untuk mulai chat"
DB_FILE = Path.home() / ".xmpp_chat.db"
STAMP = "%d/%m %H:%M"
SHOW = {"Online": None, "Away": "away", "Jangan Ganggu": "dnd"}
STATES = {"away": "away", "xa": "away", "dnd": "dnd"}
COLORS = {"on": "#1a9c3c", "away": "#e0a100", "dnd": "#c0392b", "off": "#888888"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    contact TEXT NOT NULL,
    mine INTEGER NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat ON messages (account, contact, id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Client(slixmpp.ClientXMPP):
    def __init__(self, jid, password, events):
        super().__init__(jid, password)
        self.events = events
        self.auto_authorize = None
        self.register_plugin("xep_0199")
        self.add_event_handler("session_start", self.on_start)
        self.add_event_handler("message", self.on_message)
        self.add_event_handler("roster_subscription_request", self.on_request)
        self.add_event_handler("roster_update", self.push_roster)
        self.add_event_handler("changed_status", self.push_roster)
        for event in ("failed_auth", "failed_all_auth"):
            self.add_event_handler(event, lambda _: self.fail("JID atau password salah"))
        self.add_event_handler("connection_failed", lambda _: self.fail("Gagal terhubung ke server"))
        self.add_event_handler("disconnected", lambda _: self.fail("Koneksi terputus"))

    def fail(self, reason):
        self.events.put(("error", reason))

    async def on_start(self, _):
        self.send_presence()
        try:
            await self.get_roster()
        except (IqError, IqTimeout):
            return self.fail("Gagal mengambil daftar teman")
        self.events.put(("login",))

    def push_roster(self, _):
        friends = {jid: self.state(jid) for jid in self.client_roster.keys() if self.is_friend(jid)}
        self.events.put(("roster", friends))

    def is_friend(self, jid):
        item = self.client_roster[jid]
        return item["to"] or item["from"] or item["pending_out"]

    def state(self, jid):
        resources = self.client_roster[jid].resources.values()
        return next((STATES.get(r["show"], "on") for r in resources), "off")

    def on_message(self, msg):
        if msg["type"] in ("chat", "normal") and msg["body"]:
            self.events.put(("message", msg["from"].bare, msg["body"]))

    def on_request(self, presence):
        jid = presence["from"].bare
        if self.client_roster[jid]["to"]:
            self.answer(jid, True)
        else:
            self.events.put(("request", jid))

    def answer(self, jid, accept):
        self.send_presence(pto=jid, ptype="subscribed" if accept else "unsubscribed")
        if accept and not self.client_roster[jid]["to"]:
            self.send_presence_subscription(pto=jid)


class Session:
    def __init__(self, jid, password):
        self.events = queue.Queue()
        self.loop = asyncio.new_event_loop()
        self.client = None
        threading.Thread(target=self.run, args=(jid, password), daemon=True).start()

    def run(self, jid, password):
        asyncio.set_event_loop(self.loop)
        self.client = Client(jid, password, self.events)
        self.client.connect()
        self.loop.run_forever()

    def call(self, name, **kwargs):
        self.loop.call_soon_threadsafe(partial(getattr(self.client, name), **kwargs))

    def close(self):
        def stop():
            self.client.auto_reconnect = False
            self.client.disconnect().add_done_callback(lambda _: self.loop.stop())

        self.loop.call_soon_threadsafe(stop)


class Database:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def add(self, account, contact, mine, body):
        now = datetime.now()
        with self.db:
            self.db.execute(
                "INSERT INTO messages (account, contact, mine, body, sent_at) VALUES (?, ?, ?, ?, ?)",
                (account, contact, mine, body, now.isoformat(" ", "seconds")),
            )
        return now.strftime(STAMP)

    def history(self, account, contact):
        return self.db.execute(
            "SELECT mine, body, strftime(?, sent_at) FROM messages WHERE account = ? AND contact = ? ORDER BY id",
            (STAMP, account, contact),
        ).fetchall()

    def contacts(self, account):
        rows = self.db.execute("SELECT DISTINCT contact FROM messages WHERE account = ?", (account,))
        return [row[0] for row in rows]

    def delete_chat(self, account, contact):
        with self.db:
            self.db.execute("DELETE FROM messages WHERE account = ? AND contact = ?", (account, contact))

    def get(self, key, default=""):
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def put(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x500")
        self.minsize(560, 360)
        self.setup_icon()
        self.db = Database(DB_FILE)
        self.session = None
        self.me = ""
        self.current = None
        self.roster = {}
        self.unread = {}
        self.search_var = tk.StringVar()
        self.show_pass_var = tk.BooleanVar(value=False)
        self.remember_var = tk.BooleanVar(value=self.db.get("remember_password", "1") == "1")
        self.jid_var = tk.StringVar(value=self.db.get("last_jid"))
        saved_pass = self.db.get("saved_password") if self.remember_var.get() else ""
        self.pass_var = tk.StringVar(value=saved_pass)
        self.info_var = tk.StringVar()
        self.build_login()
        self.build_chat()
        self.show(self.login_frame)
        self.bind("<FocusIn>", self.on_focus)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.after(100, self.poll)

    def setup_icon(self):
        base_dir = Path(__file__).resolve().parent
        ico_file = base_dir / "icon.ico"
        png_file = base_dir / "logo.png"
        if ico_file.exists():
            try:
                self.iconbitmap(default=str(ico_file))
            except Exception:
                try:
                    self.iconbitmap(str(ico_file))
                except Exception:
                    pass
        if png_file.exists():
            try:
                self.app_icon = tk.PhotoImage(file=str(png_file))
                self.iconphoto(True, self.app_icon)
            except Exception:
                pass

    def build_login(self):
        self.login_frame = ttk.Frame(self)
        box = ttk.Frame(self.login_frame)
        box.place(relx=0.5, rely=0.5, anchor="center")

        base_dir = Path(__file__).resolve().parent
        logo_path = base_dir / "logo_small.png"
        if not logo_path.exists():
            logo_path = base_dir / "logo.png"
        if logo_path.exists():
            try:
                self.logo_img = tk.PhotoImage(file=str(logo_path))
                ttk.Label(box, image=self.logo_img).pack(pady=(0, 8))
            except Exception:
                pass

        ttk.Label(box, text="Login JabriX", font=("", 16, "bold")).pack(pady=(0, 14))

        ttk.Label(box, text="JID (user@server)").pack(anchor="w")
        entry_jid = ttk.Entry(box, textvariable=self.jid_var, width=34)
        entry_jid.pack(pady=(0, 8))
        entry_jid.bind("<Return>", self.login)

        ttk.Label(box, text="Password").pack(anchor="w")
        self.pass_entry = ttk.Entry(box, textvariable=self.pass_var, show="*" if not self.show_pass_var.get() else "", width=34)
        self.pass_entry.pack(pady=(0, 6))
        self.pass_entry.bind("<Return>", self.login)

        opt_frame = ttk.Frame(box)
        opt_frame.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(opt_frame, text="Ingat password", variable=self.remember_var).pack(side="left")
        ttk.Checkbutton(opt_frame, text="Tampilkan", variable=self.show_pass_var, command=self.toggle_show_pass).pack(side="right")

        ttk.Button(box, text="Login", command=self.login).pack(fill="x")
        ttk.Label(box, textvariable=self.info_var, foreground="#c0392b", wraplength=260).pack(pady=8)

    def toggle_show_pass(self):
        self.pass_entry.configure(show="" if self.show_pass_var.get() else "*")

    def build_chat(self):
        self.chat_frame = ttk.Frame(self)

        # Bottom Status Bar
        self.status_bar = ttk.Frame(self.chat_frame, padding=(8, 4))
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar_label = ttk.Label(self.status_bar, text="", font=("", 8), foreground="#555555")
        self.status_bar_label.pack(side="left")

        # Sidebar
        side = ttk.Frame(self.chat_frame)
        side.pack(side="left", fill="y")
        self.me_label = ttk.Label(side, padding=8, font=("", 10, "bold"))
        self.me_label.pack(fill="x")
        self.status = ttk.Combobox(side, values=list(SHOW), state="readonly")
        self.status.bind("<<ComboboxSelected>>", self.set_status)
        self.status.pack(fill="x", padx=6, pady=(0, 6))

        # Search Bar for contacts
        search_frame = ttk.Frame(side)
        search_frame.pack(fill="x", padx=6, pady=(0, 4))
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill="x")
        self.search_var.trace_add("write", lambda *_: self.refresh_tree())

        self.tree = ttk.Treeview(side, show="tree", selectmode="browse")
        for tag, color in COLORS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.pack(fill="both", expand=True, padx=6)
        for text, command in (("Tambah Teman", self.add_friend), ("Hapus Teman", self.delete_friend), ("Logout", self.logout)):
            ttk.Button(side, text=text, command=command).pack(fill="x", padx=6, pady=(6, 0))
        ttk.Frame(side, height=6).pack()

        # Main chat area
        main = ttk.Frame(self.chat_frame)
        main.pack(side="right", fill="both", expand=True)

        header_bar = ttk.Frame(main, padding=(8, 6))
        header_bar.pack(fill="x")
        self.title_label = ttk.Label(header_bar, text=PLACEHOLDER, font=("", 11, "bold"))
        self.title_label.pack(side="left", fill="x", expand=True)
        self.clear_chat_btn = ttk.Button(header_bar, text="Bersihkan Chat", command=self.clear_current_chat, state="disabled")
        self.clear_chat_btn.pack(side="right")

        box = ttk.Frame(main)
        box.pack(fill="both", expand=True)
        self.log = tk.Text(box, state="disabled", wrap="word", padx=8, pady=8, relief="flat")
        self.log.tag_configure("me", foreground="#1b5fc1")
        self.log.tag_configure("them", foreground="#222222")
        self.log.tag_configure("time", foreground="#999999")
        scroll = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        # Context menu on chat log
        self.chat_menu = tk.Menu(self, tearoff=0)
        self.chat_menu.add_command(label="Salin", command=self.copy_selection)
        self.chat_menu.add_command(label="Pilih Semua", command=self.select_all_log)
        self.log.bind("<Button-3>", self.show_context_menu)

        bar = ttk.Frame(main, padding=6)
        bar.pack(fill="x")
        self.entry = ttk.Entry(bar)
        self.entry.bind("<Return>", self.send)
        self.entry.pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="Kirim", command=self.send).pack(side="right", padx=(6, 0))

    def show(self, frame):
        self.login_frame.pack_forget()
        self.chat_frame.pack_forget()
        frame.pack(fill="both", expand=True)

    def poll(self):
        while self.session:
            try:
                event, *args = self.session.events.get_nowait()
            except queue.Empty:
                break
            getattr(self, f"on_{event}")(*args)
        self.after(100, self.poll)

    def login(self, _=None):
        jid, password = self.jid_var.get().strip(), self.pass_var.get()
        if self.session:
            return
        if "@" not in jid or not password:
            return self.info_var.set("Isi JID (user@server) dan password")
        self.info_var.set("Menghubungkan...")
        self.me = jid
        self.session = Session(jid, password)

    def logout(self, reason=""):
        if self.session:
            self.session.close()
        self.session = None
        self.roster, self.unread = {}, {}
        self.reset_chat()
        self.refresh_tree()
        self.info_var.set(reason)
        if self.remember_var.get():
            self.pass_var.set(self.db.get("saved_password"))
        self.show(self.login_frame)

    def reset_chat(self):
        self.current = None
        self.title_label.configure(text=PLACEHOLDER)
        if hasattr(self, "clear_chat_btn"):
            self.clear_chat_btn.configure(state="disabled")
        self.clear_log()

    def on_login(self):
        self.db.put("last_jid", self.me)
        if self.remember_var.get():
            self.db.put("remember_password", "1")
            self.db.put("saved_password", self.pass_var.get())
        else:
            self.db.put("remember_password", "0")
            self.db.put("saved_password", "")
        self.info_var.set("")
        self.me_label.configure(text=self.me)
        self.status.set("Online")
        self.show(self.chat_frame)
        self.refresh_tree()
        self.entry.focus()

    def on_error(self, reason):
        self.logout(reason)

    def on_roster(self, roster):
        self.roster = {jid: "off" for jid in self.db.contacts(self.me)} | roster
        self.refresh_tree()

    def on_message(self, jid, body):
        self.roster.setdefault(jid, "off")
        self.record(jid, False, body)
        if jid != self.current or not self.focus_displayof():
            self.unread[jid] = self.unread.get(jid, 0) + 1
            self.bell()
        self.refresh_tree()

    def on_request(self, jid):
        accept = messagebox.askyesno("Permintaan Teman", f"{jid} ingin berteman dengan Anda. Terima?", parent=self)
        self.session.call("answer", jid=jid, accept=accept)

    def on_focus(self, _):
        if self.unread.pop(self.current, None):
            self.refresh_tree()

    def refresh_tree(self):
        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        visible_roster = {
            jid: state for jid, state in self.roster.items()
            if not query or query in jid.lower()
        }
        for jid in set(self.tree.get_children()) - set(visible_roster):
            self.tree.delete(jid)
        for jid, state in visible_roster.items():
            if not self.tree.exists(jid):
                self.tree.insert("", "end", iid=jid)
            badge = f" ({self.unread[jid]})" if jid in self.unread else ""
            self.tree.item(jid, text=f"● {jid}{badge}", tags=(state,))
        total = sum(self.unread.values())
        self.title(f"({total}) {APP_TITLE}" if total else APP_TITLE)

        if hasattr(self, "status_bar_label") and self.me:
            online_count = sum(1 for s in self.roster.values() if s != "off")
            total_count = len(self.roster)
            self.status_bar_label.configure(
                text=f"Terhubung sebagai: {self.me}   •   {online_count}/{total_count} teman online"
            )

    def select(self, _=None):
        if not self.tree.selection():
            return
        self.current = self.tree.selection()[0]
        self.unread.pop(self.current, None)
        state_names = {"on": "Online", "away": "Away", "dnd": "Jangan Ganggu", "off": "Offline"}
        st = state_names.get(self.roster.get(self.current, "off"), "Offline")
        self.title_label.configure(text=f"{self.current}   •   ● {st}")
        if hasattr(self, "clear_chat_btn"):
            self.clear_chat_btn.configure(state="normal")
        self.clear_log()
        for mine, text, stamp in self.db.history(self.me, self.current):
            self.write(mine, text, stamp)
        self.refresh_tree()
        self.entry.focus()

    def clear_current_chat(self):
        if not self.current:
            return
        if messagebox.askyesno("Bersihkan Chat", f"Hapus seluruh riwayat chat dengan {self.current}?", parent=self):
            self.db.delete_chat(self.me, self.current)
            self.clear_log()

    def show_context_menu(self, event):
        try:
            self.chat_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.chat_menu.grab_release()

    def copy_selection(self):
        try:
            selected = self.log.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected)
        except tk.TclError:
            pass

    def select_all_log(self):
        self.log.tag_add("sel", "1.0", "end")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def write(self, mine, text, stamp):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{stamp}] ", "time")
        self.log.insert("end", f"{'Anda' if mine else self.current}: {text}\n", "me" if mine else "them")
        self.log.configure(state="disabled")
        self.log.see("end")

    def record(self, jid, mine, text):
        stamp = self.db.add(self.me, jid, mine, text)
        if jid == self.current:
            self.write(mine, text, stamp)

    def send(self, _=None):
        text = self.entry.get().strip()
        if not text or not self.current:
            return
        self.session.call("send_message", mto=self.current, mbody=text, mtype="chat")
        self.record(self.current, True, text)
        self.entry.delete(0, "end")

    def set_status(self, _=None):
        self.session.call("send_presence", pshow=SHOW[self.status.get()])

    def add_friend(self):
        jid = (simpledialog.askstring("Tambah Teman", "JID teman (user@server):", parent=self) or "").strip()
        if not jid:
            return
        if "@" not in jid:
            return messagebox.showwarning("Tambah Teman", "Format JID harus user@server", parent=self)
        self.session.call("send_presence_subscription", pto=jid)
        messagebox.showinfo("Tambah Teman", f"Permintaan pertemanan dikirim ke {jid}", parent=self)

    def delete_friend(self):
        jid = self.current
        if not jid or not messagebox.askyesno("Hapus Teman", f"Hapus {jid} beserta riwayat chat?", parent=self):
            return
        self.session.call("del_roster_item", jid=jid)
        self.db.delete_chat(self.me, jid)
        for store in (self.unread, self.roster):
            store.pop(jid, None)
        self.reset_chat()
        self.refresh_tree()

    def quit_app(self):
        if self.session:
            self.session.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()