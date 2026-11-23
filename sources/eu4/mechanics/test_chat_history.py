"""Sprawdzenie trwałości migawek i aktualności kontekstu rozmowy."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from chat_history import ChatConflict, ChatHistory
from user_sources import UserSources


class ChatHistoryTest(unittest.TestCase):
    def test_snapshot_survives_source_changes_and_stale_reply(self):
        with TemporaryDirectory() as folder:
            folder = Path(folder)
            history = ChatHistory(folder / "chats.sqlite3")
            sources = UserSources(folder / "user-sources.sqlite3")
            source_id = sources.save("Polska", "Pierwotny fragment.")["id"]
            chunk_id = f"user:{source_id}:1"
            snapshot = {**sources.record(chunk_id), "number": 1}
            reading = {"pages": [
                {"query": "Unia Polski", "items": [
                    {"chunk_id": chunk_id, "title": "Polska", "text": "Pierwotny fragment.",
                     "kept": True, "kept_text": "Pierwotny", "game_version": ""},
                    {"chunk_id": "trade:1", "title": "Handel", "text": "Kupcy kierują handlem.",
                     "kept": False, "game_version": "1.37"},
                ], "action": "search", "gap": "Warunki unii"},
                {"query": "Warunki unii Polski", "items": [], "action": "ready", "gap": ""},
            ], "stop": "ready"}

            chat_id, first_id = history.append(
                chat_id=None, expected_message_id=None, question="Pytanie o Polskę",
                answer="Zobacz opis [1].", sources=[snapshot],
                diagnostics={"sources": [snapshot], "cited_numbers": [1], "reading": reading},
            )
            _, second_id = history.append(
                chat_id=chat_id, expected_message_id=first_id, question="I co dalej?",
                answer="To zależy od kampanii.", sources=[], diagnostics={},
            )
            saved = ChatHistory(history.path).get(chat_id)
            first = saved["messages"][0]
            self.assertEqual(first["sources"][0]["text"], "Pierwotny fragment.")
            self.assertEqual(first["diagnostics"]["sources"], [snapshot])
            self.assertEqual(first["diagnostics"]["reading"], reading)
            self.assertEqual(saved["messages"][1]["diagnostics"], {})

            sources.save("Polska", "Nowy fragment.", source_id=source_id)
            self.assertEqual(sources.record(chunk_id)["text"], "Nowy fragment.")
            self.assertEqual(history.get(chat_id), saved)
            self.assertTrue(sources.delete(source_id))
            self.assertIsNone(sources.record(chunk_id))
            self.assertEqual(history.get(chat_id), saved)

            with self.assertRaises(ChatConflict):
                history.append(
                    chat_id=chat_id, expected_message_id=first_id, question="Pytanie ze starej karty",
                    answer="Spóźniona odpowiedź.", sources=[], diagnostics={},
                )
            self.assertEqual(history.get(chat_id), saved)
            self.assertEqual(history.last_message(chat_id)["id"], second_id)
