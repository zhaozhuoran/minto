def encode_varint(value: int) -> bytes:
    """Encodes an integer into Minecraft's VarInt format."""
    # Since VarInt is up to 5 bytes, mask negative integers as 32-bit unsigned.
    val = value & 0xFFFFFFFF
    result = bytearray()
    while True:
        temp = val & 0x7F
        val >>= 7
        if val != 0:
            temp |= 0x80
        result.append(temp)
        if val == 0:
            break
    return bytes(result)


async def read_varint(reader) -> tuple[int, int]:
    """
    Reads a VarInt from an async reader (like asyncio.StreamReader) or a synchronous byte stream.
    Returns a tuple of (value, bytes_read).
    """
    num_read = 0
    result = 0
    while True:
        if hasattr(reader, "readexactly"):
            byte_bytes = await reader.readexactly(1)
            b = byte_bytes[0]
        else:
            byte_bytes = reader.read(1)
            if not byte_bytes:
                raise ConnectionError("EOF while reading VarInt")
            b = byte_bytes[0]

        value = b & 0x7F
        result |= value << (7 * num_read)
        num_read += 1

        if num_read > 5:
            raise ValueError("VarInt is too big (exceeds 5 bytes)")

        if (b & 0x80) == 0:
            break

    # Convert unsigned to signed 32-bit int
    if result & 0x80000000:
        result -= 0x100000000
    return result, num_read


def read_varint_from_buffer(buffer: bytes, offset: int = 0) -> tuple[int, int]:
    """
    Synchronously decodes a VarInt from a byte array buffer at the given offset.
    Returns (value, bytes_read).
    """
    num_read = 0
    result = 0
    while True:
        if offset + num_read >= len(buffer):
            raise IndexError("Buffer overflow while decoding VarInt")
        b = buffer[offset + num_read]
        value = b & 0x7F
        result |= value << (7 * num_read)
        num_read += 1
        if num_read > 5:
            raise ValueError("VarInt too big")
        if (b & 0x80) == 0:
            break

    if result & 0x80000000:
        result -= 0x100000000
    return result, num_read
