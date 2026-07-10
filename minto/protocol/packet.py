import struct
from minto.protocol.varint import encode_varint, read_varint_from_buffer

def create_packet(packet_id: int, payload: bytes) -> bytes:
    """
    Constructs a standard Minecraft packet.
    Packet structure: Length (VarInt) + PacketID (VarInt) + Payload (bytes)
    """
    id_bytes = encode_varint(packet_id)
    total_len = len(id_bytes) + len(payload)
    return encode_varint(total_len) + id_bytes + payload


def read_string(buffer: bytes, offset: int) -> tuple[str, int]:
    """
    Reads a VarInt-prefixed string from buffer with length bounds validation.
    Returns (string_value, new_offset).
    """
    length, bytes_read = read_varint_from_buffer(buffer, offset)
    offset += bytes_read
    if length < 0 or length > 32767:
        raise ValueError(f"String length {length} is invalid or exceeds safe limit of 32767")
    if offset + length > len(buffer):
        raise ValueError("String length exceeds buffer size")
    string_data = buffer[offset:offset+length]
    return string_data.decode("utf-8"), offset + length


def write_string(value: str) -> bytes:
    """
    Writes a string in VarInt-prefixed format.
    """
    data = value.encode("utf-8")
    return encode_varint(len(data)) + data


def read_ushort(buffer: bytes, offset: int) -> tuple[int, int]:
    """Reads an unsigned short (uint16) from buffer."""
    if offset + 2 > len(buffer):
        raise ValueError("Buffer too small for ushort")
    value = struct.unpack(">H", buffer[offset:offset+2])[0]
    return value, offset + 2


def write_ushort(value: int) -> bytes:
    """Writes an unsigned short (uint16)."""
    return struct.pack(">H", value)


class HandshakePacket:
    """
    Handshake packet structure (Packet ID = 0x00, Server bound):
    - Protocol Version: VarInt
    - Server Address: String
    - Server Port: Unsigned Short
    - Next State: VarInt (1 for status, 2 for login, 3 for transfer)
    """
    def __init__(self, protocol_version: int, server_address: str, server_port: int, next_state: int):
        self.protocol_version = protocol_version
        self.server_address = server_address
        self.server_port = server_port
        self.next_state = next_state

    @classmethod
    def decode(cls, payload: bytes) -> "HandshakePacket":
        offset = 0
        protocol_version, bytes_read = read_varint_from_buffer(payload, offset)
        offset += bytes_read

        server_address, offset = read_string(payload, offset)
        server_port, offset = read_ushort(payload, offset)

        next_state, bytes_read = read_varint_from_buffer(payload, offset)
        return cls(protocol_version, server_address, server_port, next_state)

    def encode(self) -> bytes:
        payload = bytearray()
        payload.extend(encode_varint(self.protocol_version))
        payload.extend(write_string(self.server_address))
        payload.extend(write_ushort(self.server_port))
        payload.extend(encode_varint(self.next_state))
        return create_packet(0x00, bytes(payload))


class LoginStartPacket:
    """
    Login Start packet structure (Packet ID = 0x00, Server bound):
    - Player Name: String (max length 16)
    - UUID / optional signature fields depending on protocol version (we just need the Player Name here).
    """
    def __init__(self, player_name: str):
        self.player_name = player_name

    @classmethod
    def decode(cls, payload: bytes) -> "LoginStartPacket":
        # First field is player name
        player_name, _ = read_string(payload, 0)
        return cls(player_name)
