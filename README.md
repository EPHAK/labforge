# labforge

A harness for building and verifying vulnerable-VM security training labs
on disposable KVM guests.

It boots a throwaway VM from a cloud image, runs a build script inside it
over SSH, and supports verifying the result by executing the lab against a
real target rather than reviewing it statically.

## Scope

- Boot and destroy disposable Ubuntu guests (qcow2 overlay + cloud-init).
- Execute a build script in the guest and stream its output.
- Rebuild from a pristine image to check that a build guide is complete.
- Capture real command output from a built guest and render it as terminal
  screenshots and a PDF for lab documentation.

## Requirements

- KVM, `qemu-system-x86_64`, `qemu-img`
- `genisoimage` or `mkisofs`
- Python 3.9+, `paramiko`
- Chrome or Chromium (only for `render` and `pdf`)

## Usage

```bash
pip install -r requirements.txt

# Create and boot a guest; SSH is forwarded to localhost:2222
python -m labforge up --name demo

# Run a build script inside it
python -m labforge run --name demo --script build.sh

# Capture command output for documentation
python -m labforge capture --name demo --user analyst --spec shots.json

# Render captures as terminal PNGs
python -m labforge render --shots shots.json --out docs/shots

# Render a Markdown walkthrough to PDF, inlining referenced images
python -m labforge pdf --source walkthrough.md --out walkthrough.pdf

# Destroy the guest
python -m labforge down --name demo
```

## Layout

```
labforge/
  vm.py        guest lifecycle: base image, seed ISO, overlay, boot, destroy
  remote.py    SSH connection and command execution
  capture.py   record command output from a guest
  render.py    terminal-style PNGs from captured output
  docs.py      Markdown to PDF with images inlined
  cli.py       command line entry point
docs/
  failure-modes.md         environmental failures to test for
  validation-checklist.md  checks to run before publishing a lab
```

## Notes

**Overlays.** Guests are qcow2 overlays on a shared read-only base image.
Creating a guest costs a few hundred kilobytes; destroying one deletes the
overlay.

**Networking.** User-mode networking with a forwarded SSH port. No bridges
or host firewall changes.

**Process handling.** Guests are tracked by pidfile and terminated by pid.
Pattern-matching the process list to find them is avoided, since a pattern
that matches the guest can also match the shell issuing the command.

**Timeouts.** `remote.run` takes a hard timeout. Commands that open an
interactive shell never send EOF and would otherwise block indefinitely.

**Documentation assets.** Screenshots are generated from output captured on
a built guest, so they reflect what the machine produced.

## License

MIT. See [LICENSE](LICENSE).
