"""Record command output from a built guest, for use in documentation.

Runs a set of commands as a given account and stores their output for
rendering as screenshots or embedding in a walkthrough.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import paramiko

from .remote import run


@dataclass
class Shot:
    name: str
    command: str
    lines: list[str]


def capture(ssh: paramiko.SSHClient, spec: list[dict], timeout: float = 60) -> list[Shot]:
    """Run each command in `spec` and keep its output.

    Each spec entry is {"name", "command", optional "max_lines"}. Output
    longer than `max_lines` is tail-trimmed, which is what a terminal of
    that height would have shown anyway.
    """
    shots: list[Shot] = []
    for entry in spec:
        result = run(ssh, entry["command"], timeout=timeout)
        lines = [l.rstrip() for l in result.out.rstrip("\n").split("\n")]
        limit = entry.get("max_lines")
        if limit and len(lines) > limit:
            lines = lines[-limit:]
        shots.append(Shot(entry["name"], entry["command"], lines))
    return shots


def save(shots: list[Shot], path: Path) -> Path:
    path.write_text(json.dumps([asdict(s) for s in shots], indent=1))
    return path


def load(path: Path) -> list[Shot]:
    return [Shot(**d) for d in json.loads(Path(path).read_text())]
