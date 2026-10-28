import unittest
from zero3_usb_boot.boot import sha256
from zero3_usb_boot.spi import validate_image, verify_readback
from zero3_usb_boot.publish import root_uuid

class SpiTests(unittest.TestCase):
    def setUp(self):
        self.image = bytearray(40000);self.image[4:12] = b"eGON.BT0";self.image = bytes(self.image)
    def test_valid_firmware(self):validate_image(self.image, sha256(self.image))
    def test_bad_firmware_hash(self):
        with self.assertRaises(ValueError):validate_image(self.image, "0"*64)
    def test_bad_magic(self):
        with self.assertRaises(ValueError):validate_image(bytes(40000), sha256(bytes(40000)))
    def test_readback_and_preserved_tail(self):
        before = b"x"*65536;end = 40960;after = self.image+b"\xff"*(end-len(self.image))+before[end:]
        self.assertEqual(verify_readback(before, after, self.image, 4096), end)
    def test_readback_corruption(self):
        before = b"x"*65536
        with self.assertRaises(ValueError):verify_readback(before, b"z"*65536, self.image, 4096)
    def test_changed_tail(self):
        before = b"x"*65536;after = self.image+b"\xff"*(65536-len(self.image))
        with self.assertRaises(ValueError):verify_readback(before, after, self.image, 4096)
    def test_uuid_validation(self):
        self.assertEqual(root_uuid("00000000-0000-0000-0000-000000000000"), "00000000-0000-0000-0000-000000000000")
        with self.assertRaises(ValueError):root_uuid('invalid";reset')

if __name__ == "__main__":unittest.main()
