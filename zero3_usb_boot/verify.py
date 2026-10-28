"""Read-only, identity-minimized boot status report."""
import argparse
import json
import os
import subprocess
from pathlib import Path

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = json.loads(run("findmnt", "-J", "-o", "SOURCE,FSTYPE", "/"))["filesystems"][0]
    device = Path(root["source"].split("[")[0]).resolve().name
    subsystem = Path("/sys/class/block") / device
    usb = "usb" in str(subsystem.resolve()).lower()
    failed = run("systemctl", "--failed", "--no-legend", "--plain")
    result = {"board": Path("/proc/device-tree/model").read_text().rstrip("\0"),
              "kernel": os.uname().release, "cpuCount": os.cpu_count(),
              "rootFilesystem": root["fstype"], "rootBackedByUsb": usb,
              "bootPartitionMounted": os.path.ismount("/boot/firmware"),
              "sshActive": subprocess.run(["systemctl", "is-active", "--quiet", "ssh"]).returncode == 0,
              "failedUnitCount": len(failed.splitlines()) if failed else 0,
              "scope": "Current read-only status; does not itself prove a cold boot or SPI provenance"}
    value = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(value)
    print(value, end="")

if __name__ == "__main__":
    main()
