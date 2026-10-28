"""Download the pinned public package and extract only its verified U-Boot."""
import argparse
import io
import json
import tarfile
import urllib.request
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zero3_usb_boot.boot import sha256
from zero3_usb_boot.prepare import deb_payload

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/firmware"))
    args = parser.parse_args()
    metadata = json.loads((Path(__file__).resolve().parents[1] / "examples/validated-inputs.json").read_text())["uboot"]
    args.output.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(metadata["packageUrl"], timeout=60) as response:
        package = response.read(8 * 1024 * 1024 + 1)
    if sha256(package) != metadata["packageSha256"]:
        raise ValueError("Public package SHA256 mismatch; no firmware written")
    with deb_payload(package) as data, tarfile.open(fileobj=data, mode="r|*") as archive:
        for item in archive:
            if item.isfile() and item.name.endswith("/u-boot-sunxi-with-spl.bin"):
                image = archive.extractfile(item).read()
                if sha256(image) != metadata["imageSha256"] or len(image) != metadata["imageSize"]:
                    raise ValueError("U-Boot payload does not match the tested build")
                target = args.output / "u-boot-sunxi-with-spl.bin"
                with target.open("xb") as f:
                    f.write(image)
                print("Verified U-Boot saved:", target)
                return
    raise ValueError("No U-Boot payload found")

if __name__ == "__main__":
    main()
