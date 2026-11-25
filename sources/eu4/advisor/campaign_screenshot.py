"""A single window frame returned directly as MCP image content."""

import asyncio
import base64
from pathlib import Path
import subprocess
import sys

from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import CallToolResult, ImageContent


CAPTURE = Path(__file__).parent / "capture/bin/Release/net8.0-windows/Eu4Capture.exe"


def capture_frame(game_dir: Path | None) -> bytes:
    if sys.platform != "win32" or not game_dir:
        raise ToolError("Zrzut wymaga systemu Windows i wskazanej instalacji EU4.")
    if not CAPTURE.is_file():
        raise ToolError("Przygotuj narzędzie obrazu poleceniem dotnet build sources/eu4/advisor/capture -c Release.")
    try:
        result = subprocess.run(
            [CAPTURE, game_dir / "eu4.exe"], capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError("Windows nie zwrócił klatki EU4. Sprawdź okno gry i spróbuj ponownie.") from exc
    if result.returncode:
        raise ToolError(result.stderr.decode("utf-8", errors="replace").strip() or "Nie udało się odczytać okna EU4.")
    if not result.stdout.startswith(b"\xff\xd8") or not result.stdout.endswith(b"\xff\xd9"):
        raise ToolError("Windows zwrócił niepełny obraz EU4.")
    return result.stdout


def register_screenshot(server, world, annotations):
    @server.tool(annotations=annotations)
    async def eu4_ui_screenshot() -> CallToolResult:
        """Pobierz jedną aktualną klatkę okna EU4 jako obraz na prośbę gracza. Działa również po F9."""
        frame = await asyncio.to_thread(capture_frame, world.game_dir)
        return CallToolResult(content=[ImageContent(
            type="image", mime_type="image/jpeg", data=base64.b64encode(frame).decode("ascii"),
        )])
