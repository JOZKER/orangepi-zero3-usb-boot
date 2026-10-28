import gzip
import struct
import unittest
from zero3_usb_boot.boot import extract_image, make_script, read_script, boot_command

def image():
    data = bytearray(128)
    data[56:60] = b"ARM\x64"
    return bytes(data)

def efi(raw):
    payload = gzip.compress(raw)
    linux = bytes(4) + b"zimg" + struct.pack("<II", 16, len(payload)) + payload
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HH", data, 132, 0xAA64, 1)
    data[152:160] = b".linux\0\0"
    struct.pack_into("<IIII", data, 160, len(linux), 0, len(linux), 512)
    return bytes(data) + linux

class BootTests(unittest.TestCase):
    def test_script_roundtrip(self):
        command = boot_command("orangepi-zero3", "boot=local rootwait rw")
        self.assertEqual(read_script(make_script(command)), command)

    def test_deterministic_image(self):
        self.assertEqual(make_script("echo test\n"), make_script("echo test\n"))

    def test_header_crc_rejects_corruption(self):
        data = bytearray(make_script("echo test\n"));data[20] ^= 1
        with self.assertRaises(ValueError):read_script(bytes(data))

    def test_payload_crc_rejects_corruption(self):
        data = bytearray(make_script("echo test\n"));data[-1] ^= 1
        with self.assertRaises(ValueError):read_script(bytes(data))

    def test_truncated_script(self):
        with self.assertRaises(ValueError):read_script(make_script("test")[:-1])

    def test_boot_injection_rejected(self):
        for relative in ["../private", "x;reset", "x\ny"]:
            with self.assertRaises(ValueError):boot_command(relative, "rootwait")
        with self.assertRaises(ValueError):boot_command("board", 'rootwait";reset')

    def test_raw_image(self):self.assertEqual(extract_image(image()), image())
    def test_efi_gzip(self):self.assertEqual(extract_image(efi(image())), image())
    def test_invalid_pe(self):
        for data in [b"", b"x"*128, efi(b"not arm64"), efi(image())[:180]]:
            with self.assertRaises(ValueError):extract_image(data)

if __name__ == "__main__":unittest.main()
