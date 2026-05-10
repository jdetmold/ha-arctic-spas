"""Stream parser that consumes raw bytes and yields LevvenPacket instances.

Direct port of the byte-by-byte state machine in
SpaBoii/SpaBoii.py:handle_packets, refactored so the caller feeds bytes in
and pulls completed packets out via a generator.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .packet import LevvenPacket


def _signed_byte(b: int) -> int:
    return b - 256 if b > 127 else b


def _u32_be(b1: int, b2: int, b3: int, b4: int) -> int:
    return ((b1 & 0xFF) << 24) | ((b2 & 0xFF) << 16) | ((b3 & 0xFF) << 8) | (b4 & 0xFF)


def _u16_be(b1: int, b2: int) -> int:
    return ((b1 & 0xFF) << 8) | (b2 & 0xFF)


# Magic byte sequence (raw, unsigned): 0xAB 0xAD 0x1D 0x3A
_MAGIC_BYTES = (0xAB, 0xAD, 0x1D, 0x3A)


class StreamParser:
    """Stateful parser that buffers across calls until a packet is complete."""

    def __init__(self) -> None:
        self._state = 0
        self._packet = LevvenPacket()
        self._t1 = 0
        self._t2 = 0
        self._t3 = 0
        self._payload_index = 0
        self._payload_buf = bytearray()

    def feed(self, data: bytes) -> Iterator[LevvenPacket]:
        """Consume bytes; yield any completed packets."""
        for byte in data:
            yield from self._feed_byte(byte)

    def _feed_byte(self, raw: int) -> Iterable[LevvenPacket]:
        signed = _signed_byte(raw)
        s = self._state
        try:
            if s == 0:
                self._state = 1 if raw == _MAGIC_BYTES[0] else 0
            elif s == 1:
                self._state = 2 if raw == _MAGIC_BYTES[1] else 0
            elif s == 2:
                self._state = 3 if raw == _MAGIC_BYTES[2] else 0
            elif s == 3:
                self._state = 4 if raw == _MAGIC_BYTES[3] else 0
            elif s == 4:
                self._t1 = signed
                self._state = 5
            elif s == 5:
                self._t2 = signed
                self._state = 6
            elif s == 6:
                self._t3 = signed
                self._state = 7
            elif s == 7:
                self._packet.checksum = _u32_be(self._t1, self._t2, self._t3, signed)
                self._state = 8
            elif s == 8:
                self._t1 = signed
                self._state = 9
            elif s == 9:
                self._t2 = signed
                self._state = 10
            elif s == 10:
                self._t3 = signed
                self._state = 11
            elif s == 11:
                self._packet.sequence_number = _u32_be(self._t1, self._t2, self._t3, signed)
                self._state = 12
            elif s == 12:
                self._t1 = signed
                self._state = 13
            elif s == 13:
                self._t2 = signed
                self._state = 14
            elif s == 14:
                self._t3 = signed
                self._state = 15
            elif s == 15:
                self._packet.optional = _u32_be(self._t1, self._t2, self._t3, signed)
                self._state = 16
            elif s == 16:
                self._t3 = signed
                self._state = 17
            elif s == 17:
                self._packet.type = _u16_be(self._t3, signed)
                self._state = 18
            elif s == 18:
                self._t3 = signed
                self._state = 19
            elif s == 19:
                size = _u16_be(self._t3, signed)
                self._payload_buf = bytearray(size)
                self._payload_index = 0
                if size == 0:
                    yield self._finalise()
                else:
                    self._state = 20
            elif s == 20:
                self._payload_buf[self._payload_index] = raw & 0xFF
                self._payload_index += 1
                if self._payload_index >= len(self._payload_buf):
                    yield self._finalise()
        except Exception:
            self._reset()

    def _finalise(self) -> LevvenPacket:
        finished = LevvenPacket(
            type=self._packet.type,
            payload=bytes(self._payload_buf),
            sequence_number=self._packet.sequence_number,
            optional=self._packet.optional,
            checksum=self._packet.checksum,
        )
        self._reset()
        return finished

    def _reset(self) -> None:
        self._state = 0
        self._packet = LevvenPacket()
        self._payload_index = 0
        self._payload_buf = bytearray()
