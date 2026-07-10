import unittest
import os
import shutil
import asyncio
import zipfile
from datetime import datetime, timedelta

from minto.protocol.varint import encode_varint, read_varint_from_buffer, read_varint
from minto.protocol.packet import create_packet, write_string, HandshakePacket, LoginStartPacket
from minto.protocol.favicon import generate_minto_favicon_b64
from minto.logger import MintoLogger
from minto.proxy import MinecraftProxyInstance


class TestVarInt(unittest.TestCase):
    def test_encode_decode(self):
        test_values = [0, 1, 127, 128, 255, 25565, -1, -2147483648, 2147483647]
        for val in test_values:
            encoded = encode_varint(val)
            decoded, size = read_varint_from_buffer(encoded, 0)
            self.assertEqual(decoded, val)
            self.assertEqual(size, len(encoded))


class TestPacket(unittest.TestCase):
    def test_create_packet(self):
        packet = create_packet(0x00, b"\x01\x02\x03")
        # Packet length (VarInt) + Packet ID (VarInt 0x00) + payload
        # 0x04 (total length), 0x00 (packet id), 0x01, 0x02, 0x03
        self.assertEqual(packet, b"\x04\x00\x01\x02\x03")

    def test_string_bounds_validation(self):
        from minto.protocol.packet import read_string
        # Let's create a string with an invalid/huge length (e.g., 500000) encoded as a VarInt
        # VarInt 500000 is 0xA0 0x86 0x1E
        huge_len_varint = b"\xA0\x86\x1E" + b"some arbitrary text"
        with self.assertRaises(ValueError) as context:
            read_string(huge_len_varint, 0)
        self.assertIn("exceeds safe limit of 32767", str(context.exception))

    def test_handshake_packet(self):
        handshake = HandshakePacket(protocol_version=763, server_address="localhost", server_port=25565, next_state=2)
        encoded = handshake.encode()

        # Read total packet length
        packet_len, bytes_read = read_varint_from_buffer(encoded, 0)
        # Read packet id
        packet_id, bytes_read2 = read_varint_from_buffer(encoded, bytes_read)
        self.assertEqual(packet_id, 0x00)

        payload = encoded[bytes_read + bytes_read2:]
        decoded = HandshakePacket.decode(payload)
        self.assertEqual(decoded.protocol_version, 763)
        self.assertEqual(decoded.server_address, "localhost")
        self.assertEqual(decoded.server_port, 25565)
        self.assertEqual(decoded.next_state, 2)


class TestFavicon(unittest.TestCase):
    def test_generate_favicon(self):
        b64 = generate_minto_favicon_b64()
        self.assertTrue(b64.startswith("data:image/png;base64,"))
        self.assertGreater(len(b64), 100)


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.test_log_dir = "test_logs"
        if os.path.exists(self.test_log_dir):
            shutil.rmtree(self.test_log_dir)

    def tearDown(self):
        if os.path.exists(self.test_log_dir):
            shutil.rmtree(self.test_log_dir)

    def test_logger_archiving(self):
        minto_logger = MintoLogger(log_dir=self.test_log_dir, level="INFO", console_out=False, file_out=True)
        logger = minto_logger.get_logger("TestLogger")
        logger.info("This is a test log message that should be archived.")

        # Check that latest.log was created and contains text
        latest_path = os.path.join(self.test_log_dir, "latest.log")
        self.assertTrue(os.path.exists(latest_path))
        self.assertGreater(os.path.getsize(latest_path), 0)

        # Trigger manual archiving of the log as if it was yesterday (e.g. "2026-07-10")
        minto_logger.archive_current_log("2026-07-10")

        # Verify that zipped archive exists
        zip_path = os.path.join(self.test_log_dir, "2026-07-10.zip")
        self.assertTrue(os.path.exists(zip_path))

        # Verify latest.log is empty now
        self.assertEqual(os.path.getsize(latest_path), 0)

        # Verify that zip file contains the original file with correct name
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("2026-07-10.log", namelist)
            content = zf.read("2026-07-10.log").decode("utf-8")
            self.assertIn("This is a test log message that should be archived.", content)


class TestProxyAccessControl(unittest.TestCase):
    def test_ip_access(self):
        service_cfg = {
            "Name": "test-service",
            "Listen": 25565,
            "TargetAddress": "localhost",
            "TargetPort": 25565,
            "IPAccess": {
                "Mode": "accept",
                "List": ["127.0.0.1", "192.168.1.1"]
            }
        }
        inst = MinecraftProxyInstance(service_cfg)
        self.assertTrue(inst.check_ip_access("127.0.0.1"))
        self.assertTrue(inst.check_ip_access("192.168.1.1"))
        self.assertFalse(inst.check_ip_access("10.0.0.1"))

    def test_name_access(self):
        service_cfg = {
            "Name": "test-service",
            "Listen": 25565,
            "TargetAddress": "localhost",
            "TargetPort": 25565,
            "Minecraft": {
                "NameAccess": {
                    "Mode": "deny",
                    "List": ["badplayer", "griefer"]
                }
            }
        }
        inst = MinecraftProxyInstance(service_cfg)
        self.assertTrue(inst.check_player_name_access("goodplayer"))
        self.assertFalse(inst.check_player_name_access("badplayer"))
        self.assertFalse(inst.check_player_name_access("griefer"))


if __name__ == "__main__":
    unittest.main()
