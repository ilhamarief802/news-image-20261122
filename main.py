#!/usr/bin/env python3
"""Write 22 November 2026's world news page to /output/entry.png.

The page is a committed file, entry.png, drawn by render.py from page.json; this
program copies it and then proves the copy is a whole, valid image before it
leaves anything behind. Standard library only: the sandbox runs Python 3.13 with
nothing installed, no network, a read-only /bot and a writable /output.

Checks, in the order the gate applies them:
  * the source exists and its first bytes say PNG (or JPEG);
  * it is at most 1048576 bytes and at most 1024 by 1024 pixels, read from the
    IHDR chunk (PNG) or the SOF marker (JPEG);
  * every PNG chunk is present with its CRC, through to IEND, so the file is a
    whole image rather than a truncated one;
  * the bytes written to /output are read back and match the source exactly.

Exits non-zero with one clear line on any failure, so a broken copy can never be
mistaken for a good one. Two runs write the same bytes because the program copies
a fixed file with no timestamps, randomness or locale in the path.
"""
import os
import struct
import sys
import zlib
from typing import NoReturn

JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
MAX_BYTES = 1048576
MAX_PX = 1024


def fail(msg: str) -> "NoReturn":
    sys.exit(f"main.py: {msg}")


def parse_png(data: bytes) -> tuple:
    """Return (width, height) after checking every chunk, or fail."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail("not a PNG: bad signature")
    pos, dims = 8, None
    while True:
        if pos + 8 > len(data):
            fail("PNG ends before its IEND chunk")
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            fail(f"PNG chunk {ctype!r} is truncated")
        crc_at = pos + 8 + length
        if crc_at + 4 > len(data):
            fail(f"PNG chunk {ctype!r} has no checksum")
        (want,) = struct.unpack(">I", data[crc_at:crc_at + 4])
        if zlib.crc32(ctype + body) & 0xFFFFFFFF != want:
            fail(f"PNG chunk {ctype!r} fails its checksum")
        if dims is None:
            if ctype != b"IHDR":
                fail("PNG does not open with IHDR")
            if length != 13:
                fail("PNG IHDR is not 13 bytes")
            dims = struct.unpack(">II", body[:8])
        pos = crc_at + 4
        if ctype == b"IEND":
            if pos != len(data):
                fail("PNG continues past IEND")
            return dims


def parse_jpeg(data: bytes) -> tuple:
    """Walk JPEG segments to the first SOF, or fail."""
    if data[:2] != b"\xff\xd8":
        fail("not a JPEG: bad signature")
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            fail("JPEG segment header missing")
        marker = data[pos + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        (seg,) = struct.unpack(">H", data[pos + 2:pos + 4])
        if marker in JPEG_SOF:
            if pos + 9 > len(data):
                fail("JPEG SOF is truncated")
            h, w = struct.unpack(">HH", data[pos + 5:pos + 9])
            return w, h
        pos += 2 + seg
    fail("JPEG has no SOF marker")


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "entry.png")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    dest = os.path.join(out_dir, "entry.png")

    if not os.path.isfile(src):
        fail(f"missing source image {src}")
    data = open(src, "rb").read()
    if len(data) > MAX_BYTES:
        fail(f"image is {len(data)} bytes, over the {MAX_BYTES} cap")

    w, h = parse_png(data) if data[:8] == b"\x89PNG\r\n\x1a\n" else parse_jpeg(data)
    if w > MAX_PX or h > MAX_PX:
        fail(f"image is {w}x{h}, over the {MAX_PX}x{MAX_PX} cap")
    if w == 0 or h == 0:
        fail(f"image reports {w}x{h}")

    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        if open(dest, "rb").read() != data:
            fail("the copy does not match the source")
    except OSError as exc:
        fail(f"cannot write {dest}: {exc.strerror or exc}")
    print(f"wrote {dest} ({len(data)} bytes, {w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
