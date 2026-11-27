"""Asystent EU4 w tle (przede wszystkim Windows): przytrzymaj skrót, mów, puść — agent odpowiada.

Ikona w zasobniku pokazuje stan. Połączenie z agentem ElevenLabs powstaje przy pierwszym
naciśnięciu skrótu i kończy się po minucie bezczynności, bo ElevenLabs liczy minuty
połączenia. Mikrofon trafia do agenta tylko podczas trzymania skrótu; poza tym idzie cisza.
Źródła EU4 są szukane lokalnie, jak w voice.py. Pytania, odpowiedzi, źródła wysłane agentowi
i ostrzeżenia trafiają do .eu4/history.sqlite; okno historii otwiera się z ikony. Konfiguracja w .env:
ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID i opcjonalnie EU4_VOICE_HOTKEY (domyślnie <ctrl_r>).
"""

import argparse
from collections import deque
import logging
import os
import queue
import socket
import sys
import threading
import time

from ask import prepared_db_path
from history import History
from mcp_server import find_passages
from voice import RATE, ROOT, load_env_file, make_elevenlabs_client, make_tools

DEFAULT_HOTKEY = "<ctrl_r>"
IDLE_SECONDS = 60       # rozłącz po minucie bez mowy i odpowiedzi
MAX_HOLD_SECONDS = 120  # zabezpieczenie, gdy system zgubi puszczenie klawisza
LOCK_PORT = 47821       # druga kopia aplikacji nie wystartuje
BLOCK = 4000            # 250 ms dźwięku z mikrofonu
LOG_FILE = ROOT / ".eu4" / "voice-app.log"
HISTORY_FILE = ROOT / ".eu4" / "history.sqlite"
KEY_NAMES = {"ctrl_r": "Prawy Ctrl", "ctrl_l": "Lewy Ctrl", "ctrl": "Ctrl", "shift": "Shift",
             "shift_r": "Prawy Shift", "alt": "Alt", "alt_l": "Lewy Alt", "alt_r": "Prawy Alt",
             "alt_gr": "AltGr", "caps_lock": "Caps Lock", "scroll_lock": "Scroll Lock", "space": "Spacja"}
COLORS = {"idle": (128, 134, 140), "connecting": (230, 145, 40), "ready": (46, 150, 90),
          "listening": (210, 50, 50), "speaking": (60, 120, 220)}
STATUS = {"idle": "Gotowy", "connecting": "Łączę z agentem…", "ready": "Połączony",
          "listening": "Słucham…", "speaking": "Agent mówi"}

log = logging.getLogger("eu4-voice")


class HistoryLogHandler(logging.Handler):
    """Ostrzeżenia i błędy aplikacji trafiają też do historii, przy bieżącej rozmowie."""

    def __init__(self, history, session):
        super().__init__(logging.WARNING)
        self.history, self.session = history, session

    def emit(self, record):
        try:
            text = record.getMessage()
            if record.exc_info:
                text += "\n" + logging.Formatter().formatException(record.exc_info)
            self.history.add(self.session(), "log", text, {"level": record.levelname})
        except Exception:  # historia nie może zatrzymać aplikacji ani zapętlić logowania
            pass


def hotkey_label(spec):
    parts = spec.replace("<", "").replace(">", "").split("+")
    return "+".join(KEY_NAMES.get(part, part.upper()) for part in parts)


class HoldHotkey:
    """Wywołuje on_change(True/False), gdy cała kombinacja zostaje wciśnięta albo puszczona."""

    def __init__(self, spec, on_change):
        from pynput import keyboard

        self.keyboard = keyboard
        # HotKey.parse zwraca klawisze specjalne (np. <ctrl_r>) jako KeyCode; wracamy do Key.
        self.special = {}
        for key in keyboard.Key:
            vk = getattr(key.value, "vk", None)
            if vk is not None:
                self.special.setdefault(vk, key)
        aliases = {keyboard.Key.ctrl: {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
                   keyboard.Key.shift: {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
                   keyboard.Key.alt: {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}}
        self.combo = [aliases.get(key, {self.normalize(key)}) for key in keyboard.HotKey.parse(spec)]
        self.on_change = on_change
        self.pressed = set()
        self.active = False
        self.listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def normalize(self, key):
        if isinstance(key, self.keyboard.Key):
            return key
        vk = getattr(key, "vk", None)
        if vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):  # cyfry i litery na Windows
            return chr(vk).lower()
        if key.char and key.char.isprintable():
            return key.char.lower()
        return self.special.get(vk, vk)

    def _update(self):
        active = all(options & self.pressed for options in self.combo)
        if active != self.active:
            self.active = active
            self.on_change(active)

    def _press(self, key):
        self.pressed.add(self.normalize(key))
        self._update()

    def _release(self, key):
        self.pressed.discard(self.normalize(key))
        self._update()

    def reset(self):
        self.pressed.clear()
        self._update()


def make_audio_class(AudioInterface, sounddevice):
    class PushToTalkAudio(AudioInterface):
        """Mikrofon i głośnik otwarte przez cały czas działania aplikacji.

        Do agenta idzie dźwięk tylko podczas trzymania skrótu, poza tym cisza. Mowa sprzed
        zestawienia połączenia jest buforowana, więc pierwsze słowa nie przepadają.
        """

        def __init__(self):
            self.talking = False
            self.lock = threading.Lock()
            self.send = None
            self.before_connect = deque(maxlen=40)  # do 10 s mowy
            self.queue = queue.Queue()
            self.pending = b""
            self.flush = False
            self.mic = sounddevice.RawInputStream(samplerate=RATE, channels=1, dtype="int16",
                                                  blocksize=BLOCK, callback=self._mic)
            self.speaker = sounddevice.RawOutputStream(samplerate=RATE, channels=1, dtype="int16",
                                                       blocksize=1000, callback=self._play)
            self.mic.start()
            self.speaker.start()

        @property
        def speaking(self):
            return bool(self.pending) or not self.queue.empty()

        def _mic(self, data, frames, time_info, status):
            chunk = bytes(data) if self.talking else bytes(len(data))
            with self.lock:
                if self.send is None:
                    if self.talking:
                        self.before_connect.append(chunk)
                    return
                send = self.send
            send(chunk)

        def start(self, input_callback):
            with self.lock:
                for chunk in self.before_connect:
                    input_callback(chunk)
                self.before_connect.clear()
                self.send = input_callback

        def stop(self):
            with self.lock:
                self.send = None
            self.interrupt()

        def output(self, audio):
            self.queue.put(audio)

        def interrupt(self):
            self.flush = True
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break

        def _play(self, outdata, frames, time_info, status):
            if self.flush:
                self.pending, self.flush = b"", False
            need = len(outdata)
            while len(self.pending) < need:
                try:
                    self.pending += self.queue.get_nowait()
                except queue.Empty:
                    break
            chunk, self.pending = self.pending[:need], self.pending[need:]
            outdata[:len(chunk)] = chunk
            outdata[len(chunk):] = b"\x00" * (need - len(chunk))

        def close(self):
            for stream in (self.mic, self.speaker):
                stream.stop()
                stream.close()

    return PushToTalkAudio


class VoiceApp:
    def __init__(self, db_path, api_key, agent_id, hotkey, history):
        from elevenlabs.conversational_ai.conversation import (
            AudioInterface, ClientTools, Conversation, ConversationInitiationData)

        self.db_path = db_path
        self.history = history
        self.session_id = None
        self.agent_id = agent_id
        self.client = make_elevenlabs_client(api_key)
        self.Conversation, self.ClientTools = Conversation, ClientTools
        # Bez powitania przy każdym połączeniu: gracz zaczyna mówić od razu.
        self.initiation = ConversationInitiationData(conversation_config_override={"agent": {"first_message": ""}})
        self.hotkey_text = hotkey_label(hotkey)
        self.hotkey = HoldHotkey(hotkey, self.on_hotkey)  # najpierw skrót: błąd w .env widać od razu
        import sounddevice  # bez PortAudio rzuca OSError już przy imporcie

        self.audio = make_audio_class(AudioInterface, sounddevice)()
        self.lock = threading.Lock()
        self.talk_lock = threading.Lock()
        self.talk_sources = set()
        self.conversation = None
        self.connected = False
        self.pressed_at = None
        self.last_activity = time.monotonic()
        self.running = True
        self.icon = None
        self.window = None
        self.state = None
        from history_web import HistoryWindow

        self.window = HistoryWindow(history, db_path, self.status, log)

    # --- rozmowa ---------------------------------------------------------------------------
    def touch(self):
        self.last_activity = time.monotonic()

    def on_hotkey(self, active):
        self.set_talking("keyboard", active)

    def set_talking(self, source, active):
        with self.talk_lock:
            if active:
                self.talk_sources.add(source)
            else:
                self.talk_sources.discard(source)
            talking = bool(self.talk_sources)
            if talking == self.audio.talking:
                return
            self.touch()
            self.audio.talking = talking
            self.pressed_at = time.monotonic() if talking else None
            if talking:
                self.audio.interrupt()
                threading.Thread(target=self.ensure_connected, daemon=True).start()

    def ensure_connected(self):
        with self.lock:
            if self.conversation is not None or not self.running:
                return
            log.info("Łączę z agentem…")
            self.session_id = self.history.new_session()
            self.conversation = self.Conversation(
                self.client, self.agent_id,
                requires_auth=True,
                audio_interface=self.audio,
                config=self.initiation,
                client_tools=make_tools(self.db_path, self.ClientTools, report=log.info, on_tool=self.remember),
                callback_user_transcript=self.on_user,
                callback_agent_response=self.on_agent,
                callback_disconnect=self.on_disconnect,
            )
            try:
                self.conversation.start_session()
            except Exception:
                log.exception("Nie udało się połączyć z ElevenLabs")
                self.conversation = None
                self.show_error("Nie udało się połączyć z ElevenLabs. Spróbuj ponownie.")

    def remember(self, kind, text, data=None):
        try:
            self.history.add(self.session_id, kind, text, data)
        except Exception as error:
            log.warning("Nie zapisano w historii: %s", error)

    def on_user(self, text):
        self.touch()
        self.connected = True
        log.info("Ty: %s", text)
        if self.window is not None:
            self.window.post("user", text)
        self.remember("user", text)

    def on_agent(self, text):
        self.touch()
        self.connected = True
        log.info("Agent: %s", text)
        if self.window is not None:
            self.window.post("agent", text)
        self.remember("agent", text)

    def on_disconnect(self, details):
        with self.lock:
            self.conversation = None
            self.connected = False
        if details.reason == "error":
            log.warning("Rozłączono: %s", details.message or details.close_reason)
            self.show_error("Połączenie z agentem zostało przerwane. Spróbuj ponownie.")
        else:
            log.info("Rozłączono (%s)", details.reason)
        self.session_id = None  # późniejsze ostrzeżenia nie należą już do tej rozmowy

    def end_conversation(self):
        conversation = self.conversation
        if conversation is not None:
            conversation.end_session()

    # --- ikona i pętla stanu ----------------------------------------------------------------
    def status(self):
        state = self.state or "idle"
        return {"state": state, "label": STATUS[state], "hotkey": self.hotkey_text,
                "session_id": self.session_id}

    def current_state(self):
        if self.audio.talking:
            return "listening"
        if self.audio.speaking:
            return "speaking"
        if self.conversation is None:
            return "idle"
        return "ready" if self.audio.send is not None else "connecting"

    def watch(self):
        while self.running:
            now = time.monotonic()
            if self.pressed_at and now - self.pressed_at > MAX_HOLD_SECONDS:
                log.warning("Skrót trzymany zbyt długo, wyłączam mikrofon.")
                self.set_talking("button", False)
                self.hotkey.reset()
            if self.audio.speaking:
                self.touch()
            if (self.conversation is not None and not self.audio.talking
                    and now - self.last_activity > IDLE_SECONDS):
                log.info("Brak aktywności, kończę połączenie.")
                self.end_conversation()
            state = self.current_state()
            if state != self.state and self.icon is not None:
                self.state = state
                self.icon.icon = icon_image(state)
                self.icon.title = f"EU4 — {STATUS[state]} · przytrzymaj {self.hotkey_text}"
            time.sleep(0.2)

    def show_error(self, message):
        if self.window is not None:
            self.window.post("error", message)
        self.notify(message)

    def notify(self, message):
        try:
            if self.icon is not None:
                self.icon.notify(message, "Asystent EU4")
        except Exception:  # nie każdy system ma powiadomienia
            pass

    def quit(self, *_):
        log.info("Zamykam aplikację.")
        self.running = False
        self.end_conversation()
        self.hotkey.listener.stop()
        self.window.stop()
        self.audio.close()
        if self.icon is not None:
            self.icon.stop()

    def run(self, show_window=True):
        import pystray

        items = [
            pystray.MenuItem(lambda item: f"Stan: {STATUS[self.state or 'idle']}", None, enabled=False),
            pystray.MenuItem(f"Mów: przytrzymaj {self.hotkey_text}", None, enabled=False),
            pystray.MenuItem("Historia rozmów", self.window.open, default=True),
            pystray.MenuItem("Rozłącz teraz", lambda *_: self.end_conversation()),
            pystray.MenuItem("Zakończ", self.quit),
        ]
        icon = icon_image("idle")
        if sys.platform == "win32":
            from voice_window import VoiceWindow

            self.window = VoiceWindow(self, STATUS, COLORS, icon)
            items.insert(0, pystray.MenuItem("Otwórz okno", lambda *_: self.window.post("show"), default=True))
        self.icon = pystray.Icon("eu4-voice", icon, "Asystent EU4", pystray.Menu(*items))
        self.hotkey.listener.start()
        threading.Thread(target=self.watch, daemon=True).start()

        def ready(icon):
            icon.visible = True
            self.notify(f"Przytrzymaj {self.hotkey_text} i zadaj pytanie o EU4.")

        if self.window is None:
            self.icon.run(setup=ready)
        else:
            self.icon.run_detached(setup=ready)
            self.window.run(show_window)


def icon_image(state):
    from PIL import Image, ImageDraw

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, size - 2, size - 2), fill=COLORS[state])
    white = (255, 255, 255)
    draw.rounded_rectangle((24, 12, 40, 38), radius=8, fill=white)         # mikrofon
    draw.arc((17, 22, 47, 46), start=0, end=180, fill=white, width=4)       # uchwyt
    draw.line((32, 46, 32, 52), fill=white, width=4)
    draw.line((24, 52, 40, 52), fill=white, width=4)
    return image


def fatal(message):
    log.error(message)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Asystent EU4", 0x10)
    else:
        print(message, file=sys.stderr)
    raise SystemExit(1)


def main():
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Asystent EU4 w tle: przytrzymaj skrót i mów.")
    parser.add_argument("--db", metavar="PLIK", help="ścieżka do bazy EU4 (albo EU4_RAG_DB)")
    parser.add_argument("--hotkey", default=os.environ.get("EU4_VOICE_HOTKEY", DEFAULT_HOTKEY),
                        help="skrót w zapisie pynput, np. <ctrl_r>, <caps_lock>, <ctrl>+<alt>+v")
    parser.add_argument("--tray-only", action="store_true", help="uruchom z ukrytym oknem")
    args = parser.parse_args()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
    if sys.stdout is not None:  # pythonw nie ma konsoli
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=handlers)

    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        fatal("Asystent EU4 już działa. Otwórz jego okno z ikony w zasobniku systemowym.")

    api_key, agent_id = os.environ.get("ELEVENLABS_API_KEY"), os.environ.get("ELEVENLABS_AGENT_ID")
    if not api_key or not agent_id:
        fatal(f"Brakuje ELEVENLABS_API_KEY albo ELEVENLABS_AGENT_ID w {ROOT / '.env'}.")
    try:
        db_path = prepared_db_path(args.db)
    except FileNotFoundError as exc:
        fatal(f"{exc} Najpierw uruchom: python eu4.py setup --voice")
    if db_path.with_name("semantic").joinpath("manifest.json").is_file():
        try:
            import semantic  # noqa: F401  (ładuje biblioteki natywne przed wątkami)
        except ImportError:
            pass
    log.info("Ładuję indeks…")
    find_passages(db_path, "kupcy", 1)

    history = History(HISTORY_FILE)
    try:
        app = VoiceApp(db_path, api_key, agent_id, args.hotkey, history)
    except ImportError as exc:
        fatal(f"Brakuje pakietu {exc.name}. Uruchom: python eu4.py setup --voice")
    except ValueError as exc:
        fatal(f"Nieprawidłowy skrót {args.hotkey!r}: {exc}")
    except OSError as exc:
        fatal(f"Nie mogę otworzyć mikrofonu ani głośnika: {exc}")
    logging.getLogger().addHandler(HistoryLogHandler(history, lambda: app.session_id))
    log.info("Gotowe. Przytrzymaj %s i mów.", app.hotkey_text)
    app.run(show_window=not args.tray_only)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:  # pythonw: pokaż błąd zamiast cicho zniknąć
        logging.getLogger("eu4-voice").exception("Nieoczekiwany błąd")
        fatal(f"Nieoczekiwany błąd: {error}\nSzczegóły w {LOG_FILE}")
