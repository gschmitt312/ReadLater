"""Generate simple bookmark icons as PNG files."""
import struct, zlib, math

def make_png(size):
    """Create a minimal PNG with a bookmark ribbon icon."""
    img = []
    cx = size / 2
    accent = (91, 110, 245)
    bg     = (15, 17, 23)

    for y in range(size):
        row = []
        for x in range(size):
            # Circle background
            dx, dy = x - cx + 0.5, y - cx + 0.5
            dist = math.sqrt(dx*dx + dy*dy)
            r_outer = size * 0.48
            r_inner = size * 0.30

            if dist <= r_outer:
                # Draw a bookmark shape inside
                bx = (x - cx) / (size * 0.28)
                by = (y - cx) / (size * 0.30)
                # Bookmark ribbon: rectangle with notch at bottom
                if -0.65 <= bx <= 0.65 and -0.90 <= by <= 0.90:
                    notch_y = 0.50
                    if by > notch_y:
                        # V-notch: |bx| + (by - notch_y) > 0.65
                        if abs(bx) + (by - notch_y) * 1.3 < 0.65:
                            row += list(accent) + [255]
                        else:
                            row += list(bg) + [255]
                    else:
                        row += list(accent) + [255]
                else:
                    row += list(bg) + [255]
            else:
                row += [0, 0, 0, 0]  # transparent
        img.append(bytes(row))

    return _encode_png(size, size, img)

def _encode_png(w, h, rows):
    def chunk(tag, data):
        c = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)

    raw = b"".join(b"\x00" + r for r in rows)
    compressed = zlib.compress(raw, 9)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )

for size in (16, 48, 128):
    data = make_png(size)
    with open(f"icons/icon{size}.png", "wb") as f:
        f.write(data)
    print(f"Generated icon{size}.png ({len(data)} bytes)")
