"""SSH execution helpers.

Handles waiting for a guest that is still booting, and bounding commands
that open an interactive shell with a hard timeout.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

import paramiko


@dataclass
class Result:
    stdout: str
    stderr: str
    rc: int

    @property
    def out(self) -> str:
        return (self.stdout + self.stderr).strip()


def connect(host: str = "127.0.0.1", port: int = 2222, user: str = "builder",
            password: str = "builder", retries: int = 60,
            delay: float = 5.0) -> paramiko.SSHClient:
    """Open an SSH session, retrying while the guest finishes booting."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    last: Exception | None = None
    for _ in range(retries):
        try:
            client.connect(host, port=port, username=user, password=password,
                           timeout=5, allow_agent=False, look_for_keys=False)
            return client
        except Exception as exc:  # noqa: BLE001 - any failure means "not up yet"
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"could not reach {user}@{host}:{port}: {last}")


def wait_for_cloud_init(ssh: paramiko.SSHClient) -> None:
    """Block until first-boot provisioning has finished."""
    run(ssh, "cloud-init status --wait", timeout=600)


def run(ssh: paramiko.SSHClient, command: str, timeout: float = 120,
        check: bool = False) -> Result:
    """Run one command.

    `timeout` is a hard cap. A command that opens an interactive shell
    (a setuid shell obtained during validation, for example) never sends
    EOF, so without the cap this blocks forever.
    """
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(command)

    out, err = b"", b""
    try:
        while True:
            if chan.recv_ready():
                out += chan.recv(65536)
            elif chan.recv_stderr_ready():
                err += chan.recv_stderr(65536)
            elif chan.exit_status_ready():
                while chan.recv_ready():
                    out += chan.recv(65536)
                while chan.recv_stderr_ready():
                    err += chan.recv_stderr(65536)
                break
            else:
                time.sleep(0.05)
    except Exception:  # noqa: BLE001 - timeout means we report what we have
        pass

    rc = chan.recv_exit_status() if chan.exit_status_ready() else -1
    chan.close()

    result = Result(out.decode(errors="replace"), err.decode(errors="replace"), rc)
    if check and rc != 0:
        raise RuntimeError(f"command failed (rc={rc}): {command}\n{result.out}")
    return result


def run_script(ssh: paramiko.SSHClient, script: str, stream: bool = True,
               timeout: float = 3600) -> int:
    """Pipe a shell script to the guest and stream its output.

    Used to execute a build guide exactly as written rather than
    approximately as remembered.
    """
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command("bash -s 2>&1")
    chan.sendall(script.encode())
    chan.shutdown_write()

    while True:
        if chan.recv_ready():
            chunk = chan.recv(65536).decode(errors="replace")
            if stream:
                sys.stdout.write(chunk)
                sys.stdout.flush()
        elif chan.exit_status_ready():
            break
        else:
            time.sleep(0.05)

    rc = chan.recv_exit_status()
    chan.close()
    return rc
