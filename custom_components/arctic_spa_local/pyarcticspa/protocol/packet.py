"""Levven packet framing.

Packet layout (all integers big-endian):
    offset  size  field
    0       4     magic (signed int -1414718150 = 0xABAD1D3A)
    4       4     CRC32 of header + payload (with CRC field zeroed during compute)
    8       4     sequence_number (unused for outbound from us; spa echoes its own)
    12      4     optional flags
    16      2     message type
    18      2     payload size
    20      N     payload (protobuf-encoded)
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

from .bytebuffer import ByteBuffer

MAGIC = -1414718150  # 0xABAD1D3A interpreted as signed int32


@dataclass
class LevvenPacket:
    """A Levven framing protocol packet."""

    type: int = 0
    payload: bytes = field(default_factory=bytes)
    sequence_number: int = 0
    optional: int = 0
    checksum: int = 0

    @property
    def size(self) -> int:
        return len(self.payload)

    def serialize(self) -> bytes:
        """Serialize to wire format with CRC32 computed and back-patched."""
        buf = ByteBuffer.allocate(self.size + 20)
        buf.put_int(MAGIC)
        buf.put_int(0)  # CRC placeholder, back-patched below
        buf.put_int(self.sequence_number)
        buf.put_int(self.optional)
        buf.put_short(self.type)
        buf.put_short(self.size)
        if self.payload:
            buf.put_bytes(bytes(self.payload))

        crc = zlib.crc32(buf.get_stream().getvalue())
        self.checksum = crc
        buf.put_int_at(4, crc)
        return buf.get_stream().getvalue()
