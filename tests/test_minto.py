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


import json

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


class MockMinecraftServer:
    def __init__(self, port, online_players=123, max_players=456):
        self.port = port
        self.online_players = online_players
        self.max_players = max_players
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", self.port)

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def handle(self, reader, writer):
        try:
            # Read handshake packet
            packet_len, _ = await read_varint(reader)
            await reader.readexactly(packet_len)

            # Read status request packet
            packet_len, _ = await read_varint(reader)
            await reader.readexactly(packet_len)

            # Send Status Response
            motd_obj = {
                "version": {"name": "Mock Server", "protocol": 763},
                "players": {"max": self.max_players, "online": self.online_players},
                "description": {"text": "Mock"}
            }
            motd_json = json.dumps(motd_obj).encode("utf-8")
            motd_payload = encode_varint(len(motd_json)) + motd_json
            response = create_packet(0x00, motd_payload)
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


class TestNewFeatures(unittest.TestCase):
    def test_default_players_and_user_specified(self):
        # 1. Test fallback to default 0/1005 when not specified
        config_no_specified = {
            "Name": "test",
            "Listen": 25565,
            "TargetAddress": "localhost",
            "TargetPort": 25565,
            "Minecraft": {
                "OnlineCount": {
                    "Online": -1,
                    "Max": 2026
                }
            }
        }
        inst = MinecraftProxyInstance(config_no_specified)
        self.assertEqual(inst.user_specified_online, None)
        self.assertEqual(inst.max_players, 2026)

        # 2. Test when both are not specified / missing
        config_missing = {
            "Name": "test2",
            "Listen": 25566,
            "TargetAddress": "localhost",
            "TargetPort": 25566,
            "Minecraft": {}
        }
        inst2 = MinecraftProxyInstance(config_missing)
        self.assertEqual(inst2.user_specified_online, None)
        self.assertEqual(inst2.user_specified_max, None)
        self.assertEqual(inst2.max_players, 1005)

        # 3. Test when both are specified
        config_both = {
            "Name": "test3",
            "Listen": 25567,
            "TargetAddress": "localhost",
            "TargetPort": 25567,
            "Minecraft": {
                "OnlineCount": {
                    "Online": 42,
                    "Max": 500
                }
            }
        }
        inst3 = MinecraftProxyInstance(config_both)
        self.assertEqual(inst3.user_specified_online, 42)
        self.assertEqual(inst3.user_specified_max, 500)
        self.assertEqual(inst3.max_players, 500)

    def test_integration_ping_and_players(self):
        asyncio.run(self.run_integration_test_ping_and_players())

    async def run_integration_test_ping_and_players(self):
        # Start mock backend server
        mock_server = MockMinecraftServer(25590, online_players=123, max_players=456)
        await mock_server.start()

        try:
            # Start Minto proxy instance with ShowSourcePlayers = True and EnablePingDelay = True
            service_cfg = {
                "Name": "MintoTest",
                "Listen": 25591,
                "TargetAddress": "127.0.0.1",
                "TargetPort": 25590,
                "Minecraft": {
                    "EnablePingDelay": True,
                    "OnlineCount": {
                        "ShowSourcePlayers": True
                    }
                }
            }
            proxy = MinecraftProxyInstance(service_cfg)
            await proxy.start()

            try:
                # Connect as a client to the proxy
                client_reader, client_writer = await asyncio.open_connection("127.0.0.1", 25591)

                try:
                    # Send Handshake packet
                    handshake = HandshakePacket(protocol_version=763, server_address="127.0.0.1", server_port=25591, next_state=1)
                    client_writer.write(handshake.encode())

                    # Send Status Request
                    client_writer.write(create_packet(0x00, b""))
                    await client_writer.drain()

                    # Read Status Response
                    packet_len, _ = await read_varint(client_reader)
                    packet_id, _ = await read_varint(client_reader)
                    self.assertEqual(packet_id, 0x00)

                    payload_len = packet_len - 1
                    payload = await client_reader.readexactly(payload_len)
                    from minto.protocol.packet import read_string
                    json_str, _ = read_string(payload, 0)

                    # Verify players from backend mock server are returned!
                    data = json.loads(json_str)
                    self.assertEqual(data["players"]["online"], 123)
                    self.assertEqual(data["players"]["max"], 456)

                    # Send Ping packet (ID 0x01) with 8 bytes timestamp payload
                    ping_payload = b"\x11\x22\x33\x44\x55\x66\x77\x88"
                    client_writer.write(create_packet(0x01, ping_payload))
                    await client_writer.drain()

                    # Read Ping Response
                    ping_len, _ = await read_varint(client_reader)
                    ping_id, _ = await read_varint(client_reader)
                    self.assertEqual(ping_id, 0x01)
                    returned_payload = await client_reader.readexactly(ping_len - 1)
                    self.assertEqual(returned_payload, ping_payload)

                finally:
                    client_writer.close()
                    await client_writer.wait_closed()

            finally:
                await proxy.stop()

        finally:
            await mock_server.stop()

    def test_integration_defaults(self):
        asyncio.run(self.run_integration_defaults())

    async def run_integration_defaults(self):
        # Start Minto proxy instance with ShowSourcePlayers = False and default fallback
        service_cfg = {
            "Name": "MintoTest",
            "Listen": 25592,
            "TargetAddress": "127.0.0.1",
            "TargetPort": 25590,
            "Minecraft": {
                "OnlineCount": {
                    "Online": -1,
                    "Max": -1
                }
            }
        }
        proxy = MinecraftProxyInstance(service_cfg)
        await proxy.start()

        try:
            # Connect as a client to the proxy
            client_reader, client_writer = await asyncio.open_connection("127.0.0.1", 25592)

            try:
                # Send Handshake packet
                handshake = HandshakePacket(protocol_version=763, server_address="127.0.0.1", server_port=25592, next_state=1)
                client_writer.write(handshake.encode())

                # Send Status Request
                client_writer.write(create_packet(0x00, b""))
                await client_writer.drain()

                # Read Status Response
                packet_len, _ = await read_varint(client_reader)
                packet_id, _ = await read_varint(client_reader)
                self.assertEqual(packet_id, 0x00)

                payload_len = packet_len - 1
                payload = await client_reader.readexactly(payload_len)
                from minto.protocol.packet import read_string
                json_str, _ = read_string(payload, 0)

                # Verify default player counts are returned (active connections / 1005)
                data = json.loads(json_str)
                self.assertEqual(data["players"]["online"], 1)
                self.assertEqual(data["players"]["max"], 1005)

            finally:
                client_writer.close()
                await client_writer.wait_closed()

        finally:
            await proxy.stop()

    def test_integration_caching(self):
        asyncio.run(self.run_integration_caching())

    async def run_integration_caching(self):
        mock_server = MockMinecraftServer(25593, online_players=789, max_players=1011)
        await mock_server.start()

        try:
            service_cfg = {
                "Name": "MintoTestCache",
                "Listen": 25594,
                "TargetAddress": "127.0.0.1",
                "TargetPort": 25593,
                "Minecraft": {
                    "OnlineCount": {
                        "ShowSourcePlayers": True
                    }
                }
            }
            proxy = MinecraftProxyInstance(service_cfg)
            await proxy.start()

            try:
                # Query once (populates cache)
                online1, max1 = await proxy.query_source_server(763)
                self.assertEqual(online1, 789)
                self.assertEqual(max1, 1011)

                # Stop backend mock server completely
                await mock_server.stop()

                # Query second time (should hit cache and succeed without throwing connection error)
                online2, max2 = await proxy.query_source_server(763)
                self.assertEqual(online2, 789)
                self.assertEqual(max2, 1011)

            finally:
                await proxy.stop()

        finally:
            await mock_server.stop()


if __name__ == "__main__":
    unittest.main()
