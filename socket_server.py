import json
import logging
import socket
import threading
from urllib.parse import quote
from urllib.request import urlopen


LOG_FILE = "chitchat_server.log"


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def encode_message(payload):
    return json.dumps(payload, ensure_ascii=False)


def decode_message(raw_text):
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text
    return parsed if isinstance(parsed, dict) else raw_text


class ServerThread(threading.Thread):
    def __init__(self, server, client_socket):
        super().__init__(daemon=True)
        self.server = server
        self.client_socket = client_socket
        self.name_label = None
        self.reader = client_socket.makefile(mode="r", buffering=1, encoding="utf-8")
        self.writer = client_socket.makefile(mode="w", buffering=1, encoding="utf-8")

    def send(self, message):
        if isinstance(message, dict):
            message = encode_message(message)
        self.writer.write(message + "\n")
        self.writer.flush()

    def _handle_request(self, payload):
        message_type = payload.get("type")
        if message_type == "chat":
            text = payload.get("text", "")
            if text:
                self.server.broadcast(
                    {
                        "type": "chat",
                        "sender": self.name_label,
                        "text": text,
                    }
                )
                logging.info("message from %s: %s", self.name_label, text)
        elif message_type == "private":
            recipient = payload.get("to", "").strip()
            text = payload.get("text", "").strip()
            if not recipient or not text:
                self.send(
                    {
                        "type": "system",
                        "sender": "Server",
                        "text": "Usage: /msg USERNAME MESSAGE",
                    }
                )
                return

            target_thread = self.server.find_thread_by_name(recipient)
            if target_thread is None:
                self.send(
                    {
                        "type": "system",
                        "sender": "Server",
                        "text": f"User '{recipient}' is not online.",
                    }
                )
                return

            private_payload = {
                "type": "private",
                "sender": self.name_label,
                "to": target_thread.name_label,
                "text": text,
            }
            target_thread.send(private_payload)
            if target_thread is not self:
                self.send(private_payload)
            logging.info("private message from %s to %s: %s", self.name_label, recipient, text)
        elif message_type == "users":
            self.send({"type": "users", "users": self.server.list_users()})
        elif message_type == "weather":
            location = payload.get("location", "")
            unit = payload.get("unit", "c")
            if location:
                reply = self.server.fetch_weather(location, unit)
                self.server.broadcast(
                    {
                        "type": "system",
                        "sender": "WeatherBot",
                        "text": reply,
                    }
                )
                logging.info("weather request from %s for %s in unit %s", self.name_label, location, unit)
        elif message_type == "image":
            filename = payload.get("filename", "image")
            data = payload.get("data", "")
            mime_type = payload.get("mime", "image/png")
            if data:
                self.server.broadcast(
                    {
                        "type": "image",
                        "sender": self.name_label,
                        "filename": filename,
                        "mime": mime_type,
                        "data": data,
                    }
                )
                logging.info("image from %s: %s", self.name_label, filename)
        elif message_type == "action":
            text = payload.get("text", "")
            if text:
                self.server.broadcast(
                    {
                        "type": "system",
                        "sender": self.name_label,
                        "text": f"* {self.name_label} {text}",
                    }
                )
        else:
            self.server.broadcast(
                {
                    "type": "system",
                    "sender": "Server",
                    "text": f"Unsupported command from {self.name_label}",
                }
            )

    def run(self):
        try:
            hello_line = self.reader.readline().strip()
            hello = decode_message(hello_line)
            if isinstance(hello, dict) and hello.get("type") == "hello":
                self.name_label = hello.get("name", "Anonymous").strip() or "Anonymous"
            else:
                self.name_label = hello_line or "Anonymous"

            self.server.register_name(self, self.name_label)
            logging.info("connect %s from %s", self.name_label, self.client_socket.getpeername())
            self.server.broadcast(
                {
                    "type": "system",
                    "sender": "Server",
                    "text": f"**[{self.name_label}] Entered**",
                }
            )
            self.server.broadcast_users()

            for data in self.reader:
                data = data.strip()
                if not data:
                    continue

                payload = decode_message(data)
                if isinstance(payload, dict):
                    self._handle_request(payload)
                else:
                    self.server.broadcast(f"[{self.name_label}] {data}")
                    logging.info("legacy message from %s: %s", self.name_label, data)
        except Exception as e:
            logging.exception("Error handling client communication: %s", e)
        finally:
            self.server.remove_thread(self)
            self.server.broadcast(
                {
                    "type": "system",
                    "sender": "Server",
                    "text": f"**[{self.name_label}] Left**",
                }
            )
            self.server.broadcast_users()
            try:
                logging.info("disconnect %s from %s", self.name_label, self.client_socket.getpeername())
            except OSError:
                logging.info("disconnect %s", self.name_label)
            try:
                self.reader.close()
                self.writer.close()
                self.client_socket.close()
            except Exception:
                pass


class SocketServer:
    def __init__(self, host="127.0.0.1", port=1234):
        self.host = host
        self.port = port
        self.clients = []
        self.client_names = {}
        self.lock = threading.Lock()

    def add_thread(self, thread):
        with self.lock:
            self.clients.append(thread)

    def remove_thread(self, thread):
        with self.lock:
            if thread in self.clients:
                self.clients.remove(thread)
            self.client_names.pop(thread, None)

    def register_name(self, thread, name):
        with self.lock:
            self.client_names[thread] = name

    def list_users(self):
        with self.lock:
            return [name for name in self.client_names.values() if name]

    def find_thread_by_name(self, name):
        lowered_name = name.lower()
        with self.lock:
            for thread, stored_name in self.client_names.items():
                if stored_name and stored_name.lower() == lowered_name:
                    return thread
        return None

    def broadcast_users(self):
        self.broadcast({"type": "users", "users": self.list_users()})

    def broadcast(self, message):
        if isinstance(message, dict):
            logging.info("broadcast: %s", message.get("text", message.get("type", "message")))
            payload = encode_message(message)
        else:
            logging.info("broadcast: %s", message)
            payload = message

        with self.lock:
            for client in self.clients:
                try:
                    client.send(payload)
                except Exception as exc:
                    logging.warning("broadcast failure: %s", exc)

    def fetch_weather(self, location, unit="c"):
        unit = str(unit).lower().strip()
        if unit not in {"c", "f"}:
            unit = "c"

        encoded_location = quote(location)
        url = f"https://wttr.in/{encoded_location}?format=j1"
        try:
            with urlopen(url, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))

            current = payload["current_condition"][0]
            description = current["weatherDesc"][0]["value"]
            if unit == "f":
                temp_value = current["temp_F"]
                feels_like = current["FeelsLikeF"]
                unit_label = "F"
            else:
                temp_value = current["temp_C"]
                feels_like = current["FeelsLikeC"]
                unit_label = "C"

            humidity = current["humidity"]
            wind_kph = current["windspeedKmph"]
            return (
                f"Weather for {location}: {description}, {temp_value}°{unit_label}"
                f" (feels like {feels_like}°{unit_label}, humidity {humidity}%, wind {wind_kph} km/h)"
            )
        except Exception as exc:
            logging.warning("weather lookup failed for %s: %s", location, exc)
            return f"WeatherBot could not fetch weather for {location}."

    def serve(self):
        configure_logging()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(50)
            logging.info("waiting for client connection on %s:%s", self.host, self.port)

            while True:
                client_socket, addr = server_socket.accept()
                logging.info("accepted connection from %s", addr)

                thread = ServerThread(self, client_socket)
                self.add_thread(thread)
                thread.start()


if __name__ == "__main__":
    SocketServer().serve()
