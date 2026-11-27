"""Rozmowa głosowa z agentem ElevenLabs, który szuka źródeł EU4 na tym komputerze.

Agent (rozpoznawanie mowy, LLM, głos) działa w ElevenLabs. Gdy chce coś sprawdzić,
wywołuje narzędzie klienta search_eu4 albo read_eu4_record przez to samo połączenie
WebSocket, a ten program przeszukuje lokalną bazę. Nie trzeba wystawiać serwera do internetu.

Ustaw ELEVENLABS_AGENT_ID (i ELEVENLABS_API_KEY dla agenta prywatnego) w środowisku
albo w pliku .env w katalogu projektu.
"""

import argparse
import json
import os
from pathlib import Path
import queue
import signal
import ssl
import threading

from ask import prepared_db_path
from mcp_server import find_passages
from search import read_record

ROOT = Path(__file__).resolve().parents[3]
RATE = 16000  # ElevenLabs: 16-bitowe PCM mono 16 kHz w obie strony


def load_env_file(path):
    """Wczytaj proste wpisy KLUCZ=wartość z .env, nie nadpisując zmiennych środowiska."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def make_elevenlabs_client(api_key):
    from elevenlabs.client import ElevenLabs

    if os.name != "nt" or os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return ElevenLabs(api_key=api_key)

    import httpx

    http_client = httpx.Client(verify=ssl.create_default_context(), follow_redirects=True)
    return ElevenLabs(api_key=api_key, httpx_client=http_client)


def make_tools(db_path, ClientTools, report=print, on_tool=None):
    """on_tool(kind, text, payload) dostaje dokładnie to, co trafia do agenta (np. do historii)."""
    def search_eu4(params):
        query = str(params.get("query") or "")
        try:
            limit = min(max(int(params.get("limit") or 4), 1), 8)
        except (TypeError, ValueError):
            limit = 4
        passages = find_passages(db_path, query, limit)
        report(f"  [szukam: {query}]")
        for item in passages:
            report(f"    • {item.get('title', item['chunk_id'])}  ({item['chunk_id']})")
        payload = json.dumps(passages, ensure_ascii=False)
        if on_tool is not None:
            on_tool("search", query, payload)
        return payload

    def read_eu4_record(params):
        found = read_record(db_path, str(params.get("chunk_id") or ""))
        if found is None:
            raise ValueError("Nie ma takiego fragmentu.")
        report(f"  [czytam: {found.get('chunk_id')}]")
        payload = json.dumps(found, ensure_ascii=False)
        if on_tool is not None:
            on_tool("record", found.get("chunk_id", ""), payload)
        return payload

    tools = ClientTools()
    tools.register("search_eu4", search_eu4)
    tools.register("read_eu4_record", read_eu4_record)
    return tools


def make_audio(AudioInterface):
    import sounddevice

    class SoundDeviceAudio(AudioInterface):
        """Mikrofon i głośnik przez sounddevice (PortAudio jest w paczce na Windows i macOS)."""

        def start(self, input_callback):
            self.queue = queue.Queue()
            self.pending = b""
            self.flush = False
            self.input = sounddevice.RawInputStream(
                samplerate=RATE, channels=1, dtype="int16", blocksize=4000,
                callback=lambda data, frames, time, status: input_callback(bytes(data)),
            )
            self.output_stream = sounddevice.RawOutputStream(
                samplerate=RATE, channels=1, dtype="int16", blocksize=1000, callback=self._play,
            )
            self.output_stream.start()
            self.input.start()

        def stop(self):
            for stream in (self.input, self.output_stream):
                stream.stop()
                stream.close()

        def output(self, audio):
            self.queue.put(audio)

        def interrupt(self):
            # Użytkownik przerwał agenta: wyrzuć niewypowiedziany dźwięk.
            self.flush = True
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break

        def _play(self, outdata, frames, time, status):
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

    return SoundDeviceAudio()


def main():
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Porozmawiaj głosowo z agentem ElevenLabs o EU4.")
    parser.add_argument("--db", metavar="PLIK", help="ścieżka do bazy EU4 (albo EU4_RAG_DB)")
    parser.add_argument("--agent-id", default=os.environ.get("ELEVENLABS_AGENT_ID"),
                        help="identyfikator agenta (albo ELEVENLABS_AGENT_ID)")
    parser.add_argument("--text", action="store_true",
                        help="pisz zamiast mówić i czytaj odpowiedzi (bez mikrofonu i głośnika)")
    args = parser.parse_args()
    if not args.agent_id:
        parser.exit(2, "Ustaw ELEVENLABS_AGENT_ID w .env albo podaj --agent-id.\n")
    try:
        db_path = prepared_db_path(args.db)
    except FileNotFoundError as exc:
        parser.exit(2, f"{exc} Najpierw uruchom: python eu4.py setup --voice\n")

    if db_path.with_name("semantic").joinpath("manifest.json").is_file():
        try:
            import semantic  # noqa: F401  (ładuje biblioteki natywne przed wątkami)
        except ImportError:
            pass
    print("Ładuję indeks…", flush=True)
    find_passages(db_path, "kupcy", 1)  # pierwsze wyszukiwanie ładuje model; agent nie czeka

    try:
        from elevenlabs.conversational_ai.conversation import AudioInterface, ClientTools, Conversation
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        client = make_elevenlabs_client(api_key)
        audio = None if args.text else make_audio(AudioInterface)
    except ImportError as exc:
        parser.exit(2, f"Brakuje pakietu {exc.name}. Zainstaluj: pip install -r requirements-voice.txt\n")
    except OSError as exc:  # sounddevice bez PortAudio (Linux)
        parser.exit(2, f"{exc}\nNa Linuksie doinstaluj PortAudio, np. sudo apt install libportaudio2\n")

    answered = threading.Event()  # tryb tekstowy czeka na odpowiedź agenta przed kolejnym pytaniem

    def agent_said(text):
        print(f"Agent: {text}", flush=True)
        answered.set()

    def disconnected(details):
        if details.reason == "error":
            print(f"Rozłączono: {details.message or details.close_reason}", flush=True)
        answered.set()

    conversation = Conversation(
        client,
        args.agent_id,
        requires_auth=bool(api_key),
        audio_interface=audio,
        client_tools=make_tools(db_path, ClientTools),
        callback_user_transcript=lambda text: print(f"Ty: {text}", flush=True),
        callback_agent_response=agent_said,
        callback_disconnect=disconnected,
    )
    signal.signal(signal.SIGINT, lambda *_: conversation.end_session())
    conversation.start_session()
    if args.text:
        answered.wait(20)  # powitanie agenta oznacza gotowe połączenie
        print("Wpisz pytanie i naciśnij Enter. Pusty wiersz kończy rozmowę.", flush=True)
        try:
            while text := input("> ").strip():
                answered.clear()
                conversation.send_user_message(text)
                answered.wait(60)
        except (EOFError, RuntimeError):  # RuntimeError: połączenie już zamknięte
            pass
        conversation.end_session()
    else:
        print("Mów do mikrofonu (najlepiej w słuchawkach). Ctrl+C kończy rozmowę.", flush=True)
    conversation_id = conversation.wait_for_session_end()
    print(f"Koniec rozmowy {conversation_id or ''}".rstrip())


if __name__ == "__main__":
    main()
