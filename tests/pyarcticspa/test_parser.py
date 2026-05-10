"""Tests for the streaming Levven packet parser."""

from custom_components.arctic_spa.pyarcticspa.protocol.messages import MessageType
from custom_components.arctic_spa.pyarcticspa.protocol.packet import LevvenPacket
from custom_components.arctic_spa.pyarcticspa.protocol.parser import StreamParser


def test_feed_complete_packet_yields_one_packet() -> None:
    raw = LevvenPacket(MessageType.LIVE, b"\x01\x02\x03").serialize()
    parser = StreamParser()
    packets = list(parser.feed(raw))
    assert len(packets) == 1
    assert packets[0].type == MessageType.LIVE
    assert packets[0].payload == b"\x01\x02\x03"


def test_feed_two_packets_back_to_back_yields_two() -> None:
    raw = (
        LevvenPacket(MessageType.LIVE, b"\xaa").serialize()
        + LevvenPacket(MessageType.INFORMATION, b"\xbb\xcc").serialize()
    )
    parser = StreamParser()
    packets = list(parser.feed(raw))
    assert len(packets) == 2
    assert packets[0].type == MessageType.LIVE
    assert packets[0].payload == b"\xaa"
    assert packets[1].type == MessageType.INFORMATION
    assert packets[1].payload == b"\xbb\xcc"


def test_feed_split_across_calls_yields_after_complete() -> None:
    raw = LevvenPacket(MessageType.LIVE, b"\x01\x02\x03").serialize()
    parser = StreamParser()
    # Split midway through the payload
    assert list(parser.feed(raw[:21])) == []
    packets = list(parser.feed(raw[21:]))
    assert len(packets) == 1
    assert packets[0].type == MessageType.LIVE
    assert packets[0].payload == b"\x01\x02\x03"


def test_leading_garbage_is_resynchronised() -> None:
    raw = b"\x00\xff\x00\xff" + LevvenPacket(MessageType.LIVE, b"\x42").serialize()
    parser = StreamParser()
    packets = list(parser.feed(raw))
    assert len(packets) == 1
    assert packets[0].payload == b"\x42"


def test_empty_payload_packet_is_yielded() -> None:
    raw = LevvenPacket(MessageType.PING, b"").serialize()
    parser = StreamParser()
    packets = list(parser.feed(raw))
    assert len(packets) == 1
    assert packets[0].type == MessageType.PING
    assert packets[0].payload == b""


def test_corrupt_packet_does_not_block_subsequent_packet() -> None:
    good = LevvenPacket(MessageType.LIVE, b"\x42").serialize()
    # Corrupt the magic of one packet, then send a clean one
    corrupt = b"\x99\x99\x99\x99" + good[4:]
    parser = StreamParser()
    packets = list(parser.feed(corrupt + good))
    # Whether the corrupt packet is dropped or partially consumed,
    # the trailing good packet must come through intact.
    assert any(p.type == MessageType.LIVE and p.payload == b"\x42" for p in packets)
