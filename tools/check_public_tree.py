"""Fail on common deployment secrets and private artifacts; never echo values."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "api-key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal-windows-path": re.compile(rb"[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_.-]+"),
    "mac-address": re.compile(rb"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b"),
    "credential-literal": re.compile(rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
}
FORBIDDEN = {".bin", ".iso", ".img", ".deb", ".exe", ".pem", ".key", ".log", ".7z", ".squashfs"}
SKIP = {".git", ".venv", "__pycache__", "build", "dist", "local", "backups", "artifacts"}

def files():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode == 0 and result.stdout:
        return [ROOT / name.decode("utf-8") for name in result.stdout.split(b"\0") if name]
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(part in SKIP for part in p.relative_to(ROOT).parts)]

def main():
    failed = []
    candidates = files()
    for file in candidates:
        name = file.relative_to(ROOT).as_posix()
        if file.suffix.lower() in FORBIDDEN or file.name in (".env", "config.local.json"):
            failed.append((name, "private-or-binary-artifact"))
        if file.stat().st_size > 1024 * 1024:
            failed.append((name, "unexpected-large-file"))
            continue
        data = file.read_bytes()
        for rule, pattern in RULES.items():
            if pattern.search(data):
                failed.append((name, rule))
    if failed:
        for name, rule in failed:
            print(f"REJECT {name}: {rule}")
        return 1
    print(f"Public tree scan passed: {len(candidates)} files; no secret values printed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
