import base64
import json
import mimetypes
import os
import queue
import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, ttk


class SocketClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chit Chat")
        self.configure(bg="#121621")
        self.geometry("860x600")
        self.resizable(True, True)

        self.socket = None
        self.reader = None
        self.writer = None
        self.nickname = None
        self.weather_unit = "c"
        self.incoming = queue.Queue()
        self.image_refs = []

        self._configure_styles()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._drain_incoming)

    def _configure_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.style.configure(
            "ChitChat.TButton",
            font=("Helvetica", 11, "bold"),
            padding=(12, 7),
            background="#4c7dff",
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
        )
        self.style.map(
            "ChitChat.TButton",
            background=[("pressed", "#3259cb"), ("active", "#3b66dd")],
            foreground=[("disabled", "#8fa1ca"), ("active", "#ffffff")],
        )

        self.style.configure(
            "Sidebar.TButton",
            font=("Helvetica", 10, "bold"),
            padding=(10, 5),
            background="#34415f",
            foreground="#f5f7ff",
            borderwidth=0,
            focusthickness=0,
        )
        self.style.map(
            "Sidebar.TButton",
            background=[("pressed", "#2d3953"), ("active", "#42517a")],
            foreground=[("disabled", "#8fa1ca"), ("active", "#ffffff")],
        )

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(1, weight=1)

        header_frame = tk.Frame(self, bg="#121621")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 8))
        header_frame.columnconfigure(0, weight=1)

        title_label = tk.Label(
            header_frame,
            text="Chit Chat",
            bg="#121621",
            fg="#f4f7ff",
            font=("Avenir Next", 22, "bold"),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = tk.Label(
            header_frame,
            text="Live group chat with users, weather, and image sharing",
            bg="#121621",
            fg="#91a4d8",
            font=("Helvetica", 10),
            anchor="w",
        )
        subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.chat_frame = tk.Frame(
            self,
            bg="#0e1220",
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#26314a",
        )
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=(8, 12))
        self.chat_frame.rowconfigure(0, weight=1)
        self.chat_frame.columnconfigure(0, weight=1)

        self.text_area = scrolledtext.ScrolledText(
            self.chat_frame,
            state="disabled",
            bg="#0b1020",
            fg="#dbe6ff",
            insertbackground="#dbe6ff",
            font=("Avenir Next", 13),
            borderwidth=0,
            wrap=tk.WORD,
        )
        self.text_area.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._configure_message_tags()

        self.sidebar = tk.Frame(
            self,
            bg="#171c2a",
            width=250,
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#26314a",
        )
        self.sidebar.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=(8, 12))
        self.sidebar.rowconfigure(1, weight=1)
        self.sidebar.columnconfigure(0, weight=1)

        sidebar_title = tk.Label(
            self.sidebar,
            text="Current Users",
            bg="#171c2a",
            fg="#f5f7ff",
            font=("Avenir Next", 13, "bold"),
        )
        sidebar_title.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

        self.user_list = tk.Listbox(
            self.sidebar,
            bg="#0d1220",
            fg="#c5d2ff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2e3954",
            highlightcolor="#4c7dff",
            activestyle="none",
            font=("Avenir Next", 11),
            selectbackground="#4c7dff",
            selectforeground="#ffffff",
        )
        self.user_list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))

        unit_label = tk.Label(
            self.sidebar,
            text="Weather Unit",
            bg="#171c2a",
            fg="#f5f7ff",
            font=("Avenir Next", 11, "bold"),
            anchor="w",
        )
        unit_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 6))

        self.weather_unit_var = tk.StringVar(value="Celsius (°C)")
        self.unit_dropdown = ttk.Combobox(
            self.sidebar,
            textvariable=self.weather_unit_var,
            values=("Celsius (°C)", "Fahrenheit (°F)"),
            state="readonly",
            font=("Helvetica", 10),
        )
        self.unit_dropdown.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))
        self.unit_dropdown.bind("<<ComboboxSelected>>", self._on_weather_unit_change)

        help_text = tk.Label(
            self.sidebar,
            text="/help /users /msg USER TEXT /unit C|F /weather CITY /image PATH",
            wraplength=180,
            justify="left",
            bg="#171c2a",
            fg="#9fb0dc",
            font=("Helvetica", 9),
        )
        help_text.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 10))

        refresh_button = ttk.Button(
            self.sidebar,
            text="Refresh Users",
            command=lambda: self._send_json({"type": "users"}),
            style="Sidebar.TButton",
        )
        refresh_button.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 14))

        input_frame = tk.Frame(self, bg="#121621")
        input_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)

        self.input_field = tk.Entry(
            input_frame,
            bg="#0d1220",
            fg="#f5f7ff",
            insertbackground="#f5f7ff",
            font=("Avenir Next", 11),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#3a4256",
            highlightcolor="#4c7dff",
        )
        self.input_field.insert(0, "Type a message or command")
        self.input_field.grid(row=0, column=0, sticky="ew", ipady=6)
        self.input_field.bind("<Return>", self._send_message)
        self.input_field.bind("<FocusIn>", self._clear_placeholder)
        self.input_field.focus_set()

        send_button = ttk.Button(
            input_frame,
            text="Send",
            command=self._send_message,
            style="ChitChat.TButton",
        )
        send_button.grid(row=0, column=1, padx=(10, 0), sticky="e")

        self.status_label = tk.Label(
            self,
            text="Disconnected",
            anchor="w",
            bg="#121621",
            fg="#9fb0dc",
            font=("Helvetica", 9),
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))

    def _clear_placeholder(self, event=None):
        if self.input_field.get() == "Type a message or command":
            self.input_field.delete(0, tk.END)

    def _set_weather_unit(self, unit_code, announce=False):
        normalized = str(unit_code).lower().strip()
        if normalized not in {"c", "f"}:
            normalized = "c"

        previous = self.weather_unit
        self.weather_unit = normalized
        if hasattr(self, "weather_unit_var"):
            self.weather_unit_var.set(
                "Fahrenheit (°F)" if self.weather_unit == "f" else "Celsius (°C)"
            )

        if announce and previous != self.weather_unit:
            unit_name = "Fahrenheit" if self.weather_unit == "f" else "Celsius"
            self._append_text(f"Weather unit set to {unit_name}\n")

    def _on_weather_unit_change(self, event=None):
        selected = self.weather_unit_var.get().lower()
        self._set_weather_unit("f" if "fahrenheit" in selected else "c", announce=True)

    def server_connection(self):
        ip = simpledialog.askstring(
            "Server IP", "Please enter a server IP.", parent=self, initialvalue="127.0.0.1"
        )
        if not ip:
            self.destroy()
            return

        name = simpledialog.askstring(
            "Nickname", "Please enter a nickname.", parent=self
        )
        if not name:
            self.destroy()
            return

        try:
            self.nickname = name.strip() or "Anonymous"
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, 1234))
            self.reader = self.socket.makefile(mode="r", buffering=1, encoding="utf-8")
            self.writer = self.socket.makefile(mode="w", buffering=1, encoding="utf-8")
            self.writer.write(json.dumps({"type": "hello", "name": self.nickname}) + "\n")
            self.writer.flush()
            self.status_label.configure(text=f"Connected as {self.nickname} to {ip}:1234")

            threading.Thread(target=self._receive_loop, daemon=True).start()
        except Exception as e:
            print(f"Failed to connect to server at {ip}:1234 - {e}")
            self.status_label.configure(text=f"Connection failed: {e}")
            self.destroy()

    def _receive_loop(self):
        reader = self.reader
        if reader is None:
            return

        try:
            for data in reader:
                payload = data.rstrip("\n")
                try:
                    message = json.loads(payload)
                except json.JSONDecodeError:
                    self.incoming.put({"type": "legacy", "text": payload})
                else:
                    self.incoming.put(message if isinstance(message, dict) else {"type": "legacy", "text": payload})
        except Exception as e:
            print(f"Error receiving messages from server: {e}")

    def _drain_incoming(self):
        while True:
            try:
                message = self.incoming.get_nowait()
            except queue.Empty:
                break
            self._handle_message(message)
        self.after(50, self._drain_incoming)

    def _handle_message(self, message):
        message_type = message.get("type")
        if message_type == "chat":
            sender = message.get("sender", "Unknown")
            text = message.get("text", "")
            tag_name = "self_bubble" if sender == self.nickname else "other_bubble"
            display_sender = "You" if sender == self.nickname else sender
            self._append_styled_block(f"{display_sender}: {text}\n", tag_name)
        elif message_type == "private":
            sender = message.get("sender", "Unknown")
            recipient = message.get("to", "")
            text = message.get("text", "")
            if sender == self.nickname:
                self._append_styled_block(f"You -> {recipient}: {text}\n", "self_bubble")
            else:
                self._append_styled_block(f"[Private] {sender} -> you: {text}\n", "other_bubble")
        elif message_type == "system":
            self._append_styled_block(f"{message.get('text', '')}\n", "system_line")
        elif message_type == "users":
            self._update_users(message.get("users", []))
        elif message_type == "image":
            self._append_image(
                sender=message.get("sender", "Unknown"),
                filename=message.get("filename", "image"),
                data=message.get("data", ""),
            )
        elif message_type == "legacy":
            self._append_styled_block(f"{message.get('text', '')}\n", "other_bubble")
        else:
            self._append_styled_block(f"{message}\n", "system_line")

    def _update_users(self, users):
        self.user_list.delete(0, tk.END)
        if not users:
            self.user_list.insert(tk.END, "No users online")
            return
        for user in users:
            self.user_list.insert(tk.END, user)

    def _configure_message_tags(self):
        self.text_area.tag_configure(
            "system_line",
            foreground="#9fb0dc",
            lmargin1=14,
            lmargin2=14,
            rmargin=14,
            spacing1=4,
            spacing3=6,
        )
        self.text_area.tag_configure(
            "other_bubble",
            background="#182033",
            foreground="#dbe6ff",
            lmargin1=14,
            lmargin2=14,
            rmargin=80,
            spacing1=6,
            spacing3=8,
        )
        self.text_area.tag_configure(
            "self_bubble",
            background="#20335f",
            foreground="#ffffff",
            justify="right",
            lmargin1=80,
            lmargin2=80,
            rmargin=14,
            spacing1=6,
            spacing3=8,
        )
        self.text_area.tag_configure(
            "caption_line",
            foreground="#a9b8e8",
            lmargin1=14,
            lmargin2=14,
            rmargin=14,
            spacing1=4,
            spacing3=2,
        )

    def _append_styled_block(self, text, tag_name):
        self.text_area.configure(state="normal")
        start_index = self.text_area.index(tk.END)
        self.text_area.insert(tk.END, text)
        end_index = self.text_area.index(tk.END)
        self.text_area.tag_add(tag_name, start_index, end_index)
        self.text_area.see(tk.END)
        self.text_area.configure(state="disabled")

    def _append_text(self, text):
        self._append_styled_block(text, "system_line")

    def _append_image(self, sender, filename, data):
        try:
            photo = tk.PhotoImage(data=data)
        except tk.TclError:
            self._append_styled_block(
                f"[{sender}] shared image {filename} but Tk could not render it.\n",
                "caption_line",
            )
            return

        caption = f"[{sender}] shared image {filename}\n"
        self.text_area.configure(state="normal")
        caption_start = self.text_area.index(tk.END)
        self.text_area.insert(tk.END, caption)
        caption_end = self.text_area.index(tk.END)
        self.text_area.tag_add("caption_line", caption_start, caption_end)
        self.text_area.image_create(tk.END, image=photo)
        self.text_area.insert(tk.END, "\n")
        self.text_area.see(tk.END)
        self.text_area.configure(state="disabled")
        self.image_refs.append(photo)
        if len(self.image_refs) > 20:
            self.image_refs = self.image_refs[-20:]

    def _send_json(self, payload):
        writer = self.writer
        if writer is None:
            return
        try:
            writer.write(json.dumps(payload, ensure_ascii=False) + "\n")
            writer.flush()
        except Exception as e:
            print(f"Failed to send message to server: {e}")

    def _send_image(self, path):
        if not os.path.exists(path):
            messagebox.showerror("Image not found", f"Could not find: {path}")
            return

        mime_type, _ = mimetypes.guess_type(path)
        mime_type = mime_type or "image/png"
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")

        self._send_json(
            {
                "type": "image",
                "filename": os.path.basename(path),
                "mime": mime_type,
                "data": encoded,
            }
        )

    def _handle_command(self, data):
        parts = data.split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command == "/help":
            self._append_text(
                "Commands: /help, /users, /msg USER TEXT, /unit C|F, /weather CITY, /image PATH, /me ACTION\n"
            )
            return True

        if command == "/users":
            self._send_json({"type": "users"})
            return True

        if command == "/msg":
            if not argument or " " not in argument:
                self._append_text("Usage: /msg USERNAME MESSAGE\n")
                return True
            recipient, private_text = argument.split(maxsplit=1)
            self._send_json({"type": "private", "to": recipient, "text": private_text})
            return True

        if command == "/weather":
            if not argument:
                self._append_text("Usage: /weather CITY\n")
                return True
            self._send_json({"type": "weather", "location": argument, "unit": self.weather_unit})
            return True

        if command == "/unit":
            if not argument:
                current_label = "F" if self.weather_unit == "f" else "C"
                self._append_text(f"Current weather unit: {current_label}. Use /unit C or /unit F\n")
                return True

            selected = argument.lower()
            if selected in {"c", "celsius"}:
                self._set_weather_unit("c", announce=True)
            elif selected in {"f", "fahrenheit"}:
                self._set_weather_unit("f", announce=True)
            else:
                self._append_text("Usage: /unit C or /unit F\n")
            return True

        if command == "/image":
            if not argument:
                argument = filedialog.askopenfilename(
                    title="Choose an image",
                    filetypes=[
                        ("Image files", "*.png *.gif *.ppm *.pgm *.jpg *.jpeg"),
                        ("All files", "*.*"),
                    ],
                )
            if not argument:
                return True
            self._send_image(argument)
            return True

        if command == "/me":
            if argument:
                self._send_json({"type": "action", "text": argument})
            return True

        return False

    def _send_message(self, event=None):
        data = self.input_field.get()
        self.input_field.delete(0, tk.END)
        if not data or data == "Type a message or command":
            return

        if data.startswith("/") and self._handle_command(data):
            return

        self._send_json({"type": "chat", "text": data})

    def _on_close(self):
        reader = self.reader
        writer = self.writer
        socket_obj = self.socket
        if socket_obj:
            try:
                if reader:
                    reader.close()
                if writer:
                    writer.close()
                socket_obj.close()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = SocketClient()
    app.after(100, app.server_connection)
    app.mainloop()
