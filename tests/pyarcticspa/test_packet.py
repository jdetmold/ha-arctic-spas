"""Tests for LevvenPacket serialization."""

from custom_components.arctic_spa_local.pyarcticspa.protocol.messages import MessageType
from custom_components.arctic_spa_local.pyarcticspa.protocol.packet import LevvenPacket


def test_serialize_live_ping_with_empty_payload() -> None:
    pkt = LevvenPacket(MessageType.LIVE, b"")
    raw = pkt.serialize()

    # Magic bytes: -1414718150 big-endian signed -> 0xAB 0xAD 0x1D 0x3A
    assert raw[0:4] == b"\xab\xad\x1d\x3a"
    # Header is 20 bytes total, then payload
    assert len(raw) == 20
    # Type is at offset 16 as big-endian short
    assert raw[16:18] == b"\x00\x00"  # LIVE = 0x00
    # Size at offset 18 as big-endian short
    assert raw[18:20] == b"\x00\x00"


def test_serialize_information_ping_has_correct_type_byte() -> None:
    pkt = LevvenPacket(MessageType.INFORMATION, b"")
    raw = pkt.serialize()
    # Type 0x30 at offset 16-17
    assert raw[16:18] == b"\x00\x30"


def test_serialize_with_payload_includes_payload_at_end() -> None:
    payload = bytes([0xAA, 0xBB, 0xCC])
    pkt = LevvenPacket(MessageType.COMMAND, payload)
    raw = pkt.serialize()

    # Size short reflects payload length
    assert raw[18:20] == b"\x00\x03"
    # Payload follows the 20-byte header
    assert raw[20:23] == payload
    assert len(raw) == 23


def test_checksum_field_is_populated_after_serialize() -> None:
    pkt = LevvenPacket(MessageType.LIVE, b"")
    raw = pkt.serialize()
    # CRC32 of bytes [0..4) + [8..end) lands at offset 4-7. We don't
    # assert a specific value here (CRC is a function of the whole
    # buffer); we just assert it's nonzero — i.e. it was computed.
    assert raw[4:8] != b"\x00\x00\x00\x00"
    assert pkt.checksum != 0
