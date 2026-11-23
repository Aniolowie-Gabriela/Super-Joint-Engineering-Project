import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import ask
from paged_reader import read_sources


def source(name, text, **extra):
    return {
        "chunk_id": name, "title": name, "text": text, "game_version": "1.37.5.0",
        "source_type": "game_script", "source_path": f"common/{name}.txt", **extra,
    }


def decision(action, keep=(), gap="", query=""):
    return json.dumps({"keep": list(keep), "action": action, "gap": gap, "query": query})


def find_quote(prompt, text):
    return int(re.search(rf"(?m)^(\d+): {re.escape(text)}$", prompt)[1])


class PagedReaderTests(unittest.TestCase):
    def test_five_page_limit_and_query_provenance(self):
        first = [source(f"pierwszy_{i}", f"Pominięty tekst {i}") for i in range(12)]
        next_pool = [first[1], source("drugi", "Źródło drugiego zapytania")]
        seen_prompts = []
        reading = {}

        def choose(system, message):
            seen_prompts.append(message)
            if len(seen_prompts) == 1:
                return decision("search", gap="Brakuje efektu", query="reformulacja")
            keep = [find_quote(message, "Pominięty tekst 11")] if len(seen_prompts) == 5 else []
            return decision("next", keep=keep, gap="Brakuje zakresu")

        kept, _, final_gap = read_sources(
            "Pytanie", "pierwsze", {"pierwsze": first, "reformulacja": next_pool}.__getitem__,
            choose, 4096, 3600, reading,
        )

        self.assertEqual([len(page["items"]) for page in reading["pages"]], [3, 1, 3, 3, 3])
        self.assertEqual([page["query"] for page in reading["pages"]],
                         ["pierwsze", "reformulacja", "pierwsze", "pierwsze", "pierwsze"])
        self.assertNotIn("Pominięty tekst 1\n", seen_prompts[1])
        self.assertEqual(reading["stop"], "limit")
        self.assertEqual(kept[0]["chunk_id"], "pierwszy_11")
        self.assertEqual(final_gap, "Brakuje zakresu")

    def test_ask_keeps_raw_rule_and_personal_exception_across_queries(self):
        rule = source("reguła", "Wzbogacony kontekst", source_text="Reguła z danych gry.")
        skipped = source("boczny", "Nieprzydatny tekst.")
        exception = source("wyjątek", "Wyjątek z własnego poradnika.")
        exception.update(source_type="user_source", game_version=None)
        initial = "Jak działa reguła i jaki jest wyjątek?"
        reformulation = "named exception"
        personal_queries = []
        prompts = []

        def personal_search(query):
            personal_queries.append(query)
            return [exception] if query == reformulation else []

        def respond(host, port, payload):
            prompts.append(payload)
            user_message = payload["messages"][1]["content"]
            if len(prompts) == 1:
                reply = decision("search", [find_quote(user_message, rule["source_text"])],
                                 "Brakuje wyjątku", reformulation)
            elif len(prompts) == 2:
                self.assertIn("Reguła z danych gry.", user_message)
                self.assertNotIn("Nieprzydatny tekst.", user_message)
                reply = decision("ready", [find_quote(user_message, exception["text"])])
            else:
                self.assertIn("Reguła z danych gry.", user_message)
                self.assertIn("Wyjątek z własnego poradnika.", user_message)
                self.assertNotIn("Nieprzydatny tekst.", user_message)
                reply = "Reguła obowiązuje [1], w opisanej sytuacji działa wyjątek [2]."
            return 200, {"message": {"content": reply}, "done_reason": "stop"}

        trace = {}
        with patch.dict(os.environ, {"EU4_GPU_STRICT": "1", "EU4_LLM_BACKEND": "ollama"}), \
             patch.object(ask, "resolve_db_path", return_value=Path(__file__)), \
             patch.object(ask, "trade_question", return_value=None), \
             patch.object(ask, "guide_context", return_value=[]), \
             patch.object(ask, "context", side_effect=[[rule, skipped], [rule]]), \
             patch.object(ask, "_chat_request", side_effect=respond):
            result = ask.ask(initial, __file__, diagnostics=trace, personal_search=personal_search)

        self.assertEqual(personal_queries, [initial, reformulation])
        self.assertEqual([prompt["think"] for prompt in prompts], [False, False, True])
        self.assertTrue(all(prompt["options"]["draft_num_predict"] == 0 for prompt in prompts))
        self.assertNotIn("format", prompts[-1])
        self.assertEqual(result["sources"][0]["source_path"], rule["source_path"])
        passage = result["sources"][0]["passages"][0]
        self.assertEqual(rule["source_text"][passage["start"]:passage["end"]], passage["text"])
        self.assertEqual(trace["cited_numbers"], [1, 2])
        self.assertEqual(trace["reading"]["stop"], "ready")
        self.assertEqual([item["kept"] for item in trace["reading"]["pages"][0]["items"]], [True, False])

    def test_invalid_reader_output_cannot_become_evidence(self):
        for reply in ("wybierz numer 1", decision("ready", [999]), decision("ready")):
            with self.subTest(reply=reply):
                trace = {}
                with patch.object(ask, "completion", return_value=(reply, {})) as completion:
                    result = ask.ask("Pytanie", preferred_records=[source("a", "Treść")], diagnostics=trace)
                self.assertEqual(completion.call_count, 1)
                self.assertEqual(result["sources"], [])
                self.assertEqual(trace["reading"]["stop"], "invalid")

    def test_campaign_stops_at_a_single_question_without_evidence(self):
        trace = {}
        reply = decision("campaign", gap="Ile masz dukatów w skarbcu?")
        with patch.object(ask, "completion", return_value=(reply, {})) as completion:
            result = ask.ask("Czy mam na tę budowę?", preferred_records=[source("a", "Koszt")], diagnostics=trace)
        self.assertEqual(completion.call_count, 1)
        self.assertEqual(result["answer"], "Ile masz dukatów w skarbcu?")
        self.assertEqual(trace["reading"]["stop"], "campaign")


if __name__ == "__main__":
    unittest.main()
