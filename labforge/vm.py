"""Disposable KVM guest lifecycle: base image, cloud-init seed, boot, destroy.

Guests are qcow2 overlays on a shared read-only base image.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_IMAGE_URL = (
    "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
)

CLOUD_CONFIG = """#cloud-config
hostname: {hostname}
ssh_pwauth: true
users:
  - name: {user}
    groups: [sudo]
    shell: /bin/bash
    lock_passwd: false
    plain_text_passwd: {password}
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]
package_update: true
"""


@dataclass
class Guest:
    """A disposable VM and the details needed to reach it."""

    name: str
    root: Path
    ssh_port: int
    user: str
    password: str

    @property
    def disk(self) -> Path:
        return self.root / "disk.qcow2"

    @property
    def seed(self) -> Path:
        return self.root / "seed.iso"

    @property
    def pidfile(self) -> Path:
        return self.root / "qemu.pid"

    @property
    def console(self) -> Path:
        return self.root / "console.log"

    def pid(self) -> int | None:
        try:
            pid = int(self.pidfile.read_text().strip())
        except (OSError, ValueError):
            return None
        return pid if _alive(pid) else None

    def is_running(self) -> bool:
        return self.pid() is not None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def fetch_base_image(dest: Path, url: str = DEFAULT_IMAGE_URL) -> Path:
    """Download the cloud image once, atomically.

    The download is staged to a temporary name and moved into place only on
    success. An overlay built on a half-downloaded base boots to an
    initramfs prompt with a "root filesystem not found" error rather than
    a clear download failure.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest

    staging = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, staging)
    _run(["qemu-img", "check", str(staging)])
    staging.replace(dest)
    return dest


def build_seed(guest: Guest, hostname: str | None = None) -> Path:
    """Generate a cloud-init NoCloud seed ISO for first boot."""
    work = guest.root
    work.mkdir(parents=True, exist_ok=True)

    (work / "user-data").write_text(
        CLOUD_CONFIG.format(
            hostname=hostname or guest.name,
            user=guest.user,
            password=guest.password,
        )
    )
    (work / "meta-data").write_text(
        f"instance-id: {guest.name}\nlocal-hostname: {hostname or guest.name}\n"
    )

    tool = shutil.which("genisoimage") or shutil.which("mkisofs")
    if not tool:
        raise RuntimeError("genisoimage or mkisofs is required to build the seed ISO")

    _run([tool, "-output", str(guest.seed), "-volid", "cidata",
          "-joliet", "-rock", str(work / "user-data"), str(work / "meta-data")])
    return guest.seed


def create_disk(guest: Guest, base: Path, size: str = "20G") -> Path:
    """Create the qcow2 overlay backed by the shared base image."""
    _run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2",
          "-b", str(base.resolve()), str(guest.disk), size])
    return guest.disk


def boot(guest: Guest, memory_mb: int = 3072, cpus: int = 4) -> int:
    """Start the guest headless and return its pid."""
    if guest.is_running():
        raise RuntimeError(f"guest {guest.name} is already running")

    cmd = [
        "qemu-system-x86_64",
        "-enable-kvm", "-cpu", "host",
        "-m", str(memory_mb), "-smp", str(cpus),
        "-drive", f"file={guest.disk},if=virtio,format=qcow2",
        "-drive", f"file={guest.seed},media=cdrom,format=raw",
        "-netdev", f"user,id=n0,hostfwd=tcp::{guest.ssh_port}-:22",
        "-device", "virtio-net-pci,netdev=n0",
        "-nographic",
        "-serial", f"file:{guest.console}",
        "-monitor", "none",
        "-pidfile", str(guest.pidfile),
    ]
    with open(guest.root / "qemu.log", "wb") as log:
        subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)

    for _ in range(50):
        if guest.pid():
            return guest.pid()
        time.sleep(0.2)
    raise RuntimeError(f"guest {guest.name} did not start; see {guest.root/'qemu.log'}")


def destroy(guest: Guest, keep_disk: bool = False) -> None:
    """Stop the guest and remove its overlay.

    Terminates by pid from the pidfile. Never pattern-match the process
    list to find it: a pattern broad enough to match the guest is also
    broad enough to match the shell that is doing the matching.
    """
    pid = guest.pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not _alive(pid):
                break
            time.sleep(0.1)
        else:
            os.kill(pid, signal.SIGKILL)

    guest.pidfile.unlink(missing_ok=True)
    if not keep_disk:
        guest.disk.unlink(missing_ok=True)


def up(name: str, root: Path, ssh_port: int = 2222, user: str = "builder",
       password: str = "builder", size: str = "20G",
       image_url: str = DEFAULT_IMAGE_URL) -> Guest:
    """Fetch the base image if needed, then create and boot a guest."""
    guest = Guest(name=name, root=root / name, ssh_port=ssh_port,
                  user=user, password=password)
    guest.root.mkdir(parents=True, exist_ok=True)

    base = fetch_base_image(root / "base.img", image_url)
    build_seed(guest)
    create_disk(guest, base, size=size)
    boot(guest)
    return guest
