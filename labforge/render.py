"""Render captured command output as terminal-style PNGs.

Uses headless Chrome as the rasteriser.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
from pathlib import Path

from .capture import Shot

WIDTH = 1100
LINE_HEIGHT = 21

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #12161c; font-family: "DejaVu Sans Mono", monospace; }
.win { width: %dpx; background: #12161c; }
.bar { background: #262d36; padding: 7px 12px; display: flex; align-items: center; gap: 7px; }
.dot { width: 11px; height: 11px; border-radius: 50%%; display: inline-block; }
.r { background: #ec6a5e; } .y { background: #f4bf4f; } .g { background: #61c554; }
.ttl { color: #9aa5b1; font-size: 12px; margin-left: 9px; }
.body { padding: 11px 14px 14px; font-size: 13.5px; line-height: %dpx; color: #d5dae1;
        white-space: pre; }
.prompt { color: #61c554; }
.host { color: #56a8f5; }
.cmd { color: #ffffff; }
.hl { color: #f4bf4f; font-weight: bold; }
""" % (WIDTH, LINE_HEIGHT)


def _chrome() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("chrome or chromium is required to render screenshots")


def _markup(line: str, highlight: list[str]) -> str:
    escaped = html.escape(line)
    for needle in highlight:
        if needle in line:
            esc = html.escape(needle)
            return escaped.replace(esc, f'<span class="hl">{esc}</span>')
    return escaped


def render(shot: Shot, out_dir: Path, user: str = "analyst",
           host: str = "target", highlight: list[str] | None = None) -> Path:
    """Draw one capture as a terminal window and return the PNG path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    highlight = highlight or []

    prompt = (f'<span class="prompt">{html.escape(user)}@</span>'
              f'<span class="host">{html.escape(host)}</span>'
              f'<span class="prompt">:~$</span> ')
    body = [prompt + f'<span class="cmd">{html.escape(shot.command)}</span>']
    body += [_markup(l, highlight) for l in shot.lines]
    body.append(prompt)

    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{CSS}</style></head><body><div class='win'>"
            f"<div class='bar'><span class='dot r'></span>"
            f"<span class='dot y'></span><span class='dot g'></span>"
            f"<span class='ttl'>{html.escape(user)}@{html.escape(host)}</span></div>"
            f"<div class='body'>{chr(10).join(body)}</div></div></body></html>")

    height = 34 + 25 + len(body) * LINE_HEIGHT + 14
    out = out_dir / f"{shot.name}.png"

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "shot.html"
        src.write_text(page, encoding="utf-8")
        subprocess.run(
            [_chrome(), "--headless", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={td}/profile", "--hide-scrollbars",
             f"--window-size={WIDTH},{height}",
             f"--screenshot={out}", src.as_uri()],
            check=True, capture_output=True)
    return out


def render_all(shots: list[Shot], out_dir: Path, **kwargs) -> list[Path]:
    return [render(shot, out_dir, **kwargs) for shot in shots]
