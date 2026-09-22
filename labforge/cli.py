"""Command line entry point: python -m labforge <command> ...

Kept intentionally simple: this wraps the library functions in vm.py,
remote.py, capture.py, render.py and docs.py rather than adding its own
logic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import capture as capture_mod
from . import docs as docs_mod
from . import render as render_mod
from . import remote, vm

DEFAULT_ROOT = Path.home() / ".labforge"


def _guest(name: str, root: Path, port: int, user: str, password: str) -> vm.Guest:
    return vm.Guest(name=name, root=root / name, ssh_port=port, user=user, password=password)


def cmd_up(args: argparse.Namespace) -> int:
    guest = vm.up(args.name, args.root, ssh_port=args.port,
                   user=args.user, password=args.password, size=args.size)
    print(f"guest {guest.name} up: ssh {guest.user}@127.0.0.1 -p {guest.ssh_port}")
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    guest = _guest(args.name, args.root, args.port, args.user, args.password)
    vm.destroy(guest, keep_disk=args.keep_disk)
    print(f"guest {args.name} destroyed")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    guest = _guest(args.name, args.root, args.port, args.user, args.password)
    ssh = remote.connect(port=guest.ssh_port, user=guest.user, password=guest.password)
    try:
        remote.wait_for_cloud_init(ssh)
        script = Path(args.script).read_text()
        rc = remote.run_script(ssh, script)
    finally:
        ssh.close()
    return rc


def cmd_capture(args: argparse.Namespace) -> int:
    guest = _guest(args.name, args.root, args.port, args.ssh_user, args.password)
    ssh = remote.connect(port=guest.ssh_port, user=args.user, password=args.user_password)
    try:
        spec = json.loads(Path(args.spec).read_text())
        shots = capture_mod.capture(ssh, spec)
    finally:
        ssh.close()
    out = Path(args.out)
    capture_mod.save(shots, out)
    print(f"wrote {out} ({len(shots)} captures)")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    shots = capture_mod.load(Path(args.shots))
    paths = render_mod.render_all(shots, Path(args.out), user=args.user, host=args.host)
    for p in paths:
        print(f"wrote {p}")
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    out = docs_mod.to_pdf(Path(args.source), Path(args.out), title=args.title)
    print(f"wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="labforge")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help=f"working directory for guests (default: {DEFAULT_ROOT})")
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("up", help="create and boot a guest")
    up.add_argument("--name", required=True)
    up.add_argument("--port", type=int, default=2222)
    up.add_argument("--user", default="builder")
    up.add_argument("--password", default="builder")
    up.add_argument("--size", default="20G")
    up.set_defaults(func=cmd_up)

    down = sub.add_parser("down", help="destroy a guest")
    down.add_argument("--name", required=True)
    down.add_argument("--port", type=int, default=2222)
    down.add_argument("--user", default="builder")
    down.add_argument("--password", default="builder")
    down.add_argument("--keep-disk", action="store_true")
    down.set_defaults(func=cmd_down)

    run = sub.add_parser("run", help="run a script inside a guest")
    run.add_argument("--name", required=True)
    run.add_argument("--port", type=int, default=2222)
    run.add_argument("--user", default="builder")
    run.add_argument("--password", default="builder")
    run.add_argument("--script", required=True)
    run.set_defaults(func=cmd_run)

    cap = sub.add_parser("capture", help="capture command output from a guest")
    cap.add_argument("--name", required=True)
    cap.add_argument("--port", type=int, default=2222)
    cap.add_argument("--ssh-user", default="builder")
    cap.add_argument("--password", default="builder")
    cap.add_argument("--user", required=True, help="account to run captured commands as")
    cap.add_argument("--user-password", required=True)
    cap.add_argument("--spec", required=True, help="JSON list of {name, command, max_lines}")
    cap.add_argument("--out", default="shots.json")
    cap.set_defaults(func=cmd_capture)

    render = sub.add_parser("render", help="render captures as terminal PNGs")
    render.add_argument("--shots", required=True)
    render.add_argument("--out", required=True)
    render.add_argument("--user", default="analyst")
    render.add_argument("--host", default="target")
    render.set_defaults(func=cmd_render)

    pdf = sub.add_parser("pdf", help="render a Markdown document to PDF")
    pdf.add_argument("--source", required=True)
    pdf.add_argument("--out", required=True)
    pdf.add_argument("--title")
    pdf.set_defaults(func=cmd_pdf)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
