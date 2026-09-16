"""Markdown to print-quality PDF, with referenced images inlined.

Scoped to what a lab walkthrough actually uses: headings, paragraphs,
fenced code, lists, emphasis, inline code and images. A full Markdown
engine is not worth the dependency for that set.

Images are embedded as data URIs so the resulting PDF is self-contained
and the screenshot directory does not have to ship alongside it.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font: 11pt/1.55 "DejaVu Sans", Arial, sans-serif; color: #1a1a1a; }
h1 { font-size: 21pt; margin: 0 0 4pt; border-bottom: 2px solid #333; padding-bottom: 6pt; }
h2 { font-size: 14pt; margin: 20pt 0 6pt; color: #14304f; page-break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 5pt; color: #14304f; page-break-after: avoid; }
p { margin: 7pt 0; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9.5pt;
       background: #f0f0f0; padding: 1px 4px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #d8dde2; border-left: 3px solid #14304f;
      padding: 8pt 10pt; font-family: "DejaVu Sans Mono", monospace; font-size: 9pt;
      line-height: 1.45; white-space: pre-wrap; word-wrap: break-word;
      page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
ol, ul { margin: 7pt 0 7pt 18pt; }
li { margin: 3pt 0; }
.shot { margin: 9pt 0; page-break-inside: avoid; }
.shot img { width: 100%; border: 1px solid #c3c9d0; border-radius: 3px; display: block; }
.cap { font-size: 8pt; color: #5d6874; margin-top: 3pt; font-style: italic; }
strong { color: #000; }
"""

_BLOCK_START = r"^(#{1,4}\s|```|[-*]\s|\d+\.\s|!\[)"


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def _image(alt: str, rel: str, base: Path) -> str:
    path = (base / rel).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"document references a missing image: {rel}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    caption = f'<div class="cap">{html.escape(alt)}</div>' if alt else ""
    return (f'<div class="shot"><img src="data:{mime};base64,{data}" '
            f'alt="{html.escape(alt)}">{caption}</div>')


def to_html(markdown: str, base: Path) -> str:
    out: list[str] = []
    lines = markdown.splitlines()
    i = 0
    list_tag: str | None = None

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            close_list()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue

        if not line.strip():
            close_list()
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", line.strip())
        if image:
            close_list()
            out.append(_image(image.group(1), image.group(2), base))
            i += 1
            continue

        for pattern, tag in ((r"^(\d+)\.\s+(.*)$", "ol"), (r"^[-*]\s+(.*)$", "ul")):
            item = re.match(pattern, line)
            if not item:
                continue
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            parts = [item.groups()[-1]]
            i += 1
            while i < len(lines) and re.match(r"^\s{2,}\S", lines[i]):
                parts.append(lines[i].strip())
                i += 1
            out.append(f"<li>{_inline(' '.join(parts))}</li>")
            break
        else:
            close_list()
            para = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(_BLOCK_START, lines[i]):
                para.append(lines[i])
                i += 1
            out.append(f"<p>{_inline(' '.join(para))}</p>")

    close_list()
    return "\n".join(out)


def to_pdf(source: Path, out: Path, title: str | None = None) -> Path:
    """Render a Markdown file to PDF via headless Chrome."""
    chrome = (shutil.which("google-chrome") or shutil.which("chromium")
              or shutil.which("chromium-browser"))
    if not chrome:
        raise RuntimeError("chrome or chromium is required to render the PDF")

    source = Path(source)
    body = to_html(source.read_text(encoding="utf-8"), source.parent)
    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(title or source.stem)}</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "doc.html"
        src.write_text(page, encoding="utf-8")
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={td}/profile", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", src.as_uri()],
            check=True, capture_output=True)
    return out
