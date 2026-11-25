import struct
import tempfile
import unittest
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from map_neighbors import MapTopology, register_neighbors
from world import WorldSources


def _bitmap(rows):
    # Kod koloru RGB prowincji nr N to (N, 1, 0). Bitmapa zapisuje BGR.
    width = len(rows[0])
    padding = bytes((-width * 3) % 4)
    pixels = b"".join(b"".join(bytes((0, 1, index)) for index in row) + padding for row in reversed(rows))
    header = struct.pack("<2sI4xI", b"BM", 54 + len(pixels), 54)
    dib = struct.pack("<IiiHHII16x", 40, width, len(rows), 1, 24, 0, len(pixels))
    return header + dib + pixels


class MapNeighborsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "launcher-settings.json").write_text('{"gameId":"eu4","rawVersion":"v1.37.5.0"}', encoding="utf-8")
        self.map_dir = self.root / "map"
        self.map_dir.mkdir()
        (self.map_dir / "definition.csv").write_text(
            "province;red;green;blue;x;x\n"
            "1;1;1;0;Start;x\n2;2;1;0;Closed;x\n3;3;1;0;Coast;x\n"
            "4;4;1;0;Lake;x\n5;5;1;0;Wasteland;x\n6;1;1;0;RNW;x\n",
            encoding="utf-8",
        )
        (self.map_dir / "default.map").write_text(
            "sea_starts = { 3 # sea\n }\nlakes = { 4 }\nonly_used_for_random = { 6 }\n", encoding="utf-8",
        )
        (self.map_dir / "climate.txt").write_text("impassable = { 5 }\n", encoding="utf-8")
        (self.map_dir / "adjacencies.csv").write_text(
            "From;To;Type;Through;start_x;start_y;stop_x;stop_y;Comment\n"
            "2;1;impassable;-1;-1;-1;-1;-1;Block\n3;2;lake;4;-1;-1;-1;-1;Lake\n"
            "5;1;sea;3;-1;-1;-1;-1;Crossing\n-1;-1;;-1;-1;-1;-1;-1;\n",
            encoding="utf-8",
        )
        (self.map_dir / "provinces.bmp").write_bytes(_bitmap(((1, 2, 2), (3, 4, 5), (3, 4, 5))))
        self.world = WorldSources(self.root)

    async def test_tool_reports_edges_special_connections_and_exclusions(self):
        server = MCPServer("test-map")
        register_neighbors(server, self.world, None, ToolAnnotations(read_only_hint=True, destructive_hint=False))
        result = (await server.call_tool("eu4_map_neighbors", {"province_id": 1})).structured_content
        self.assertEqual(result["province"], {"province_id": 1, "name": "Start", "kind": "land"})
        self.assertEqual(result["neighbors"], [{"province_id": 3, "name": "Coast", "kind": "sea"}])
        self.assertEqual(result["special_connections"], [{
            "province_id": 5, "name": "Wasteland", "kind": "wasteland", "type": "sea",
            "through": {"province_id": 3, "name": "Coast", "kind": "sea"},
        }])
        self.assertEqual(result["blocked_connections"], [{
            "province_id": 2, "name": "Closed", "kind": "land", "type": "impassable", "through": None,
        }])
        # Prowincja 4 dotyka 1 wyłącznie narożnikiem. Krawędź 3–4 jest zwykłym stykiem.
        other = (await server.call_tool("eu4_map_neighbors", {"province_id": 3})).structured_content
        self.assertEqual([(row["province_id"], row["kind"]) for row in other["neighbors"]], [
            (1, "land"), (4, "lake"), (5, "wasteland"),
        ])
        self.assertEqual(other["special_connections"][0]["type"], "lake")
        rnw = (await server.call_tool("eu4_map_neighbors", {"province_id": 6})).structured_content
        self.assertEqual(rnw["error_code"], "province_not_on_map")

    def test_map_wraps_east_west_only(self):
        (self.map_dir / "provinces.bmp").write_bytes(_bitmap(((1, 4, 3), (4, 4, 4), (5, 4, 2))))
        topology = MapTopology(self.world)
        left = topology.neighbors(1)
        right = topology.neighbors(3)
        self.assertEqual([row["province_id"] for row in left["neighbors"]], [3, 4])
        self.assertEqual([row["province_id"] for row in right["neighbors"]], [1, 4])

    def test_linked_bitmap_is_unavailable(self):
        bitmap = self.map_dir / "provinces.bmp"
        other = self.root / "outside.bmp"
        bitmap.rename(other)
        try:
            bitmap.hardlink_to(other)
        except OSError as exc:
            self.skipTest(str(exc))
        result = MapTopology(self.world).neighbors(1)
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "map_unavailable")

    def test_truncated_bitmap_is_rejected(self):
        bitmap = self.map_dir / "provinces.bmp"
        bitmap.write_bytes(bitmap.read_bytes()[:-1])
        result = MapTopology(self.world).neighbors(1)
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "map_format_unsupported")
