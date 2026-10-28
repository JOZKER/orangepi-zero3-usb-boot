"""Publish an installed kernel to an already-mounted FAT32 boot partition."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from .boot import extract_image, make_script, boot_command, sha256
from .initrd import console_overlay

def root_uuid(value):
    return str(uuid.UUID(value))

def atomic_write(target, data):
    temporary = target.with_name(target.name + ".new")
    with temporary.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", default=os.uname().release if hasattr(os, "uname") else "")
    parser.add_argument("initrd", nargs="?", type=Path)
    parser.add_argument("--boot", type=Path, default=Path("/boot/firmware"))
    parser.add_argument("--kernel", type=Path)
    parser.add_argument("--dtb", type=Path)
    parser.add_argument("--root-uuid")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", args.version):
        parser.error("Invalid kernel version")
    if not os.path.ismount(args.boot):
        parser.error("Boot partition must be mounted; refusing to write into an ordinary directory")
    if not args.dry_run and os.geteuid() != 0:
        parser.error("Publishing on the board requires root")
    value = args.root_uuid
    if value is None:
        config = Path("/etc/zero3-boot.json")
        if config.exists():
            value = json.loads(config.read_text())["root_uuid"]
        else:
            value = subprocess.check_output(["findmnt", "-n", "-o", "UUID", "/"], text=True).strip()
    value = root_uuid(value)
    kernel = args.kernel or Path("/boot/vmlinuz-" + args.version)
    initrd = args.initrd or Path("/boot/initrd.img-" + args.version)
    dtb = args.dtb
    if dtb is None:
        candidates = [Path("/usr/lib/firmware") / args.version / "device-tree/allwinner/sun50i-h618-orangepi-zero3.dtb",
                      Path("/usr/lib/linux-image-" + args.version) / "allwinner/sun50i-h618-orangepi-zero3.dtb"]
        dtb = next((p for p in candidates if p.is_file()), None)
    if dtb is None:
        parser.error("Matching kernel DTB not found; provide --dtb explicitly")
    image = extract_image(kernel.read_bytes())
    ramdisk, mode = console_overlay(initrd.read_bytes())
    tree = dtb.read_bytes()
    if tree[:4] != b"\xd0\x0d\xfe\xed":
        parser.error("Invalid DTB")
    files = {"Image": image, "initrd": ramdisk, "zero3.dtb": tree}
    fingerprint = sha256(b"".join(files.values()))[:16]
    relative = f"orangepi-zero3/installed/{args.version}-{fingerprint}"
    arguments = f"boot=local root=UUID={value} rootfstype=ext4 rootwait rw console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x05000000 loglevel=6 panic=30"
    script = boot_command(relative, arguments)
    report = {"version": args.version, "destination": relative, "consoleFix": mode,
              "files": {name: sha256(content) for name, content in files.items()}, "dryRun": args.dry_run}
    if args.dry_run:
        print(json.dumps(report, indent=2))
        return
    destination = args.boot / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        for name, content in files.items():
            if (destination / name).read_bytes() != content:
                raise RuntimeError("Existing content-addressed boot generation is inconsistent")
    else:
        temporary = Path(tempfile.mkdtemp(prefix=".new-", dir=destination.parent))
        try:
            for name, content in files.items():
                atomic_write(temporary / name, content)
            atomic_write(temporary / "sha256.json", json.dumps(report["files"], indent=2).encode() + b"\n")
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    for name in ["boot.cmd", "boot.scr"]:
        source = args.boot / name
        backup = args.boot / name.replace("boot.", "boot.previous.")
        if source.exists() and not backup.exists():
            shutil.copyfile(source, backup)
    atomic_write(args.boot / "boot.cmd", script.encode("ascii"))
    atomic_write(args.boot / "boot.scr", make_script(script))
    os.sync()
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
