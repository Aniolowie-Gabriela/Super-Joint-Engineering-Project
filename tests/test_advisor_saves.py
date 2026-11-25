from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from zipfile import ZIP_DEFLATED, ZipFile

from sources.eu4.advisor.saves import SaveError, SaveProvider, _Text


class SaveProviderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.provider = SaveProvider([self.root])

    def save(self, name, body, *, mtime=10):
        path = self.root / name
        path.write_bytes(b"\nEU4txt\r\n" + body)
        os.utime(path, (mtime, mtime))
        return path

    def test_navigates_repeated_keys_mixed_lists_and_quoted_values(self):
        self.save(
            "fixture.eu4",
            b'date=1444.11.11 player="POL" # }\n'
            b'mod_data={ entry={ proper="\xc9t\xe9" } "a \\"b\\""'
            b' { test=4 } entry={ picture=rgb{4 5 6} test>=7 } }',
        )

        page = self.provider.read(["mod_data"], limit=2)
        first = page["items"][0]["selector"]
        second_page = self.provider.read(["mod_data"], offset=page["next_offset"], limit=2)
        last = second_page["items"][-1]["selector"]
        self.assertEqual(page["items"][1]["value"], 'a "b"')
        self.assertEqual(first, {"key": "entry", "occurrence": 0})
        self.assertEqual(last, {"key": "entry", "occurrence": 1})
        self.assertEqual(self.provider.read(["mod_data", first, "proper"])["value"], "Été")
        self.assertEqual(self.provider.read(["mod_data", 2, "test"])["value"], "4")
        self.assertEqual(self.provider.read(["mod_data", last, "picture", 2])["value"], "6")
        with self.assertRaisesRegex(SaveError, "Klucz się powtarza"):
            self.provider.read(["mod_data", "entry"])

        matches = self.provider.find("TEST", exact=True, limit=1)
        self.assertEqual(matches["next_offset"], 1)
        self.assertEqual(self.provider.read(matches["items"][0]["path"])["value"], "4")
        following = self.provider.find("TEST", exact=True, offset=1, limit=1)
        self.assertEqual(following["items"][0]["operator"], ">=")
        self.assertEqual(self.provider.read(following["items"][0]["path"])["value"], "7")

    def test_zip_lists_and_reads_all_eu4_sections(self):
        path = self.root / "archive.eu4"
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("meta", b'EU4txt\ndate=1500.2.3 player="FRA" campaign_id="a"')
            archive.writestr("gamestate", b'EU4txt\ncountries={ FRA={ treasury=42.250 } }')
            archive.writestr("ai", b'EU4txt\nmod_ai={ data=-5 }')
            archive.writestr("../escape", b"do not extract")

        info = self.provider.list_saves()["items"][0]
        self.assertEqual((info["game_date"], info["player"], info["campaign_id"]), ("1500.2.3", "FRA", "a"))
        self.assertEqual(self.provider.status()["format"], "zip-text")
        self.assertEqual(self.provider.read(["countries", "FRA", "treasury"])["value"], "42.250")
        self.assertEqual(self.provider.read(["mod_ai", "data"])["value"], "-5")
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_find_preserves_casefolded_unicode_and_literal_keys(self):
        self.save("fixture.eu4", 'arbitrary={ "Straße"=8 =="value" !question? =yes }'.encode())
        self.assertEqual(self.provider.find("STRASSE", exact=True)["items"][0]["value"], "8")
        self.assertEqual(self.provider.read(["arbitrary", "="])["value"], "value")
        self.assertEqual(self.provider.read(["arbitrary", "!question?"])["value"], "yes")

    def test_latest_complete_snapshot_and_active_campaign_selection(self):
        self.save("first.eu4", b'date=1500.2.3 player="FRA" campaign_id="a" value=1')
        newest = self.save("second.eu4", b'date=1500.3.3 player="FRA" campaign_id="a" value=2', mtime=20)
        self.assertEqual(self.provider.status(require_campaign=True)["selection"], "single_campaign")
        self.assertEqual(self.provider.read(["value"], require_campaign=True)["value"], "2")
        self.save("other.eu4", b'date=1500.4.3 player="ENG" campaign_id="b" value=3', mtime=30)
        self.assertEqual(self.provider.status(require_campaign=True)["error_code"], "selection_required")
        self.assertEqual(self.provider.read(["value"], campaign_id="a")["value"], "2")
        self.assertEqual(self.provider.read(["value"])["value"], "3")

        newest.write_bytes(b'EU4txt\ndate=1500.3.3 player="FRA" campaign_id="a" value={ ')
        os.utime(newest, (40, 40))
        self.assertEqual(self.provider.status("second.eu4")["error_code"], "invalid_save")
        fallback = self.provider.read(["value"], campaign_id="a")
        self.assertEqual(fallback["value"], "1")
        self.assertEqual(fallback["unreadable_newer_saves"], 1)

    def test_names_cannot_escape_roots_and_duplicates_need_root_index(self):
        duplicate = self.save("fixture.eu4", b"secret=first")
        other = self.root / "other"
        other.mkdir()
        (other / duplicate.name).write_bytes(b"EU4txt\nsecret=second")
        self.provider = SaveProvider([self.root, other])
        for name in ("../fixture.eu4", str(duplicate), "fixture.eu4:stream.eu4"):
            self.assertEqual(self.provider.status(name)["error_code"], "invalid_request")
        self.assertEqual(self.provider.status("fixture.eu4")["error_code"], "ambiguous_save")
        self.assertEqual(self.provider.read(["secret"], save="fixture.eu4", root_index=1)["value"], "second")

    def test_binary_snapshot_requires_local_converter(self):
        path = self.root / "binary.eu4"
        content = b"EU4bin\x12\xa0"
        path.write_bytes(content)
        self.assertEqual(self.provider.status()["error_code"], "converter_required")
        with self.assertRaisesRegex(SaveError, "Rakaly"):
            self.provider.read()
        self.assertEqual(path.read_bytes(), content)

    def test_deflated_binary_archive_keeps_the_original_fast_path(self):
        path = self.root / "legacy.eu4"
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            for name in ("meta", "gamestate", "ai"):
                archive.writestr(name, b"EU4bin\x12\xa0")
        with patch.object(self.provider, "_melt", return_value=_Text(b"EU4txt\nplayer=FRA")) as melt:
            self.assertEqual(self.provider.status()["player"], "FRA")
        melt.assert_called_once_with(path.read_bytes())

    @unittest.skipUnless(hasattr(zipfile, "ZIP_ZSTANDARD"), "Wymaga obsługi Zstandard w zipfile")
    def test_zstandard_binary_archive_lists_metadata_and_repacks_only_eu4_sections(self):
        path = self.root / "modern.eu4"
        sections = {"meta": b"EU4binmeta", "gamestate": b"EU4bingame", "ai": b"EU4binai"}
        with ZipFile(path, "w", zipfile.ZIP_ZSTANDARD) as archive:
            for name, body in sections.items():
                archive.writestr(name, body)
            archive.writestr("../ignored", b"ignore")
        original = path.read_bytes()
        converter = self.root / "rakaly"
        converter.touch()
        self.provider = SaveProvider([self.root], converter)

        def melt(data, **limits):
            metadata = b'EU4txt\ndate=1537.7.20 player=LAN campaign_id="campaign"'
            if data == sections["meta"]:
                self.assertIn("max_bytes", limits)
                return _Text(metadata)
            with ZipFile(BytesIO(data)) as archive:
                self.assertEqual({item.compress_type for item in archive.infolist()}, {ZIP_DEFLATED})
                self.assertEqual({item.filename: archive.read(item) for item in archive.infolist()}, sections)
            return _Text(metadata + b" countries={ LAN={ capital=116 } }")

        with patch.object(self.provider, "_melt", side_effect=melt) as converter_call:
            listed = self.provider.list_saves()["items"][0]
            self.assertEqual((listed["game_date"], listed["player"], listed["campaign_id"]), ("1537.7.20", "LAN", "campaign"))
            country = self.provider.read(["countries", "LAN", "capital"], campaign_id="campaign")
            self.assertEqual((country["format"], country["value"]), ("zip-binary", "116"))
        self.assertEqual(converter_call.call_count, 2)
        self.assertEqual(path.read_bytes(), original)

    def test_cache_is_invalidated_when_size_or_mtime_changes(self):
        self.save("autosave.eu4", b"date=1460.1.1 value=1")
        self.assertEqual(self.provider.read(["value"])["value"], "1")
        self.save("autosave.eu4", b"date=1460.1.1 value=20")
        self.assertEqual(self.provider.read(["value"])["value"], "20")
        self.save("autosave.eu4", b"date=1460.1.1 value=30", mtime=20)
        self.assertEqual(self.provider.read(["value"])["value"], "30")


if __name__ == "__main__":
    unittest.main()
