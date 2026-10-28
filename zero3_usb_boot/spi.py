"""Make a local SPI backup/plan; commit only the exact verified plan."""
import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from .boot import sha256

def validate_image(image, expected):
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected) or sha256(image) != expected.lower():
        raise ValueError("Firmware SHA256 mismatch")
    if image[4:12] != b"eGON.BT0" or not 32768 <= len(image) <= 4 * 1024 * 1024:
        raise ValueError("Not a plausible sunxi SPL + U-Boot image")

def verify_readback(before, after, image, erase_size):
    end = (len(image) + erase_size - 1) // erase_size * erase_size
    if len(after) != len(before) or after[:len(image)] != image or after[end:] != before[end:]:
        raise ValueError("SPI readback mismatch or unexpected changes beyond the erase range")
    return end

def geometry(device):
    if not re.fullmatch(r"/dev/mtd\d+", device):
        raise ValueError("Only an explicit /dev/mtdN character device is accepted")
    model = Path("/proc/device-tree/model").read_text().rstrip("\0")
    if "OrangePi Zero3" not in model and "Orange Pi Zero 3" not in model:
        raise ValueError("Board model is not Orange Pi Zero 3")
    sys = Path("/sys/class/mtd") / Path(device).name
    values = {name: int((sys / name).read_text()) for name in ["size", "erasesize"]}
    name = (sys / "name").read_text().strip()
    if values["size"] != 16 * 1024 * 1024 or values["erasesize"] != 4096 or name != "spi0.0":
        raise ValueError("Untested SPI geometry/name; do not bypass these checks")
    return {**values, "name": name, "model": model}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("--device", default="/dev/mtd0")
    plan_parser.add_argument("--image", type=Path, required=True)
    plan_parser.add_argument("--sha256", required=True)
    plan_parser.add_argument("--output", type=Path, required=True, help="New local-only directory")
    commit_parser = commands.add_parser("commit")
    commit_parser.add_argument("--plan", type=Path, required=True)
    commit_parser.add_argument("--confirm-original-sha256", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("SPI access requires root")
    if args.action == "plan":
        info = geometry(args.device)
        image = args.image.resolve().read_bytes()
        validate_image(image, args.sha256)
        if len(image) >= info["size"]:
            parser.error("Firmware exceeds flash")
        with open(args.device, "rb", buffering=0) as f:
            original = f.read(info["size"])
        if len(original) != info["size"]:
            raise ValueError("Could not read complete original flash")
        args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
        backup = args.output / "spi-original.bin"
        backup.write_bytes(original)
        backup.chmod(0o600)
        plan = {"device": args.device, "geometry": info, "image": str(args.image.resolve()),
                "image_sha256": sha256(image), "backup": str(backup.resolve()),
                "original_sha256": sha256(original)}
        target = args.output / "plan.json"
        target.write_text(json.dumps(plan, indent=2) + "\n")
        target.chmod(0o600)
        os.sync()
        print("Backup and plan saved locally. Copy the full backup to another computer before commit.")
        print("Original flash SHA256:", plan["original_sha256"])
        return
    plan = json.loads(args.plan.read_text())
    if args.confirm_original_sha256 != plan["original_sha256"]:
        parser.error("Confirmation does not match the saved original flash digest")
    info = geometry(plan["device"])
    if info != plan["geometry"]:
        raise ValueError("Board/flash geometry changed since planning")
    image = Path(plan["image"]).read_bytes()
    validate_image(image, plan["image_sha256"])
    before = Path(plan["backup"]).read_bytes()
    with open(plan["device"], "rb", buffering=0) as f:
        current = f.read(info["size"])
    if len(before) != info["size"] or sha256(before) != plan["original_sha256"] or current != before:
        raise ValueError("Backup corrupted or SPI changed since planning; no write performed")
    # flashcp must consume the exact bytes checked above, not a path which can change.
    with tempfile.TemporaryDirectory(prefix="zero3-verified-spi-") as directory:
        frozen = Path(directory) / "u-boot.bin"
        frozen.write_bytes(image)
        frozen.chmod(0o600)
        subprocess.run(["flashcp", "-v", str(frozen), plan["device"]], check=True)
    with open(plan["device"], "rb", buffering=0) as f:
        after = f.read(info["size"])
    end = verify_readback(before, after, image, info["erasesize"])
    result = {"verified": True, "image_sha256": sha256(image), "erased_end": end}
    args.plan.with_name("result.json").write_text(json.dumps(result, indent=2) + "\n")
    os.sync()
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
