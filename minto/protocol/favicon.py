import struct
import zlib
import base64

def generate_minto_favicon_b64():
    """
    Generates a 64x64 PNG icon with a light pink background and a light blue 'M' in the center,
    fully compliant with PNG specifications, in base64 format (data:image/png;base64,...).
    Does not require PIL or any external dependencies.
    """
    width = 64
    height = 64

    # Colors:
    # Light Pink background: RGB (255, 192, 203) -> #FFC0CB
    bg_r, bg_g, bg_b = 255, 192, 203
    # Light Blue text/M: RGB (173, 216, 230) -> #ADD8E6
    fg_r, fg_g, fg_b = 173, 216, 230

    # Construct the pixel buffer.
    # Each row starts with a filter byte (0 for no filter).
    pixels = bytearray()

    # Helper to check if a pixel (col, row) is part of 'M'
    # Coordinates range from 0 to 63
    def is_m(x, y):
        # We can draw a clean, stylized bold 'M'
        # Left leg: columns 14 to 20, rows 12 to 51
        if 14 <= x <= 20 and 12 <= y <= 51:
            return True
        # Right leg: columns 43 to 49, rows 12 to 51
        if 43 <= x <= 49 and 12 <= y <= 51:
            return True
        # Left diagonal: from (21, 12) down-right to (32, 34)
        if 21 <= x <= 32:
            diag_y = 12 + int(2.0 * (x - 21))
            if diag_y - 4 <= y <= diag_y + 4 and y <= 35:
                return True
        # Right diagonal: from (31, 34) up-right to (42, 12)
        if 31 <= x <= 42:
            diag_y = 34 - int(2.0 * (x - 32))
            if diag_y - 4 <= y <= diag_y + 4 and y <= 35:
                return True
        return False

    for y in range(height):
        pixels.append(0) # Filter byte
        for x in range(width):
            if is_m(x, y):
                pixels.append(fg_r)
                pixels.append(fg_g)
                pixels.append(fg_b)
            else:
                pixels.append(bg_r)
                pixels.append(bg_g)
                pixels.append(bg_b)

    # Create PNG chunks
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk: 13 bytes
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))

    # IDAT chunk: Compressed pixel data
    idat_data = zlib.compress(pixels, level=9)
    idat_chunk = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + struct.pack(">I", zlib.crc32(b"IDAT" + idat_data))

    # IEND chunk
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND"))

    png_data = signature + ihdr_chunk + idat_chunk + iend_chunk
    b64_encoded = base64.b64encode(png_data).decode("utf-8")
    return f"data:image/png;base64,{b64_encoded}"
