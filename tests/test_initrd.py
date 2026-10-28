import gzip
import unittest
from zero3_usb_boot.initrd import member, entries, console_overlay

def archive(values):
    result = b"".join(member(name, 0o100755, data, i+1) for i, (name, data) in enumerate(values)) + member("TRAILER!!!", 0, b"", 99)
    return result + bytes((-len(result)) % 512)

class InitrdTests(unittest.TestCase):
    def test_raw(self):self.assertEqual(list(entries(archive([("init", b"test")])))[0][2], b"test")
    def test_gzip_concatenation(self):
        blob = gzip.compress(archive([("a", b"first")])) + gzip.compress(archive([("a", b"last")]))
        self.assertEqual([d for n, _, d in entries(blob)], [b"first", b"last"])
    def test_dracut_unchanged(self):
        blob = gzip.compress(archive([("init", b"native"), ("usr/lib/dracut/modules.txt", b"base")]))
        self.assertEqual(console_overlay(blob), (blob, "dracut-preserved"))
    def test_uart_overlay_and_idempotence(self):
        blob = gzip.compress(archive([("init", b"#!/bin/sh\nrun_scripts /scripts/init-top\n"), ("scripts/functions", b"functions")]))
        result, mode = console_overlay(blob)
        self.assertEqual(mode, "initramfs-tools-uart-overlay")
        self.assertTrue(result.startswith(blob))
        self.assertIn(b"/dev/ttyS0", [d for n, _, d in entries(result) if n == "init"][-1])
        self.assertEqual(console_overlay(result), (result, "already-patched"))
    def test_unknown_framework_rejected(self):
        with self.assertRaises(ValueError):console_overlay(archive([("init", b"native")]))
    def test_truncated_cpio_rejected(self):
        for blob in [b"070701", archive([("init", b"test")])[:115], b"not cpio"]:
            with self.assertRaises(ValueError):list(entries(blob))

if __name__ == "__main__":unittest.main()
