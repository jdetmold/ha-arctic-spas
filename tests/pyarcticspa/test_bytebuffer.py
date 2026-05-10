"""Tests for the big-endian ByteBuffer helper."""

from custom_components.arctic_spa_local.pyarcticspa.protocol.bytebuffer import ByteBuffer


def test_put_int_writes_big_endian_4_bytes() -> None:
    buf = ByteBuffer.allocate(8)
    buf.put_int(0x01020304)
    assert bytes(buf.get_stream().getvalue()) == b"\x01\x02\x03\x04"


def test_put_short_writes_big_endian_2_bytes() -> None:
    buf = ByteBuffer.allocate(8)
    buf.put_short(0x0102)
    assert bytes(buf.get_stream().getvalue()) == b"\x01\x02"


def test_put_int_signed_negative() -> None:
    buf = ByteBuffer.allocate(8)
    buf.put_int(-1414718150)
    # -1414718150 as big-endian signed int32
    assert bytes(buf.get_stream().getvalue()) == b"\xab\xad\x1d\x3a"


def test_put_int_at_overwrites_unsigned() -> None:
    buf = ByteBuffer.allocate(16)
    buf.put_int(0)
    buf.put_int(0)
    buf.put_int_at(0, 0xDEADBEEF)
    assert bytes(buf.get_stream().getvalue())[:4] == b"\xde\xad\xbe\xef"


def test_put_bytes_appends_payload() -> None:
    buf = ByteBuffer.allocate(8)
    buf.put_int(0x01020304)
    buf.put_bytes(b"\x05\x06\x07")
    assert bytes(buf.get_stream().getvalue()) == b"\x01\x02\x03\x04\x05\x06\x07"
