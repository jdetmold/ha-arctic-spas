"""Big-endian byte buffer helper.

Ported from SpaBoii/bytebuffer.py. Used by the Levven packet serializer.
"""

from __future__ import annotations

import io
import struct


class ByteBuffer:
    """A minimal big-endian byte buffer.

    Mirrors the subset of Java NIO ByteBuffer behaviour the Levven
    packet serializer relies on: sequential big-endian writes plus
    a positional ``put_int_at`` for back-patching the CRC field.
    """

    def __init__(self, capacity: int = 0) -> None:
        self._stream = io.BytesIO()
        self._capacity = capacity

    @staticmethod
    def allocate(capacity: int) -> ByteBuffer:
        return ByteBuffer(capacity)

    def put_short(self, value: int) -> None:
        self._stream.write(struct.pack(">h", value))

    def put_int(self, value: int) -> None:
        self._stream.write(struct.pack(">i", value))

    def put_bytes(self, value: bytes) -> None:
        self._stream.write(value)

    def put_int_at(self, index: int, value: int) -> None:
        """Overwrite four bytes at ``index`` with ``value`` as big-endian uint32."""
        current = self._stream.tell()
        self._stream.seek(index)
        self._stream.write(struct.pack(">I", value & 0xFFFFFFFF))
        self._stream.seek(current)

    def get_stream(self) -> io.BytesIO:
        return self._stream

    def get_capacity(self) -> int:
        return self._capacity
