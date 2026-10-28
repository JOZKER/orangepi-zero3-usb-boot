"""Prepare files in an ordinary directory; never formats or writes raw disks."""
import argparse
import hashlib
import io
import json
import re
import shutil
import tarfile
from pathlib import Path
from .boot import extract_image, make_script, boot_command, sha256
from .initrd import console_overlay

def deb_payload(data):
    stream = io.BytesIO(data)
    if stream.read(8) != b"!<arch>\n":
        raise ValueError("Not a Debian ar package")
    while True:
        header = stream.read(60)
        if not header:
            break
        if len(header) != 60 or header[-2:] != b"`\n":
            raise ValueError("Invalid ar header")
        size = int(header[48:58])
        content = stream.read(size)
        if len(content) != size:
            raise ValueError("Truncated ar member")
        if size % 2:
            stream.read(1)
        if header[:16].decode().strip().rstrip("/").startswith("data.tar"):
            if content.startswith(b"\x28\xb5\x2f\xfd"):
                import zstandard
                return zstandard.ZstdDecompressor().stream_reader(io.BytesIO(content))
            return io.BytesIO(content)
    raise ValueError("No data.tar in Debian package")

def find_dtb(deb):
    with deb_payload(deb) as payload, tarfile.open(fileobj=payload, mode="r|*") as archive:
        for item in archive:
            if item.isfile() and item.name.endswith("/sun50i-h618-orangepi-zero3.dtb"):
                if item.size > 1024 * 1024:
                    raise ValueError("Unexpected DTB size")
                data = archive.extractfile(item).read()
                if data[:4] != b"\xd0\x0d\xfe\xed":
                    raise ValueError("Invalid device-tree magic")
                return data
    raise ValueError("Orange Pi Zero 3 DTB missing from kernel package")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--iso-sha256", required=True, help="Expected digest from your trusted source")
    parser.add_argument("--output", type=Path, required=True, help="New, empty staging directory")
    parser.add_argument("--kernel-package", help="Explicit ISO path if several generic kernels exist")
    parser.add_argument("--copy-iso", action="store_true")
    parser.add_argument("--console-fix", choices=["auto", "never"], default="auto")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", args.iso_sha256):
        parser.error("--iso-sha256 must contain exactly 64 hexadecimal digits")
    with args.iso.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != args.iso_sha256.lower():
            parser.error("ISO SHA256 mismatch")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Output must be empty; existing boot files are never overwritten")
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", args.iso.name):
        parser.error("Use an ASCII ISO filename without shell characters")
    if args.copy_iso and args.iso.stat().st_size >= 2**32:
        parser.error("ISO does not fit FAT32's individual file size limit")
    import pycdlib
    iso = pycdlib.PyCdlib()
    iso.open(str(args.iso))
    def read(name):
        out = io.BytesIO()
        iso.get_file_from_iso_fp(out, rr_path=name)
        return out.getvalue()
    try:
        kernel = read("/casper/vmlinuz")
        initrd = read("/casper/initrd")
        packages = []
        for folder, _, files in iso.walk(rr_path="/pool"):
            for name in files:
                if re.fullmatch(r"linux-modules-[0-9].*-generic_.*_arm64\.deb", name):
                    packages.append(folder.rstrip("/") + "/" + name)
        selected = args.kernel_package
        if selected is None:
            if len(packages) != 1:
                raise ValueError("Use --kernel-package to select one of: " + ", ".join(packages))
            selected = packages[0]
        dtb = find_dtb(read(selected))
    finally:
        iso.close()
    image = extract_image(kernel)
    mode = "unchanged"
    if args.console_fix == "auto":
        initrd, mode = console_overlay(initrd)
    board = args.output / "orangepi-zero3"
    board.mkdir(parents=True)
    for name, content in [("Image", image), ("initrd", initrd), ("zero3.dtb", dtb)]:
        (board / name).write_bytes(content)
    arguments = f"boot=casper iso-scan/filename=/{args.iso.name} console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x05000000 loglevel=6 panic=30"
    script = boot_command("orangepi-zero3", arguments)
    (args.output / "boot.cmd").write_text(script, encoding="ascii")
    (args.output / "boot.scr").write_bytes(make_script(script))
    if args.copy_iso:
        shutil.copyfile(args.iso, args.output / args.iso.name)
    report = {"isoName": args.iso.name, "isoSha256": args.iso_sha256.lower(),
              "kernelPackage": selected, "consoleFix": mode,
              "files": {p.relative_to(args.output).as_posix(): sha256(p.read_bytes())
                        for p in [board / "Image", board / "initrd", board / "zero3.dtb", args.output / "boot.scr"]}}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
