import logging
import asyncio
import json
from typing import Dict, Any, List

from minto.protocol.varint import read_varint, encode_varint
from minto.protocol.packet import HandshakePacket, LoginStartPacket, create_packet, write_string
from minto.protocol.favicon import generate_minto_favicon_b64

logger = logging.getLogger("MintoProxy")


class MinecraftProxyInstance:
    def __init__(self, service_config: Dict[str, Any]):
        self.config = service_config
        self.name = service_config["Name"]
        self.listen_port = service_config["Listen"]
        self.target_address = service_config["TargetAddress"]
        self.target_port = service_config["TargetPort"]

        self.ip_access_mode = service_config.get("IPAccess", {}).get("Mode", "").lower()
        self.ip_access_list = service_config.get("IPAccess", {}).get("List", [])

        self.mc_config = service_config.get("Minecraft", {})
        self.enable_hostname_rewrite = self.mc_config.get("EnableHostnameRewrite", True)
        self.rewritten_hostname = self.mc_config.get("RewrittenHostname", self.target_address)

        self.online_count_config = self.mc_config.get("OnlineCount", {})
        self.max_players = self.online_count_config.get("Max", 2026)
        self.online_override = self.online_count_config.get("Online", -1)
        self.enable_max_limit = self.online_count_config.get("EnableMaxLimit", False)

        self.name_access_mode = self.mc_config.get("NameAccess", {}).get("Mode", "").lower()
        self.name_access_list = self.mc_config.get("NameAccess", {}).get("List", [])

        self.ping_mode = self.mc_config.get("PingMode", "disconnect").lower()
        self.motd_favicon = self.mc_config.get("MotdFavicon", "{DEFAULT_MOTD}")
        self.motd_description = self.mc_config.get("MotdDescription", "")

        self.server = None
        self._active_connections = 0

    def check_ip_access(self, ip: str) -> bool:
        """Returns True if the IP is allowed, False otherwise."""
        if not self.ip_access_mode:
            return True

        is_in_list = ip in self.ip_access_list
        if self.ip_access_mode == "accept":
            return is_in_list
        elif self.ip_access_mode == "deny":
            return not is_in_list
        return True

    def check_player_name_access(self, name: str) -> bool:
        """Returns True if the player name is allowed, False otherwise."""
        if not self.name_access_mode:
            return True

        is_in_list = name in self.name_access_list
        if self.name_access_mode == "accept":
            return is_in_list
        elif self.name_access_mode == "deny":
            return not is_in_list
        return True

    def generate_motd_json(self, protocol_version: int) -> bytes:
        """Generates MOTD JSON byte response for client status query."""
        # Compute online players count
        online = self.online_override if self.online_override >= 0 else self._active_connections

        # Determine favicon (custom pure colored PNG is generated here)
        favicon_str = self.motd_favicon
        if favicon_str == "{DEFAULT_MOTD}":
            favicon_str = generate_minto_favicon_b64()

        # Format description string
        desc = self.motd_description
        desc = desc.replace("{NAME}", self.name)
        desc = desc.replace("{HOST}", self.target_address)
        desc = desc.replace("{PORT}", str(self.target_port))

        motd_obj = {
            "version": {
                "name": "Minto Proxy 1.0",
                "protocol": protocol_version
            },
            "players": {
                "max": self.max_players,
                "online": online
            },
            "description": {
                "text": desc
            }
        }
        if favicon_str:
            motd_obj["favicon"] = favicon_str

        return json.dumps(motd_obj, ensure_ascii=False).encode("utf-8")

    async def handle_connection(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        peer = client_writer.get_extra_info("peername")
        client_ip = peer[0] if peer else "Unknown"

        if not self.check_ip_access(client_ip):
            logger.warning(f"Connection from IP {client_ip} rejected by IPAccess access controls.")
            client_writer.close()
            await client_writer.wait_closed()
            return

        logger.info(f"New inbound connection from {client_ip}")
        self._active_connections += 1

        try:
            # 1. Read Client Handshake
            # Handshake is preceded by packet length (VarInt) and Packet ID (VarInt)
            packet_len, _ = await read_varint(client_reader)
            if packet_len <= 0 or packet_len > 65535:
                raise ValueError(f"Handshake packet length {packet_len} exceeds safe limit.")

            packet_id, id_len = await read_varint(client_reader)

            if packet_id != 0x00:
                logger.warning(f"Expected handshake packet (0x00) but got packet ID {packet_id} from {client_ip}")
                return

            payload_len = packet_len - id_len
            if payload_len < 0 or payload_len > 65535:
                raise ValueError(f"Handshake payload length {payload_len} is invalid.")
            payload = await client_reader.readexactly(payload_len)

            handshake = HandshakePacket.decode(payload)
            protocol_version = handshake.protocol_version
            next_state = handshake.next_state

            logger.debug(f"Handshake: Protocol {protocol_version}, Addr {handshake.server_address}, Port {handshake.server_port}, NextState {next_state}")

            if next_state == 1:
                # MOTD/Status Request
                # Client will send an empty Status Request packet (Packet ID = 0x00)
                status_len, _ = await read_varint(client_reader)
                if status_len <= 0 or status_len > 1024:
                    raise ValueError(f"Status packet length {status_len} exceeds safe limit.")
                status_id, _ = await read_varint(client_reader)

                # Generate custom MOTD response (Packet ID = 0x00)
                motd_json = self.generate_motd_json(protocol_version)
                # JSON is prefixed with VarInt length
                motd_payload = encode_varint(len(motd_json)) + motd_json
                response_packet = create_packet(0x00, motd_payload)
                client_writer.write(response_packet)
                await client_writer.drain()

                # Check for ping packet (Packet ID = 0x01)
                try:
                    ping_len, _ = await read_varint(client_reader)
                    if ping_len <= 0 or ping_len > 1024:
                        raise ValueError(f"Ping packet length {ping_len} exceeds safe limit.")
                    ping_id, _ = await read_varint(client_reader)
                    if ping_id == 0x01:
                        # Read the remaining payload (timestamp / int64)
                        ping_payload = await client_reader.readexactly(ping_len - 1)
                        if self.ping_mode == "0ms":
                            # Return 0ms ping or custom respond
                            # 0ms responder: we can send 0 directly
                            ping_response = create_packet(0x01, b"\x00\x00\x00\x00\x00\x00\x00\x00")
                            client_writer.write(ping_response)
                        elif self.ping_mode == "disconnect":
                            # Just disconnect, do not respond
                            pass
                        else:
                            # normal: relay back same payload
                            ping_response = create_packet(0x01, ping_payload)
                            client_writer.write(ping_response)
                        await client_writer.drain()
                except Exception:
                    pass # Silent drop/disconnect is normal for client status

                logger.info(f"Responded customized MOTD for client {client_ip}")

            elif next_state == 2:
                # Login State
                # Next packet is Login Start (Packet ID = 0x00)
                login_len, _ = await read_varint(client_reader)
                if login_len <= 0 or login_len > 65535:
                    raise ValueError(f"Login Start packet length {login_len} exceeds safe limit.")
                login_id, login_id_len = await read_varint(client_reader)

                if login_id != 0x00:
                    logger.warning(f"Expected Login Start packet (0x00) but got {login_id} from {client_ip}")
                    return

                login_payload = await client_reader.readexactly(login_len - login_id_len)
                login_start = LoginStartPacket.decode(login_payload)
                player_name = login_start.player_name

                logger.info(f"Player {player_name} attempting to login from {client_ip}")

                # Verify access controls
                if not self.check_player_name_access(player_name):
                    logger.warning(f"Player {player_name} from {client_ip} was rejected by NameAccess controls.")
                    # Send custom disconnect packet (Login Disconnect packet ID is 0x00)
                    kick_message = {
                        "text": "§cConnection Rejected by NameAccess policy."
                    }
                    kick_payload = write_string(json.dumps(kick_message))
                    client_writer.write(create_packet(0x00, kick_payload))
                    await client_writer.drain()
                    return

                if self.enable_max_limit and self.max_players <= self._active_connections - 1:
                    logger.warning(f"Player {player_name} rejected: Server full ({self._active_connections - 1}/{self.max_players})")
                    kick_message = {
                        "text": f"§cServer is currently full. Max: {self.max_players}"
                    }
                    kick_payload = write_string(json.dumps(kick_message))
                    client_writer.write(create_packet(0x00, kick_payload))
                    await client_writer.drain()
                    return

                # Connect to target Minecraft server
                try:
                    server_reader, server_writer = await asyncio.wait_for(
                        asyncio.open_connection(self.target_address, self.target_port),
                        timeout=10.0
                    )
                except Exception as e:
                    logger.error(f"Failed to connect to target Minecraft server {self.target_address}:{self.target_port}: {e}")
                    kick_message = {
                        "text": "§cFailed to connect to backend target server."
                    }
                    kick_payload = write_string(json.dumps(kick_message))
                    client_writer.write(create_packet(0x00, kick_payload))
                    await client_writer.drain()
                    return

                try:
                    # Forward modified Handshake Packet to backend
                    rewritten_addr = self.rewritten_hostname if self.enable_hostname_rewrite else handshake.server_address
                    new_handshake = HandshakePacket(
                        protocol_version=handshake.protocol_version,
                        server_address=rewritten_addr,
                        server_port=handshake.server_port,
                        next_state=handshake.next_state
                    )
                    server_writer.write(new_handshake.encode())

                    # Forward Login Start Packet
                    new_login_start = create_packet(0x00, login_payload)
                    server_writer.write(new_login_start)
                    await server_writer.drain()

                    logger.info(f"Relaying connection for {player_name} to backend server ({self.target_address}:{self.target_port}) with host rewrite: {rewritten_addr}")

                    # Bidirectional tunneling
                    task_c2s = asyncio.create_task(pipe(client_reader, server_writer))
                    task_s2c = asyncio.create_task(pipe(server_reader, client_writer))

                    try:
                        done, pending = await asyncio.wait(
                            {task_c2s, task_s2c},
                            return_when=asyncio.FIRST_COMPLETED
                        )
                    finally:
                        # Cancel remaining task to prevent leaks
                        for t in [task_c2s, task_s2c]:
                            if not t.done():
                                t.cancel()
                                try:
                                    await t
                                except asyncio.CancelledError:
                                    pass
                except Exception as e:
                    logger.debug(f"Tunneling interrupted for {player_name}: {e}")
                finally:
                    server_writer.close()
                    try:
                        await server_writer.wait_closed()
                    except Exception:
                        pass
                    logger.info(f"Disconnected player {player_name} ({client_ip})")
            else:
                logger.warning(f"Unsupported next state {next_state} from client {client_ip}")

        except asyncio.IncompleteReadError:
            logger.debug(f"Incomplete read / client {client_ip} early disconnect.")
        except Exception as e:
            logger.error(f"Error handling connection from {client_ip}: {e}")
        finally:
            self._active_connections -= 1
            client_writer.close()
            try:
                await client_writer.wait_closed()
            except Exception:
                pass


    async def start(self):
        """Starts the local TCP listener proxy."""
        self.server = await asyncio.start_server(self.handle_connection, "0.0.0.0", self.listen_port)
        logger.info(f"Service '{self.name}' listening on 0.0.0.0:{self.listen_port} -> forwarding to {self.target_address}:{self.target_port}")


    async def stop(self):
        """Stops the local proxy listener."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info(f"Service '{self.name}' stopped.")


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Auxiliary method to pipeline data from async reader to writer."""
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()
