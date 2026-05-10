# Arctic Spa HA Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a HACS-installable Home Assistant custom integration `arctic_spa` that talks directly to an Arctic Spa hot tub over its local TCP protocol and creates native HA entities (no MQTT bridge).

**Architecture:** Vendored protocol library (`pyarcticspa/`, no HA imports) wrapped by an HA `DataUpdateCoordinator`. Persistent TCP connection pushes state updates to entities; commands flow back through a serialized async queue. One config entry per spa, identified by pack serial number.

**Tech Stack:** Python 3.12 (HA 2024.11+ requirement), `asyncio`, `protobuf>=4.21,<6`, Home Assistant Core, `pytest`, `pytest-homeassistant-custom-component`, `ruff`, `mypy`.

**Spec:** `docs/superpowers/specs/2026-05-09-arctic-spa-integration-design.md`

**Reference implementation:** `SpaBoii/` (cloned locally, gitignored). Treat as the protocol oracle. Files of interest:
- `SpaBoii/levven_packet.py` — packet framing & CRC32
- `SpaBoii/bytebuffer.py` — big-endian byte buffer helper
- `SpaBoii/SpaBoii.py` — packet parser state machine (`handle_packets`), command builder, ping cadence
- `SpaBoii/proto/*.proto` — protobuf schemas (vendor regenerated `_pb2.py`)

---

## Repo file map

Files to create (in `/home/jeff/Development/HA-AS-Connector/`):

```
custom_components/arctic_spa/
  __init__.py                 # async_setup_entry / async_unload_entry
  manifest.json
  hacs.json (at repo root)
  config_flow.py
  const.py
  coordinator.py
  entity.py
  climate.py
  sensor.py
  binary_sensor.py
  switch.py
  select.py
  button.py
  diagnostics.py
  strings.json
  translations/en.json
  pyarcticspa/
    __init__.py
    __main__.py               # live-dump tool: python -m pyarcticspa <ip>
    client.py
    models.py
    replay.py                 # python -m pyarcticspa.replay <capture>
    protocol/
      __init__.py
      bytebuffer.py
      packet.py
      parser.py
      messages.py
      commands.py             # build_command(**fields) -> SpaCommand
    proto/
      *.proto                 # source schemas (reference)
      *_pb2.py                # regenerated, committed

tests/
  pyarcticspa/
    test_bytebuffer.py
    test_packet.py
    test_parser.py
    test_client.py
    test_models.py
  components/arctic_spa/
    conftest.py
    test_config_flow.py
    test_init.py
    test_coordinator.py
    test_climate.py
    test_sensor.py
    test_binary_sensor.py
    test_switch.py
    test_select.py
    test_button.py
    test_diagnostics.py

scripts/
  regenerate_protos.sh

.github/workflows/
  validate.yml                # ruff, mypy, hassfest, hacs validation, pytest

pyproject.toml
README.md
LICENSE
```

---

## Phase 1: Project scaffolding

### Task 1: Initial repo files (manifest, pyproject, README skeleton)

**Files:**
- Create: `pyproject.toml`
- Create: `hacs.json`
- Create: `README.md`
- Create: `LICENSE` (MIT — matches SpaBoii)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "ha-arctic-spa"
version = "0.1.0"
description = "Home Assistant custom integration for Arctic Spa hot tubs"
readme = "README.md"
requires-python = ">=3.12"
license = {text = "MIT"}
authors = [{name = "Jeff", email = "jeff@techyyc.com"}]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "N", "ASYNC", "PT"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
exclude = ["custom_components/arctic_spa/pyarcticspa/proto/.*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `hacs.json`**

```json
{
  "name": "Arctic Spa",
  "render_readme": true,
  "homeassistant": "2024.11.0",
  "country": ["CA", "US"]
}
```

- [ ] **Step 3: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Jeff

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Create `README.md`**

```markdown
# Arctic Spa for Home Assistant

A HACS-installable Home Assistant custom integration for Arctic Spa hot tubs.
Connects directly to your spa over your local network — no MQTT broker, no
cloud account, no Supervisor add-on.

## Status

Early development. See `docs/superpowers/specs/` for the design and
`docs/superpowers/plans/` for the implementation plan.

## Installation (HACS)

1. In HACS, add this repository as a custom integration repository.
2. Install "Arctic Spa".
3. Restart Home Assistant.
4. Settings → Devices & Services → Add Integration → search "Arctic Spa".
5. Enter your spa's local IP address.

## Credit

Reverse-engineering work originated in
[SpaBoii](https://github.com/Patrick-Ohlson/SpaBoii) by Patrick Ohlson.
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml hacs.json LICENSE README.md
git commit -m "Add project metadata, HACS manifest, README, and license"
```

---

### Task 2: Vendor protobuf source files

The SpaBoii `_pb2.py` files were generated against `protobuf==3.20.3`. We will regenerate them with a current `protoc` to be compatible with `protobuf>=4.21`. The `.proto` files are the source of truth and are committed alongside the generated output.

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/proto/__init__.py`
- Create: `custom_components/arctic_spa/pyarcticspa/proto/*.proto` (copied from `SpaBoii/proto/`)
- Create: `scripts/regenerate_protos.sh`
- Create: `custom_components/arctic_spa/pyarcticspa/proto/*_pb2.py` (regenerated)

- [ ] **Step 1: Copy `.proto` source files from SpaBoii**

```bash
mkdir -p custom_components/arctic_spa/pyarcticspa/proto
cp SpaBoii/proto/*.proto custom_components/arctic_spa/pyarcticspa/proto/
```

- [ ] **Step 2: Create `custom_components/arctic_spa/pyarcticspa/proto/__init__.py`**

```python
"""Compiled protobuf message classes for the Arctic Spa local protocol.

These modules are generated from the .proto sources by
`scripts/regenerate_protos.sh`. Do not edit by hand.
"""
```

- [ ] **Step 3: Create `scripts/regenerate_protos.sh`**

```bash
#!/usr/bin/env bash
# Regenerate compiled protobuf modules from the .proto source files.
#
# Requires: pip install grpcio-tools  (provides a vendored protoc)
set -euo pipefail

PROTO_DIR="custom_components/arctic_spa/pyarcticspa/proto"

cd "$(git rev-parse --show-toplevel)"

python -m grpc_tools.protoc \
  --proto_path="$PROTO_DIR" \
  --python_out="$PROTO_DIR" \
  "$PROTO_DIR"/*.proto

echo "Regenerated $(ls "$PROTO_DIR"/*_pb2.py | wc -l) protobuf modules."
```

- [ ] **Step 4: Make the script executable and run it**

```bash
chmod +x scripts/regenerate_protos.sh
pip install grpcio-tools
./scripts/regenerate_protos.sh
```

Expected: Files like `spa_live_pb2.py`, `SpaCommand_pb2.py`, etc. created in `custom_components/arctic_spa/pyarcticspa/proto/`.

- [ ] **Step 5: Verify generated modules import**

```bash
PYTHONPATH=custom_components/arctic_spa python -c "
from pyarcticspa.proto import spa_live_pb2
from pyarcticspa.proto import SpaCommand_pb2
from pyarcticspa.proto import SpaInformation_pb2
from pyarcticspa.proto import spa_configuration_pb2
print('OK', spa_live_pb2.spa_live().DESCRIPTOR.name)
"
```

Expected: `OK spa_live`

- [ ] **Step 6: Commit**

```bash
git add scripts/ custom_components/arctic_spa/pyarcticspa/proto/
git commit -m "Vendor and regenerate Arctic Spa protobuf schemas"
```

---

## Phase 2: Protocol library (TDD)

The library lives at `custom_components/arctic_spa/pyarcticspa/`. It must have **zero Home Assistant imports** — verify with `grep -r "homeassistant" custom_components/arctic_spa/pyarcticspa/` returning nothing.

### Task 3: ByteBuffer helper

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/protocol/__init__.py`
- Create: `custom_components/arctic_spa/pyarcticspa/protocol/bytebuffer.py`
- Test: `tests/pyarcticspa/test_bytebuffer.py`
- Test: `tests/pyarcticspa/__init__.py` (empty)
- Test: `tests/__init__.py` (empty)

- [ ] **Step 1: Add empty `__init__.py` files**

```bash
mkdir -p tests/pyarcticspa custom_components/arctic_spa/pyarcticspa/protocol
touch tests/__init__.py tests/pyarcticspa/__init__.py
touch custom_components/arctic_spa/pyarcticspa/__init__.py
touch custom_components/arctic_spa/pyarcticspa/protocol/__init__.py
```

- [ ] **Step 2: Write the failing test (`tests/pyarcticspa/test_bytebuffer.py`)**

```python
"""Tests for the big-endian ByteBuffer helper."""

from custom_components.arctic_spa.pyarcticspa.protocol.bytebuffer import ByteBuffer


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
```

- [ ] **Step 3: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_bytebuffer.py -v
```

Expected: ImportError (module not yet created).

- [ ] **Step 4: Create `custom_components/arctic_spa/pyarcticspa/protocol/bytebuffer.py`**

```python
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
    a positional `put_int_at` for back-patching the CRC field.
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
        """Overwrite four bytes at `index` with `value` as big-endian uint32."""
        current = self._stream.tell()
        self._stream.seek(index)
        self._stream.write(struct.pack(">I", value & 0xFFFFFFFF))
        self._stream.seek(current)

    def get_stream(self) -> io.BytesIO:
        return self._stream

    def get_capacity(self) -> int:
        return self._capacity
```

- [ ] **Step 5: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_bytebuffer.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/__init__.py \
        custom_components/arctic_spa/pyarcticspa/protocol/__init__.py \
        custom_components/arctic_spa/pyarcticspa/protocol/bytebuffer.py \
        tests/__init__.py tests/pyarcticspa/__init__.py tests/pyarcticspa/test_bytebuffer.py
git commit -m "Add ByteBuffer helper for Levven packet serialization"
```

---

### Task 4: LevvenPacket serializer

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/protocol/messages.py`
- Create: `custom_components/arctic_spa/pyarcticspa/protocol/packet.py`
- Test: `tests/pyarcticspa/test_packet.py`

- [ ] **Step 1: Create `messages.py`**

```python
"""Message-type constants for the Levven framing protocol."""

from __future__ import annotations

from enum import IntEnum


class MessageType(IntEnum):
    """Levven message types observed in SpaBoii's reverse engineering."""

    LIVE = 0x00
    COMMAND = 0x01
    PING = 0x0A
    INFORMATION = 0x30
    CONFIGURATION = 0x03
    ONZEN_SETTINGS = 0x32

    @classmethod
    def title(cls, value: int) -> str:
        try:
            return cls(value).name.title()
        except ValueError:
            return f"Unknown(0x{value:02X})"
```

- [ ] **Step 2: Write the failing test (`tests/pyarcticspa/test_packet.py`)**

```python
"""Tests for LevvenPacket serialization."""

from custom_components.arctic_spa.pyarcticspa.protocol.messages import MessageType
from custom_components.arctic_spa.pyarcticspa.protocol.packet import LevvenPacket


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
```

- [ ] **Step 3: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_packet.py -v
```

Expected: ImportError.

- [ ] **Step 4: Create `packet.py`**

```python
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
            buf.put_bytes(self.payload)

        crc = zlib.crc32(buf.get_stream().getvalue())
        self.checksum = crc
        buf.put_int_at(4, crc)
        return buf.get_stream().getvalue()
```

- [ ] **Step 5: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_packet.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/protocol/messages.py \
        custom_components/arctic_spa/pyarcticspa/protocol/packet.py \
        tests/pyarcticspa/test_packet.py
git commit -m "Add LevvenPacket serializer with CRC32 framing"
```

---

### Task 5: Stream parser (state machine)

The parser consumes bytes and yields complete packets. It mirrors `handle_packets` in `SpaBoii/SpaBoii.py:99-133` but is fed bytes externally and yields packets via a generator-style API.

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/protocol/parser.py`
- Test: `tests/pyarcticspa/test_parser.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_parser.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `parser.py`**

```python
"""Stream parser that consumes raw bytes and yields LevvenPacket instances.

Direct port of the byte-by-byte state machine in
SpaBoii/SpaBoii.py:handle_packets, refactored so the caller feeds bytes in
and pulls completed packets out via a generator.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .messages import MessageType
from .packet import LevvenPacket


def _signed_byte(b: int) -> int:
    return b - 256 if b > 127 else b


def _u32_be(b1: int, b2: int, b3: int, b4: int) -> int:
    return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4


def _u16_be(b1: int, b2: int) -> int:
    return (b1 << 8) | b2


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
                self._packet.type = _u16_be(self._t3, signed) & 0xFFFF
                self._state = 18
            elif s == 18:
                self._t3 = signed
                self._state = 19
            elif s == 19:
                size = _u16_be(self._t3, signed) & 0xFFFF
                self._packet.payload = bytearray(size)
                self._payload_index = 0
                if size == 0:
                    yield self._finalise()
                else:
                    self._state = 20
            elif s == 20:
                assert isinstance(self._packet.payload, bytearray)
                self._packet.payload[self._payload_index] = raw & 0xFF
                self._payload_index += 1
                if self._payload_index >= len(self._packet.payload):
                    yield self._finalise()
        except Exception:
            self._reset()

    def _finalise(self) -> LevvenPacket:
        # Convert payload to bytes for downstream consumers
        finished = LevvenPacket(
            type=self._packet.type,
            payload=bytes(self._packet.payload),
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
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_parser.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/protocol/parser.py \
        tests/pyarcticspa/test_parser.py
git commit -m "Add streaming Levven packet parser"
```

---

### Task 6: Snapshot dataclasses + has_* helpers

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/models.py`
- Test: `tests/pyarcticspa/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for SpaSnapshot dataclasses and hardware-presence helpers."""

from custom_components.arctic_spa.pyarcticspa.models import (
    PumpStatus,
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
    has_blower,
    has_exhaust_fan,
    has_fogger,
    has_heater,
    has_lights,
    has_onzen,
    has_ph_orp,
    has_pump,
    has_sauna,
    has_stereo,
)


def _snapshot(**overrides: object) -> SpaSnapshot:
    state = overrides.get("state", SpaState())
    info = overrides.get("info", SpaInfo())
    config = overrides.get("config", SpaConfiguration())
    return SpaSnapshot(state=state, info=info, config=config)


def test_default_snapshot_reports_no_hardware() -> None:
    snap = _snapshot()
    assert not has_pump(snap, 1)
    assert not has_blower(snap, 1)
    assert not has_lights(snap)
    assert not has_onzen(snap)
    assert not has_heater(snap, 1)


def test_pump_present_when_state_reports_value() -> None:
    snap = _snapshot(state=SpaState(pump_1=PumpStatus.OFF))
    assert has_pump(snap, 1)
    assert not has_pump(snap, 2)


def test_lights_present_when_state_field_set() -> None:
    snap = _snapshot(state=SpaState(lights=False))
    assert has_lights(snap)


def test_onzen_present_when_state_reports_field() -> None:
    snap = _snapshot(state=SpaState(onzen=False))
    assert has_onzen(snap)


def test_ph_orp_present_when_either_value_set() -> None:
    assert has_ph_orp(_snapshot(state=SpaState(ph=7.4)))
    assert has_ph_orp(_snapshot(state=SpaState(orp=650.0)))
    assert not has_ph_orp(_snapshot())


def test_heater_presence_keyed_by_state_field() -> None:
    snap = _snapshot(state=SpaState(heater_1="IDLE"))
    assert has_heater(snap, 1)
    assert not has_heater(snap, 2)


def test_unknown_snapshot_create_everything_fallback() -> None:
    """When config is None at platform setup, all has_* helpers return True."""
    snap = SpaSnapshot(state=None, info=None, config=None)
    assert has_pump(snap, 1)
    assert has_pump(snap, 5)
    assert has_blower(snap, 2)
    assert has_lights(snap)
    assert has_onzen(snap)
    assert has_ph_orp(snap)
    assert has_heater(snap, 1)
    assert has_heater(snap, 2)
    assert has_exhaust_fan(snap)
    assert has_fogger(snap)
    assert has_stereo(snap)
    assert has_sauna(snap)


def test_blower_present_when_state_reports_value() -> None:
    snap = _snapshot(state=SpaState(blower_1=PumpStatus.OFF))
    assert has_blower(snap, 1)
    assert not has_blower(snap, 2)
```

- [ ] **Step 2: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_models.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `models.py`**

```python
"""Public dataclasses and hardware-presence helpers for the Arctic Spa library."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PumpStatus(str, Enum):
    OFF = "OFF"
    LOW = "LOW"
    HIGH = "HIGH"


class HeaterStatus(str, Enum):
    IDLE = "IDLE"
    WARMUP = "WARMUP"
    HEATING = "HEATING"
    OVERHEAT = "OVERHEAT"


@dataclass(frozen=True)
class SpaState:
    """Latest live state observed from the spa.

    Mirrors the fields of the spa_live protobuf message plus parsed
    pH/ORP values from INFORMATION packets.
    """

    temperature_fahrenheit: int | None = None
    temperature_setpoint_fahrenheit: int | None = None
    temperature_celsius: int | None = None
    pump_1: PumpStatus | None = None
    pump_2: PumpStatus | None = None
    pump_3: PumpStatus | None = None
    pump_4: PumpStatus | None = None
    pump_5: PumpStatus | None = None
    blower_1: PumpStatus | None = None
    blower_2: PumpStatus | None = None
    lights: bool | None = None
    stereo: bool | None = None
    heater_1: str | None = None  # raw HEATER_STATUS enum name
    heater_2: str | None = None
    filter: str | None = None  # raw FILTER_STATUS enum name
    onzen: bool | None = None
    ozone: str | None = None  # raw OZONE_STATUS name with OZONE_ prefix stripped
    exhaust_fan: bool | None = None
    sauna: str | None = None  # raw SAUNA_STATUS name
    heater_adc: int | None = None
    sauna_time_remaining: int | None = None
    economy: bool | None = None
    current_adc: int | None = None
    all_on: bool | None = None
    fogger: bool | None = None
    ph: float | None = None
    orp: float | None = None
    cl_range: str | None = None  # "Low" | "Mid" | "High" parsed from ONZEN_SETTINGS


@dataclass(frozen=True)
class SpaInfo:
    """Information packet contents (model, firmware, serial)."""

    pack_serial_number: str | None = None
    model_number: str | None = None
    firmware_version: str | None = None


@dataclass(frozen=True)
class SpaConfiguration:
    """Configuration packet contents — installed hardware."""

    exhaust_fan: bool | None = None
    fogger: bool | None = None
    breaker_size: int | None = None
    pumps_installed: tuple[bool, ...] = field(default_factory=lambda: ())
    blowers_installed: tuple[bool, ...] = field(default_factory=lambda: ())
    heaters_installed: int | None = None  # 0, 1 or 2


@dataclass(frozen=True)
class SpaSnapshot:
    """Bundle of the most recent state, info, and configuration."""

    state: SpaState | None = None
    info: SpaInfo | None = None
    config: SpaConfiguration | None = None


def _config_unknown(snap: SpaSnapshot) -> bool:
    """When config is None at setup, fall back to creating every entity."""
    return snap.config is None


def has_pump(snap: SpaSnapshot, n: int) -> bool:
    if _config_unknown(snap):
        return 1 <= n <= 5
    if snap.state is None:
        return False
    return getattr(snap.state, f"pump_{n}", None) is not None


def has_blower(snap: SpaSnapshot, n: int) -> bool:
    if _config_unknown(snap):
        return 1 <= n <= 2
    if snap.state is None:
        return False
    return getattr(snap.state, f"blower_{n}", None) is not None


def has_lights(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.lights is not None


def has_onzen(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.onzen is not None


def has_ph_orp(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and (snap.state.ph is not None or snap.state.orp is not None)


def has_heater(snap: SpaSnapshot, n: int) -> bool:
    if _config_unknown(snap):
        return n in (1, 2)
    if snap.state is None:
        return False
    return getattr(snap.state, f"heater_{n}", None) is not None


def has_exhaust_fan(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    if snap.config is not None and snap.config.exhaust_fan:
        return True
    return snap.state is not None and snap.state.exhaust_fan is not None


def has_fogger(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    if snap.config is not None and snap.config.fogger:
        return True
    return snap.state is not None and snap.state.fogger is not None


def has_stereo(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.stereo is not None


def has_sauna(snap: SpaSnapshot) -> bool:
    if _config_unknown(snap):
        return True
    return snap.state is not None and snap.state.sauna is not None
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_models.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/models.py \
        tests/pyarcticspa/test_models.py
git commit -m "Add SpaSnapshot dataclasses and hardware-presence helpers"
```

---

### Task 7: Command builder

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/protocol/commands.py`
- Test: `tests/pyarcticspa/test_commands.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the SpaCommand builder."""

from custom_components.arctic_spa.pyarcticspa.protocol.commands import (
    build_command,
)
from custom_components.arctic_spa.pyarcticspa.proto import SpaCommand_pb2


def test_build_command_with_setpoint_returns_serialized_bytes() -> None:
    raw = build_command(set_temperature_setpoint_fahrenheit=102)
    msg = SpaCommand_pb2.spa_command()
    msg.ParseFromString(raw)
    assert msg.set_temperature_setpoint_fahrenheit == 102


def test_build_command_with_pump_select_value() -> None:
    raw = build_command(set_pump_1=2)
    msg = SpaCommand_pb2.spa_command()
    msg.ParseFromString(raw)
    assert msg.set_pump_1 == 2


def test_build_command_with_lights_on() -> None:
    raw = build_command(set_lights=1)
    msg = SpaCommand_pb2.spa_command()
    msg.ParseFromString(raw)
    assert msg.set_lights == 1


def test_build_command_with_onzen_boost() -> None:
    raw = build_command(set_onzen=1)
    msg = SpaCommand_pb2.spa_command()
    msg.ParseFromString(raw)
    assert msg.set_onzen == 1


def test_build_command_with_unknown_field_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown command field"):
        build_command(set_self_destruct=1)
```

- [ ] **Step 2: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_commands.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `commands.py`**

```python
"""Builders for outbound SpaCommand protobuf messages."""

from __future__ import annotations

from ..proto import SpaCommand_pb2

# Allow-list of fields callers may set. Keeps us from accidentally exposing
# unsafe fields (e.g. Onzen settings beyond the boost button).
_ALLOWED_FIELDS = frozenset(
    {
        "set_temperature_setpoint_fahrenheit",
        "set_pump_1",
        "set_pump_2",
        "set_pump_3",
        "set_pump_4",
        "set_pump_5",
        "set_blower_1",
        "set_blower_2",
        "set_lights",
        "set_onzen",  # boost only — this is the field SpaBoii ships
    }
)


def build_command(**fields: int) -> bytes:
    """Build and serialize a SpaCommand from the given field assignments."""
    unknown = set(fields) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"Unknown command field(s): {sorted(unknown)}")

    msg = SpaCommand_pb2.spa_command()
    for name, value in fields.items():
        setattr(msg, name, value)
    return msg.SerializeToString()
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_commands.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/protocol/commands.py \
        tests/pyarcticspa/test_commands.py
git commit -m "Add SpaCommand builder with field allow-list"
```

---

### Task 8: Snapshot decoder (proto bytes → dataclasses)

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/decoder.py`
- Test: `tests/pyarcticspa/test_decoder.py`

The decoder converts a parsed `LevvenPacket` (with protobuf payload) into the corresponding `SpaState` / `SpaInfo` / `SpaConfiguration` dataclass. Also handles the raw byte parsing of pH/ORP from INFORMATION packets and Cl Range from ONZEN_SETTINGS — these are not in the protobuf schema and SpaBoii reverse-engineered the byte offsets directly.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the LevvenPacket -> dataclass decoder."""

from custom_components.arctic_spa.pyarcticspa.decoder import (
    decode_configuration,
    decode_information,
    decode_live,
    decode_onzen_settings,
)
from custom_components.arctic_spa.pyarcticspa.models import HeaterStatus, PumpStatus
from custom_components.arctic_spa.pyarcticspa.proto import (
    SpaCommand_pb2,  # noqa: F401  (ensures proto package import side-effects)
    SpaInformation_pb2,
    spa_configuration_pb2,
    spa_live_pb2,
)


def test_decode_live_basic_fields() -> None:
    msg = spa_live_pb2.spa_live()
    msg.temperature_fahrenheit = 102
    msg.temperature_setpoint_fahrenheit = 104
    msg.pump_1 = spa_live_pb2.HIGH
    msg.lights = True
    msg.heater_1 = spa_live_pb2.HEATING

    state = decode_live(msg.SerializeToString())
    assert state.temperature_fahrenheit == 102
    assert state.temperature_setpoint_fahrenheit == 104
    assert state.pump_1 == PumpStatus.HIGH
    assert state.lights is True
    assert state.heater_1 == HeaterStatus.HEATING.value


def test_decode_live_unset_fields_are_none() -> None:
    msg = spa_live_pb2.spa_live()
    msg.temperature_fahrenheit = 100
    state = decode_live(msg.SerializeToString())
    assert state.temperature_fahrenheit == 100
    assert state.pump_1 is None
    assert state.lights is None


def test_decode_information_serial_and_model() -> None:
    msg = SpaInformation_pb2.spa_information()
    msg.pack_serial_number = "ABCD1234"
    info = decode_information(msg.SerializeToString())
    assert info.pack_serial_number == "ABCD1234"


def test_decode_information_extracts_ph_orp_from_raw_bytes() -> None:
    """SpaBoii observed pH/ORP values appended after the protobuf payload
    in INFORMATION packets >= 100 bytes. They are encoded as little-endian
    uint16: ORP at marker 0x10, pH at marker 0x18."""
    msg = SpaInformation_pb2.spa_information()
    msg.pack_serial_number = "X" * 100  # padding to ensure >= 100 bytes
    base = msg.SerializeToString()
    # Append: 0x10 <orp_lo> <orp_hi> 0x18 <ph_lo> <ph_hi>
    orp_raw = 1300  # -> 650.0 mV
    ph_raw = 1480   # -> 7.4
    suffix = bytes([0x10]) + orp_raw.to_bytes(2, "little") + bytes([0x18]) + ph_raw.to_bytes(2, "little")

    info, ph, orp = decode_information.parse_full(base + suffix)  # type: ignore[attr-defined]
    assert info.pack_serial_number == "X" * 100
    assert orp == 650.0
    assert ph == 7.4


def test_decode_configuration() -> None:
    msg = spa_configuration_pb2.spa_configuration()
    msg.exhaust_fan = True
    msg.fogger = False
    msg.breaker_size = 60
    config = decode_configuration(msg.SerializeToString())
    assert config.exhaust_fan is True
    assert config.fogger is False
    assert config.breaker_size == 60


def test_decode_onzen_settings_recognises_low_marker() -> None:
    payload = b"\x00\x00\xab\x04\x00"
    assert decode_onzen_settings(payload) == "Low"


def test_decode_onzen_settings_recognises_mid_marker() -> None:
    payload = b"\x00\x8f\x05\x00"
    assert decode_onzen_settings(payload) == "Mid"


def test_decode_onzen_settings_recognises_high_marker() -> None:
    payload = b"\x00\xf3\x05\x00"
    assert decode_onzen_settings(payload) == "High"


def test_decode_onzen_settings_returns_none_on_unrecognised() -> None:
    assert decode_onzen_settings(b"\x00\x99\x99\x00") is None
```

- [ ] **Step 2: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_decoder.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `decoder.py`**

```python
"""Decoders that turn protobuf bytes into Spa* dataclasses.

Also handles the non-protobuf data SpaBoii reverse-engineered:
- pH and ORP appended to INFORMATION packets above ~100 bytes
- Cl Range markers in ONZEN_SETTINGS packets
"""

from __future__ import annotations

from .models import PumpStatus, SpaConfiguration, SpaInfo, SpaState
from .proto import SpaInformation_pb2, spa_configuration_pb2, spa_live_pb2

_PUMP_STATUS_NAME = {
    spa_live_pb2.OFF: PumpStatus.OFF,
    spa_live_pb2.LOW: PumpStatus.LOW,
    spa_live_pb2.HIGH: PumpStatus.HIGH,
}


def _pump_status(msg: spa_live_pb2.spa_live, field: str) -> PumpStatus | None:
    if not msg.HasField(field):
        return None
    return _PUMP_STATUS_NAME.get(getattr(msg, field))


def _opt_bool(msg, field: str) -> bool | None:
    return getattr(msg, field) if msg.HasField(field) else None


def _opt_int(msg, field: str) -> int | None:
    return getattr(msg, field) if msg.HasField(field) else None


def _opt_enum_name(msg, field: str, enum_descriptor) -> str | None:
    if not msg.HasField(field):
        return None
    return enum_descriptor.values_by_number[getattr(msg, field)].name


def decode_live(payload: bytes) -> SpaState:
    msg = spa_live_pb2.spa_live()
    msg.ParseFromString(payload)
    ozone = _opt_enum_name(msg, "ozone", spa_live_pb2.OZONE_STATUS.DESCRIPTOR)
    if ozone is not None:
        ozone = ozone.removeprefix("OZONE_")
    return SpaState(
        temperature_fahrenheit=_opt_int(msg, "temperature_fahrenheit"),
        temperature_setpoint_fahrenheit=_opt_int(msg, "temperature_setpoint_fahrenheit"),
        pump_1=_pump_status(msg, "pump_1"),
        pump_2=_pump_status(msg, "pump_2"),
        pump_3=_pump_status(msg, "pump_3"),
        pump_4=_pump_status(msg, "pump_4"),
        pump_5=_pump_status(msg, "pump_5"),
        blower_1=_pump_status(msg, "blower_1"),
        blower_2=_pump_status(msg, "blower_2"),
        lights=_opt_bool(msg, "lights"),
        stereo=_opt_bool(msg, "stereo"),
        heater_1=_opt_enum_name(msg, "heater_1", spa_live_pb2.HEATER_STATUS.DESCRIPTOR),
        heater_2=_opt_enum_name(msg, "heater_2", spa_live_pb2.HEATER_STATUS.DESCRIPTOR),
        filter=_opt_enum_name(msg, "filter", spa_live_pb2.FILTER_STATUS.DESCRIPTOR),
        onzen=_opt_bool(msg, "onzen"),
        ozone=ozone,
        exhaust_fan=_opt_bool(msg, "exhaust_fan"),
        sauna=_opt_enum_name(msg, "sauna", spa_live_pb2.SAUNA_STATUS.DESCRIPTOR),
        heater_adc=_opt_int(msg, "heater_adc"),
        sauna_time_remaining=_opt_int(msg, "sauna_time_remaining"),
        economy=_opt_bool(msg, "economy"),
        current_adc=_opt_int(msg, "current_adc"),
        all_on=_opt_bool(msg, "all_on"),
        fogger=_opt_bool(msg, "fogger"),
    )


_ORP_MARKER = 0x10
_PH_MARKER = 0x18


def decode_information(payload: bytes) -> SpaInfo:
    msg = SpaInformation_pb2.spa_information()
    msg.ParseFromString(payload)
    return SpaInfo(
        pack_serial_number=msg.pack_serial_number or None,
        model_number=getattr(msg, "model_number", None) or None,
        firmware_version=getattr(msg, "firmware_version", None) or None,
    )


def _parse_information_full(payload: bytes) -> tuple[SpaInfo, float | None, float | None]:
    """Parse INFORMATION payload + optionally extract pH/ORP appended bytes.

    SpaBoii observation: when the INFORMATION packet is >= 100 bytes, the
    raw payload contains markers 0x10 (ORP) and 0x18 (pH) followed by a
    little-endian uint16. ORP raw / 2 = mV, pH raw / 200 = pH.
    """
    info = decode_information(payload)
    if len(payload) < 100:
        return info, None, None

    ph: float | None = None
    orp: float | None = None
    orp_idx = payload.find(bytes([_ORP_MARKER]))
    if orp_idx != -1 and len(payload) > orp_idx + 5:
        ph_idx = orp_idx + 3
        if payload[ph_idx] == _PH_MARKER:
            orp_raw = int.from_bytes(payload[orp_idx + 1 : orp_idx + 3], "little")
            ph_raw = int.from_bytes(payload[ph_idx + 1 : ph_idx + 3], "little")
            orp = orp_raw / 2.0
            ph = ph_raw / 200.0
    return info, ph, orp


# Expose parse_full as an attribute on decode_information for the test API.
decode_information.parse_full = _parse_information_full  # type: ignore[attr-defined]


def decode_configuration(payload: bytes) -> SpaConfiguration:
    msg = spa_configuration_pb2.spa_configuration()
    msg.ParseFromString(payload)
    return SpaConfiguration(
        exhaust_fan=_opt_bool(msg, "exhaust_fan"),
        fogger=_opt_bool(msg, "fogger"),
        breaker_size=_opt_int(msg, "breaker_size"),
    )


_ONZEN_MARKERS: dict[bytes, str] = {
    b"\xab\x04": "Low",
    b"\xa1\x04": "Low",
    b"\x8f\x05": "Mid",
    b"\x85\x05": "Mid",
    b"\xf3\x05": "High",
    b"\xe9\x05": "High",
}


def decode_onzen_settings(payload: bytes) -> str | None:
    """Extract the Cl Range setting from an ONZEN_SETTINGS packet payload."""
    for marker, label in _ONZEN_MARKERS.items():
        if marker in payload:
            return label
    return None
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_decoder.py -v
```

Expected: 9 passed. (Some specific protobuf field-name access may differ slightly per regenerated proto — adjust the decoder's `getattr` paths if needed.)

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/decoder.py \
        tests/pyarcticspa/test_decoder.py
git commit -m "Add packet payload decoder for SpaState/SpaInfo/SpaConfiguration"
```

---

### Task 9: Async SpaClient — connect, read, send, callbacks

**Files:**
- Create: `custom_components/arctic_spa/pyarcticspa/client.py`
- Test: `tests/pyarcticspa/test_client.py`

This is the central piece. The test uses `asyncio.start_server` to run a fake spa locally, then drives the client against it.

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the asyncio SpaClient."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from custom_components.arctic_spa.pyarcticspa.client import SpaClient
from custom_components.arctic_spa.pyarcticspa.protocol.messages import MessageType
from custom_components.arctic_spa.pyarcticspa.protocol.packet import LevvenPacket
from custom_components.arctic_spa.pyarcticspa.proto import (
    SpaInformation_pb2,
    spa_live_pb2,
)


def _live_packet(temp_f: int) -> bytes:
    msg = spa_live_pb2.spa_live()
    msg.temperature_fahrenheit = temp_f
    return LevvenPacket(MessageType.LIVE, msg.SerializeToString()).serialize()


def _info_packet(serial: str) -> bytes:
    msg = SpaInformation_pb2.spa_information()
    msg.pack_serial_number = serial
    return LevvenPacket(MessageType.INFORMATION, msg.SerializeToString()).serialize()


@asynccontextmanager
async def fake_spa(handler):
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield port


@pytest.mark.asyncio
async def test_client_receives_live_state_via_callback() -> None:
    states_received: list = []
    received_event = asyncio.Event()

    async def server_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Read the first ping (any), then push a LIVE packet
        await reader.read(1024)
        writer.write(_live_packet(102))
        await writer.drain()
        # Hold the connection open until the test releases it
        try:
            await reader.read(1024)
        finally:
            writer.close()

    async with fake_spa(server_handler) as port:
        client = SpaClient(host="127.0.0.1", port=port, scan_interval=0.05)

        def on_state(s):
            states_received.append(s)
            received_event.set()

        client.on_state = on_state
        await client.start()
        await asyncio.wait_for(received_event.wait(), timeout=2.0)
        await client.stop()

    assert len(states_received) >= 1
    assert states_received[0].temperature_fahrenheit == 102


@pytest.mark.asyncio
async def test_probe_once_returns_serial_after_information_packet() -> None:
    async def server_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read(1024)
        writer.write(_info_packet("SERIAL-1"))
        await writer.drain()
        await asyncio.sleep(0.5)
        writer.close()

    async with fake_spa(server_handler) as port:
        client = SpaClient(host="127.0.0.1", port=port)
        info = await client.probe_once(timeout=2.0)
        assert info.pack_serial_number == "SERIAL-1"


@pytest.mark.asyncio
async def test_probe_once_raises_on_timeout_when_server_silent() -> None:
    async def server_handler(reader, writer) -> None:
        await asyncio.sleep(5.0)
        writer.close()

    async with fake_spa(server_handler) as port:
        client = SpaClient(host="127.0.0.1", port=port)
        with pytest.raises(TimeoutError):
            await client.probe_once(timeout=0.3)


@pytest.mark.asyncio
async def test_send_command_writes_command_packet_to_socket() -> None:
    bytes_received = bytearray()
    received_event = asyncio.Event()

    async def server_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # First read: incoming pings
        try:
            while True:
                chunk = await reader.read(1024)
                if not chunk:
                    break
                bytes_received.extend(chunk)
                if any(b == MessageType.COMMAND for b in chunk[16:18]) or len(bytes_received) > 80:
                    received_event.set()
        except asyncio.CancelledError:
            raise
        finally:
            writer.close()

    async with fake_spa(server_handler) as port:
        client = SpaClient(host="127.0.0.1", port=port, scan_interval=0.1)
        await client.start()
        # Wait briefly to ensure connection
        await asyncio.sleep(0.3)
        await client.send_command_raw(MessageType.COMMAND, b"\x42\x42")
        await asyncio.wait_for(received_event.wait(), timeout=2.0)
        await client.stop()

    assert b"\xab\xad\x1d\x3a" in bytes_received  # at least one Levven magic seen
```

- [ ] **Step 2: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_client.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `client.py`**

```python
"""Asynchronous TCP client for the Arctic Spa Levven protocol.

Holds a persistent connection, drives ping cadence (LIVE / CONFIGURATION /
INFORMATION), parses inbound packets, and exposes parsed snapshots via
caller-supplied callbacks. Reconnects with exponential backoff on failure.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from .decoder import (
    _parse_information_full,
    decode_configuration,
    decode_live,
    decode_onzen_settings,
)
from .models import SpaConfiguration, SpaInfo, SpaState
from .protocol.messages import MessageType
from .protocol.packet import LevvenPacket
from .protocol.parser import StreamParser

_LOGGER = logging.getLogger(__name__)


StateCallback = Callable[[SpaState], None]
InfoCallback = Callable[[SpaInfo], None]
ConfigCallback = Callable[[SpaConfiguration], None]
ConnectCallback = Callable[[], None]
DisconnectCallback = Callable[[Exception | None], None]


class SpaClient:
    """Persistent async TCP client for one Arctic Spa."""

    def __init__(
        self,
        host: str,
        port: int = 65534,
        *,
        scan_interval: float = 2.0,
        info_interval_ticks: int = 4,
        connect_timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self._scan_interval = scan_interval
        self._info_interval_ticks = max(1, info_interval_ticks)
        self._connect_timeout = connect_timeout

        self.on_state: StateCallback | None = None
        self.on_info: InfoCallback | None = None
        self.on_config: ConfigCallback | None = None
        self.on_connect: ConnectCallback | None = None
        self.on_disconnect: DisconnectCallback | None = None

        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._writer: asyncio.StreamWriter | None = None
        self._send_lock = asyncio.Lock()

        self.connect_count = 0
        self.crc_failure_count = 0
        self.last_error: Exception | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_forever(), name=f"arctic_spa[{self.host}]")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:  # noqa: BLE001
                pass
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    async def _run_forever(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            connection_started = asyncio.get_running_loop().time()
            try:
                await self._connect_and_run()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.last_error = exc
                _LOGGER.warning("Arctic Spa %s: connection lost: %s", self.host, exc)
                if self.on_disconnect is not None:
                    self.on_disconnect(exc)

            duration = asyncio.get_running_loop().time() - connection_started
            if duration > 30:
                backoff = 1.0
            else:
                backoff = min(backoff * 2, 60.0)

            if self._stop_event.is_set():
                return
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                return
            except TimeoutError:
                pass

    async def _connect_and_run(self) -> None:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self._connect_timeout,
        )
        self._writer = writer
        self.connect_count += 1
        if self.on_connect is not None:
            self.on_connect()

        parser = StreamParser()
        ping_task = asyncio.create_task(self._ping_loop(writer))
        try:
            while not self._stop_event.is_set():
                chunk = await reader.read(2048)
                if not chunk:
                    raise ConnectionError("connection closed by spa")
                for packet in parser.feed(chunk):
                    self._dispatch(packet)
        finally:
            ping_task.cancel()
            try:
                await ping_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            self._writer = None

    async def _ping_loop(self, writer: asyncio.StreamWriter) -> None:
        i = 0
        try:
            while not self._stop_event.is_set():
                if i == 0:
                    await self._write_ping(writer, MessageType.CONFIGURATION)
                elif i % self._info_interval_ticks == 0:
                    await self._write_ping(writer, MessageType.INFORMATION)
                else:
                    await self._write_ping(writer, MessageType.LIVE)
                i += 1
                await asyncio.sleep(self._scan_interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Ping loop ended: %s", exc)

    async def _write_ping(self, writer: asyncio.StreamWriter, mtype: MessageType) -> None:
        await self._write(writer, LevvenPacket(mtype, b"").serialize())

    async def _write(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        async with self._send_lock:
            writer.write(data)
            await writer.drain()

    def _dispatch(self, packet: LevvenPacket) -> None:
        if packet.type == MessageType.LIVE:
            try:
                state = decode_live(bytes(packet.payload))
            except Exception:  # noqa: BLE001
                self.crc_failure_count += 1
                _LOGGER.debug("Failed to decode LIVE payload", exc_info=True)
                return
            if self.on_state is not None:
                self.on_state(state)
        elif packet.type == MessageType.INFORMATION:
            try:
                info, ph, orp = _parse_information_full(bytes(packet.payload))
            except Exception:  # noqa: BLE001
                self.crc_failure_count += 1
                return
            if self.on_info is not None:
                self.on_info(info)
            if (ph is not None or orp is not None) and self.on_state is not None:
                # Inject pH/ORP via a state delta: callers merge into latest state.
                self.on_state(SpaState(ph=ph, orp=orp))
        elif packet.type == MessageType.CONFIGURATION:
            try:
                config = decode_configuration(bytes(packet.payload))
            except Exception:  # noqa: BLE001
                return
            if self.on_config is not None:
                self.on_config(config)
        elif packet.type == MessageType.ONZEN_SETTINGS:
            cl_range = decode_onzen_settings(bytes(packet.payload))
            if cl_range is not None and self.on_state is not None:
                self.on_state(SpaState(cl_range=cl_range))
        # PING and unknown types: ignore

    async def send_command_raw(self, mtype: MessageType, payload: bytes) -> None:
        """Send an arbitrary Levven packet. Used by tests and send_command."""
        if self._writer is None:
            raise ConnectionError("not connected")
        await self._write(self._writer, LevvenPacket(mtype, payload).serialize())

    async def send_command(self, payload: bytes) -> None:
        """Send a serialized SpaCommand protobuf."""
        await self.send_command_raw(MessageType.COMMAND, payload)

    async def probe_once(self, timeout: float = 10.0) -> SpaInfo:
        """One-shot connect → request INFORMATION → return → disconnect."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self._connect_timeout,
        )
        try:
            # Send INFORMATION ping immediately
            writer.write(LevvenPacket(MessageType.INFORMATION, b"").serialize())
            await writer.drain()

            parser = StreamParser()
            deadline = asyncio.get_running_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError("probe timed out waiting for INFORMATION packet")
                try:
                    chunk = await asyncio.wait_for(reader.read(2048), timeout=remaining)
                except TimeoutError:
                    raise TimeoutError("probe timed out waiting for INFORMATION packet")
                if not chunk:
                    raise ConnectionError("spa closed connection during probe")
                for packet in parser.feed(chunk):
                    if packet.type == MessageType.INFORMATION:
                        info, _ph, _orp = _parse_information_full(bytes(packet.payload))
                        if info.pack_serial_number:
                            return info
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/pyarcticspa/test_client.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/client.py \
        tests/pyarcticspa/test_client.py
git commit -m "Add async SpaClient with reconnect, ping cadence, and probe_once"
```

---

### Task 10: pyarcticspa public API (`__init__.py`) and CLI tools

**Files:**
- Modify: `custom_components/arctic_spa/pyarcticspa/__init__.py`
- Create: `custom_components/arctic_spa/pyarcticspa/__main__.py`
- Create: `custom_components/arctic_spa/pyarcticspa/replay.py`

- [ ] **Step 1: Populate `__init__.py`**

```python
"""Arctic Spa local protocol client (vendored library).

Public API:
    SpaClient(host, port=65534, scan_interval=2.0, info_interval_ticks=4)
    SpaState, SpaInfo, SpaConfiguration, SpaSnapshot
    PumpStatus, HeaterStatus
    has_pump, has_blower, has_lights, has_onzen, has_ph_orp,
    has_heater, has_exhaust_fan, has_fogger, has_stereo, has_sauna
    build_command(**fields)
"""

from .client import SpaClient
from .models import (
    HeaterStatus,
    PumpStatus,
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
    has_blower,
    has_exhaust_fan,
    has_fogger,
    has_heater,
    has_lights,
    has_onzen,
    has_ph_orp,
    has_pump,
    has_sauna,
    has_stereo,
)
from .protocol.commands import build_command

__all__ = [
    "HeaterStatus",
    "PumpStatus",
    "SpaClient",
    "SpaConfiguration",
    "SpaInfo",
    "SpaSnapshot",
    "SpaState",
    "build_command",
    "has_blower",
    "has_exhaust_fan",
    "has_fogger",
    "has_heater",
    "has_lights",
    "has_onzen",
    "has_ph_orp",
    "has_pump",
    "has_sauna",
    "has_stereo",
]
```

- [ ] **Step 2: Create `__main__.py` (live-dump CLI)**

```python
"""Live packet dump tool: python -m pyarcticspa <ip>."""

from __future__ import annotations

import asyncio
import logging
import sys

from .client import SpaClient


async def _run(host: str) -> None:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

    def on_state(state):
        print(f"STATE: {state}")  # noqa: T201

    def on_info(info):
        print(f"INFO:  {info}")  # noqa: T201

    def on_config(config):
        print(f"CFG:   {config}")  # noqa: T201

    client = SpaClient(host)
    client.on_state = on_state
    client.on_info = on_info
    client.on_config = on_config
    await client.start()
    try:
        await asyncio.Event().wait()
    finally:
        await client.stop()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m pyarcticspa <spa-ip>", file=sys.stderr)  # noqa: T201
        sys.exit(2)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `replay.py` (offline capture replay)**

```python
"""Replay tool: python -m pyarcticspa.replay <capture-file>.

Reads a binary file containing one or more raw Levven packets back-to-back
and prints the parsed contents.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .decoder import decode_configuration, decode_live, decode_onzen_settings
from .protocol.messages import MessageType
from .protocol.parser import StreamParser


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m pyarcticspa.replay <capture-file>", file=sys.stderr)  # noqa: T201
        sys.exit(2)
    raw = Path(sys.argv[1]).read_bytes()
    parser = StreamParser()
    for packet in parser.feed(raw):
        name = MessageType.title(packet.type)
        if packet.type == MessageType.LIVE:
            print(name, decode_live(bytes(packet.payload)))  # noqa: T201
        elif packet.type == MessageType.CONFIGURATION:
            print(name, decode_configuration(bytes(packet.payload)))  # noqa: T201
        elif packet.type == MessageType.ONZEN_SETTINGS:
            print(name, decode_onzen_settings(bytes(packet.payload)))  # noqa: T201
        else:
            print(name, len(packet.payload), "bytes")  # noqa: T201


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify import roundtrip**

```bash
PYTHONPATH=custom_components/arctic_spa python -c "
import pyarcticspa
print(pyarcticspa.__all__)
print(pyarcticspa.SpaClient.__module__)
"
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/pyarcticspa/__init__.py \
        custom_components/arctic_spa/pyarcticspa/__main__.py \
        custom_components/arctic_spa/pyarcticspa/replay.py
git commit -m "Expose pyarcticspa public API and add CLI tools"
```

---

## Phase 3: HA integration shell

From here on, tests use `pytest-homeassistant-custom-component`. Install it:

```bash
pip install pytest-homeassistant-custom-component homeassistant
```

### Task 11: manifest.json, const.py, strings.json

**Files:**
- Create: `custom_components/arctic_spa/manifest.json`
- Create: `custom_components/arctic_spa/const.py`
- Create: `custom_components/arctic_spa/strings.json`
- Create: `custom_components/arctic_spa/translations/en.json`

- [ ] **Step 1: Create `manifest.json`**

```json
{
  "domain": "arctic_spa",
  "name": "Arctic Spa",
  "version": "0.1.0",
  "config_flow": true,
  "integration_type": "device",
  "iot_class": "local_push",
  "documentation": "https://github.com/jeff/ha-arctic-spa",
  "issue_tracker": "https://github.com/jeff/ha-arctic-spa/issues",
  "codeowners": ["@jeff"],
  "requirements": ["protobuf>=4.21,<6"],
  "dhcp": []
}
```

- [ ] **Step 2: Create `const.py`**

```python
"""Constants for the Arctic Spa integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "arctic_spa"
MANUFACTURER: Final = "Arctic Spa"
DEFAULT_NAME: Final = "Arctic Spa"
DEFAULT_PORT: Final = 65534

CONF_HOST: Final = "host"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_INFO_INTERVAL_TICKS: Final = "info_interval_ticks"
CONF_TEMPERATURE_UNIT: Final = "temperature_unit"

DEFAULT_SCAN_INTERVAL: Final = 2.0
DEFAULT_INFO_INTERVAL_TICKS: Final = 4
DEFAULT_TEMPERATURE_UNIT: Final = "F"

MIN_SETPOINT_F: Final = 80
MAX_SETPOINT_F: Final = 104
```

- [ ] **Step 3: Create `strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Arctic Spa",
        "description": "Enter your spa's local IP address.",
        "data": {
          "host": "Spa IP address",
          "name": "Name"
        }
      },
      "reconfigure": {
        "title": "Reconfigure Arctic Spa",
        "description": "Update the IP address of this spa.",
        "data": {
          "host": "Spa IP address"
        }
      }
    },
    "error": {
      "cannot_connect": "Could not connect to the spa.",
      "invalid_response": "Connected, but did not receive a valid spa response.",
      "no_serial": "Connected, but the spa did not report a serial number.",
      "wrong_spa": "The IP responds, but it is a different spa than this entry."
    },
    "abort": {
      "already_configured": "This spa is already configured.",
      "reconfigure_successful": "Spa configuration updated."
    }
  },
  "options": {
    "step": {
      "init": {
        "data": {
          "scan_interval": "Live update interval (seconds)",
          "info_interval_ticks": "Information packets every N ticks",
          "temperature_unit": "Temperature unit"
        }
      }
    }
  }
}
```

- [ ] **Step 4: Create `translations/en.json` (mirror of strings.json)**

```bash
mkdir -p custom_components/arctic_spa/translations
cp custom_components/arctic_spa/strings.json custom_components/arctic_spa/translations/en.json
```

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/manifest.json \
        custom_components/arctic_spa/const.py \
        custom_components/arctic_spa/strings.json \
        custom_components/arctic_spa/translations/en.json
git commit -m "Add integration manifest, constants, and UI strings"
```

---

### Task 12: Coordinator

**Files:**
- Create: `custom_components/arctic_spa/coordinator.py`
- Test: `tests/components/arctic_spa/__init__.py` (empty)
- Test: `tests/components/__init__.py` (empty)
- Test: `tests/components/arctic_spa/conftest.py`
- Test: `tests/components/arctic_spa/test_coordinator.py`

- [ ] **Step 1: Create `__init__.py` files**

```bash
mkdir -p tests/components/arctic_spa
touch tests/components/__init__.py tests/components/arctic_spa/__init__.py
```

- [ ] **Step 2: Create `conftest.py`**

```python
"""Shared fixtures for Arctic Spa tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.arctic_spa.pyarcticspa.models import (
    SpaConfiguration,
    SpaInfo,
    SpaState,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Required by pytest-homeassistant-custom-component."""
    yield


@pytest.fixture
def mock_spa_info() -> SpaInfo:
    return SpaInfo(
        pack_serial_number="SERIAL-1234",
        model_number="Cub Elite",
        firmware_version="1.2.3",
    )


@pytest.fixture
def mock_spa_state() -> SpaState:
    return SpaState(
        temperature_fahrenheit=102,
        temperature_setpoint_fahrenheit=104,
        heater_1="HEATING",
        lights=False,
    )


@pytest.fixture
def mock_spa_config() -> SpaConfiguration:
    return SpaConfiguration(exhaust_fan=False, fogger=False, breaker_size=60)


@pytest.fixture
def mock_client(mock_spa_info, mock_spa_state, mock_spa_config) -> Generator[MagicMock, None, None]:
    client = MagicMock()
    client.host = "192.0.2.50"
    client.port = 65534
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.send_command = AsyncMock()
    client.probe_once = AsyncMock(return_value=mock_spa_info)
    client._stored_callbacks = {}
    yield client
```

- [ ] **Step 3: Write the failing coordinator test**

```python
"""Tests for ArcticSpaCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.coordinator import ArcticSpaCoordinator
from custom_components.arctic_spa.pyarcticspa.models import SpaState


@pytest.mark.asyncio
async def test_coordinator_handle_state_updates_data(
    hass: HomeAssistant, mock_client, mock_spa_info, mock_spa_state, mock_spa_config
) -> None:
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Spa",
        data={"host": "192.0.2.50"},
        source="user",
        options={},
        unique_id="SERIAL-1234",
        discovery_keys={},
        subentries_data=(),
    )
    coord = ArcticSpaCoordinator(hass, entry, mock_client)

    # Wire callbacks (the coordinator does this in __init__; verify they are set)
    assert mock_client.on_state is not None
    assert mock_client.on_info is not None
    assert mock_client.on_config is not None

    # Simulate the client pushing an info packet first, then a state
    mock_client.on_info(mock_spa_info)
    mock_client.on_config(mock_spa_config)
    mock_client.on_state(mock_spa_state)

    assert coord.data is not None
    assert coord.data.state.temperature_fahrenheit == 102
    assert coord.data.info.pack_serial_number == "SERIAL-1234"
    assert coord.data.config.breaker_size == 60


@pytest.mark.asyncio
async def test_coordinator_state_partial_update_merges(
    hass: HomeAssistant, mock_client, mock_spa_state
) -> None:
    entry = ConfigEntry(
        version=1, minor_version=1, domain=DOMAIN, title="Spa",
        data={"host": "192.0.2.50"}, source="user", options={},
        unique_id="SERIAL-1234", discovery_keys={}, subentries_data=(),
    )
    coord = ArcticSpaCoordinator(hass, entry, mock_client)
    mock_client.on_state(mock_spa_state)
    # pH/ORP is delivered as a SpaState with only those fields set;
    # coordinator must merge rather than replace.
    mock_client.on_state(SpaState(ph=7.4, orp=650.0))

    assert coord.data.state.temperature_fahrenheit == 102  # preserved
    assert coord.data.state.ph == 7.4
    assert coord.data.state.orp == 650.0


@pytest.mark.asyncio
async def test_coordinator_disconnect_marks_failure(
    hass: HomeAssistant, mock_client, mock_spa_state
) -> None:
    entry = ConfigEntry(
        version=1, minor_version=1, domain=DOMAIN, title="Spa",
        data={"host": "192.0.2.50"}, source="user", options={},
        unique_id="SERIAL-1234", discovery_keys={}, subentries_data=(),
    )
    coord = ArcticSpaCoordinator(hass, entry, mock_client)
    mock_client.on_state(mock_spa_state)
    assert coord.last_update_success is True

    mock_client.on_disconnect(ConnectionError("boom"))
    assert coord.last_update_success is False
```

- [ ] **Step 4: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_coordinator.py -v
```

Expected: ImportError.

- [ ] **Step 5: Create `coordinator.py`**

```python
"""Coordinator that owns the SpaClient and pushes updates to entities."""

from __future__ import annotations

import logging
from dataclasses import replace

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .pyarcticspa import (
    SpaClient,
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
)

_LOGGER = logging.getLogger(__name__)


def _merge_states(old: SpaState | None, new: SpaState) -> SpaState:
    """Merge a partial state delta on top of the existing state."""
    if old is None:
        return new
    fields: dict[str, object] = {}
    for f in new.__dataclass_fields__:
        value = getattr(new, f)
        if value is not None:
            fields[f] = value
    return replace(old, **fields)  # type: ignore[arg-type]


class ArcticSpaCoordinator(DataUpdateCoordinator[SpaSnapshot]):
    """Push-driven coordinator for one Arctic Spa config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SpaClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}@{entry.data['host']}",
            update_interval=None,  # push-driven
        )
        self.entry = entry
        self.client = client
        self.data = SpaSnapshot()  # type: ignore[assignment]

        client.on_state = self._handle_state
        client.on_info = self._handle_info
        client.on_config = self._handle_config
        client.on_connect = self._handle_connect
        client.on_disconnect = self._handle_disconnect

    @callback
    def _handle_state(self, state: SpaState) -> None:
        merged = _merge_states(self.data.state if self.data else None, state)
        new_snapshot = SpaSnapshot(
            state=merged,
            info=self.data.info if self.data else None,
            config=self.data.config if self.data else None,
        )
        self.async_set_updated_data(new_snapshot)

    @callback
    def _handle_info(self, info: SpaInfo) -> None:
        new_snapshot = SpaSnapshot(
            state=self.data.state if self.data else None,
            info=info,
            config=self.data.config if self.data else None,
        )
        self.async_set_updated_data(new_snapshot)

    @callback
    def _handle_config(self, config: SpaConfiguration) -> None:
        new_snapshot = SpaSnapshot(
            state=self.data.state if self.data else None,
            info=self.data.info if self.data else None,
            config=config,
        )
        self.async_set_updated_data(new_snapshot)

    @callback
    def _handle_connect(self) -> None:
        _LOGGER.info("Arctic Spa %s: connected", self.entry.data["host"])

    @callback
    def _handle_disconnect(self, exc: Exception | None) -> None:
        self.async_set_update_error(exc or ConnectionError("disconnected"))

    async def _async_update_data(self) -> SpaSnapshot:
        # Push-driven; this is invoked by async_config_entry_first_refresh
        # before the listeners are wired. We just return whatever is in self.data.
        if self.data is None:
            return SpaSnapshot()
        return self.data

    async def send_command(self, payload: bytes) -> None:
        if not self.last_update_success:
            raise HomeAssistantError("Spa is not connected")
        await self.client.send_command(payload)
```

- [ ] **Step 6: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_coordinator.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add custom_components/arctic_spa/coordinator.py \
        tests/components/__init__.py \
        tests/components/arctic_spa/__init__.py \
        tests/components/arctic_spa/conftest.py \
        tests/components/arctic_spa/test_coordinator.py
git commit -m "Add ArcticSpaCoordinator with state merge and disconnect handling"
```

---

### Task 13: Config flow (user step + reconfigure + options)

**Files:**
- Create: `custom_components/arctic_spa/config_flow.py`
- Test: `tests/components/arctic_spa/test_config_flow.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for Arctic Spa config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import SpaInfo


@pytest.mark.asyncio
async def test_user_flow_happy_path_creates_entry(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.arctic_spa.config_flow.SpaClient.probe_once",
        new=AsyncMock(return_value=SpaInfo(pack_serial_number="ABC-123", model_number="Cub")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.50", "name": "Hot Tub"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Hot Tub"
        assert result["data"]["host"] == "192.0.2.50"
        assert result["result"].unique_id == "ABC-123"


@pytest.mark.asyncio
async def test_user_flow_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.arctic_spa.config_flow.SpaClient.probe_once",
        new=AsyncMock(side_effect=ConnectionError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.50"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_no_serial_shows_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.arctic_spa.config_flow.SpaClient.probe_once",
        new=AsyncMock(return_value=SpaInfo(pack_serial_number=None)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.50"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_serial"}


@pytest.mark.asyncio
async def test_user_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    MockConfigEntry(domain=DOMAIN, unique_id="ABC-123", data={"host": "192.0.2.50"}).add_to_hass(hass)

    with patch(
        "custom_components.arctic_spa.config_flow.SpaClient.probe_once",
        new=AsyncMock(return_value=SpaInfo(pack_serial_number="ABC-123")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.99"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
```

- [ ] **Step 2: Run test — expect failure**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_config_flow.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `config_flow.py`**

```python
"""Config flow for Arctic Spa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_HOST,
    CONF_INFO_INTERVAL_TICKS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TEMPERATURE_UNIT,
    DEFAULT_INFO_INTERVAL_TICKS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TEMPERATURE_UNIT,
    DOMAIN,
)
from .pyarcticspa import SpaClient

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

_RECONFIGURE_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class ArcticSpaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            try:
                info = await SpaClient(host=host).probe_once(timeout=10.0)
            except TimeoutError:
                errors["base"] = "invalid_response"
            except (ConnectionError, OSError):
                errors["base"] = "cannot_connect"
            else:
                if not info.pack_serial_number:
                    errors["base"] = "no_serial"
                else:
                    await self.async_set_unique_id(info.pack_serial_number)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    return self.async_create_entry(
                        title=name, data={CONF_HOST: host}
                    )
        return self.async_show_form(
            step_id="user", data_schema=_USER_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                info = await SpaClient(host=host).probe_once(timeout=10.0)
            except TimeoutError:
                errors["base"] = "invalid_response"
            except (ConnectionError, OSError):
                errors["base"] = "cannot_connect"
            else:
                if info.pack_serial_number != entry.unique_id:
                    errors["base"] = "wrong_spa"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_HOST: host}
                    )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_RECONFIGURE_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ArcticSpaOptionsFlow()


class ArcticSpaOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=10.0)),
                vol.Optional(
                    CONF_INFO_INTERVAL_TICKS,
                    default=current.get(
                        CONF_INFO_INTERVAL_TICKS, DEFAULT_INFO_INTERVAL_TICKS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
                vol.Optional(
                    CONF_TEMPERATURE_UNIT,
                    default=current.get(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT),
                ): vol.In(["F", "C"]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_config_flow.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/config_flow.py \
        tests/components/arctic_spa/test_config_flow.py
git commit -m "Add config flow with user, reconfigure, and options steps"
```

---

### Task 14: `__init__.py` setup/unload, base entity

**Files:**
- Create: `custom_components/arctic_spa/__init__.py`
- Create: `custom_components/arctic_spa/entity.py`
- Test: `tests/components/arctic_spa/test_init.py`

- [ ] **Step 1: Create `entity.py`**

```python
"""Base entity for the Arctic Spa integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ArcticSpaCoordinator
from .pyarcticspa import SpaState


class ArcticSpaEntity(CoordinatorEntity[ArcticSpaCoordinator]):
    """Base entity for one Arctic Spa device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArcticSpaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        unique_id = coordinator.entry.unique_id or coordinator.entry.entry_id
        self._attr_unique_id = f"{unique_id}_{key}"
        info = coordinator.data.info if coordinator.data else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            model=(info.model_number if info else None) or "Arctic Spa",
            sw_version=info.firmware_version if info else None,
            name=coordinator.entry.title,
        )

    @property
    def _state(self) -> SpaState | None:
        return self.coordinator.data.state if self.coordinator.data else None
```

- [ ] **Step 2: Create `__init__.py`**

```python
"""Arctic Spa integration entry point."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_HOST,
    CONF_INFO_INTERVAL_TICKS,
    CONF_SCAN_INTERVAL,
    DEFAULT_INFO_INTERVAL_TICKS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import ArcticSpaCoordinator
from .pyarcticspa import SpaClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = SpaClient(
        host=entry.data[CONF_HOST],
        scan_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        info_interval_ticks=entry.options.get(
            CONF_INFO_INTERVAL_TICKS, DEFAULT_INFO_INTERVAL_TICKS
        ),
    )
    coordinator = ArcticSpaCoordinator(hass, entry, client)
    await client.start()
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        await client.stop()
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await coordinator.client.stop()
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
```

- [ ] **Step 3: Write the failing test**

```python
"""Tests for the Arctic Spa integration setup/unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_entry_creates_coordinator(hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL-1234", data={"host": "192.0.2.50"})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_unload_entry_stops_client(hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL-1234", data={"host": "192.0.2.50"})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
    mock_client.stop.assert_awaited()
```

- [ ] **Step 4: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_init.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/arctic_spa/__init__.py \
        custom_components/arctic_spa/entity.py \
        tests/components/arctic_spa/test_init.py
git commit -m "Add integration entry-point and base entity"
```

---

## Phase 4: Platforms

Each platform is a small file. The platform's `async_setup_entry` reads the snapshot, decides which entities to create using `has_*` helpers, and registers them. State changes drive entity updates via `CoordinatorEntity._handle_coordinator_update`.

### Task 15: Climate platform

**Files:**
- Create: `custom_components/arctic_spa/climate.py`
- Test: `tests/components/arctic_spa/test_climate.py`

- [ ] **Step 1: Create `climate.py`**

```python
"""Climate platform for Arctic Spa."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_SETPOINT_F, MIN_SETPOINT_F
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import build_command


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ArcticSpaClimate(coordinator)])


class ArcticSpaClimate(ArcticSpaEntity, ClimateEntity):
    _attr_name = None  # primary entity inherits device name
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = MIN_SETPOINT_F
    _attr_max_temp = MAX_SETPOINT_F
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="climate")

    @property
    def current_temperature(self) -> float | None:
        return self._state.temperature_fahrenheit if self._state else None

    @property
    def target_temperature(self) -> float | None:
        return self._state.temperature_setpoint_fahrenheit if self._state else None

    @property
    def hvac_action(self) -> HVACAction:
        if self._state is None:
            return HVACAction.IDLE
        if self._state.heater_1 in ("HEATING", "WARMUP") or self._state.heater_2 in (
            "HEATING",
            "WARMUP",
        ):
            return HVACAction.HEATING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        target = kwargs.get("temperature")
        if target is None:
            return
        await self.coordinator.send_command(
            build_command(set_temperature_setpoint_fahrenheit=int(round(target)))
        )
```

- [ ] **Step 2: Write the test**

```python
"""Tests for ArcticSpaClimate."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import SpaSnapshot, SpaState, SpaInfo


@pytest.mark.asyncio
async def test_climate_state_reflects_snapshot(hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL-1234", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)

    snapshot = SpaSnapshot(
        state=SpaState(temperature_fahrenheit=101, temperature_setpoint_fahrenheit=104, heater_1="HEATING"),
        info=SpaInfo(pack_serial_number="SERIAL-1234", model_number="Cub"),
        config=None,
    )

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=lambda: _seed(hass, entry.entry_id, snapshot)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.spa")
    assert state is not None
    assert state.attributes["current_temperature"] == 101
    assert state.attributes["temperature"] == 104
    assert state.attributes["hvac_action"] == "heating"


@pytest.mark.asyncio
async def test_climate_set_temperature_sends_command(hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL-1234", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(temperature_fahrenheit=100, temperature_setpoint_fahrenheit=100),
        info=SpaInfo(pack_serial_number="SERIAL-1234"),
        config=None,
    )
    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=lambda: _seed(hass, entry.entry_id, snapshot)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.spa", ATTR_TEMPERATURE: 103},
            blocking=True,
        )

    mock_client.send_command.assert_awaited()


def _seed(hass: HomeAssistant, entry_id: str, snapshot: SpaSnapshot) -> None:
    """Helper used inside the patched first_refresh: seed the coordinator with a snapshot."""
    coord = hass.data[DOMAIN][entry_id]
    coord.data = snapshot
    coord.last_update_success = True
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_climate.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/climate.py \
        tests/components/arctic_spa/test_climate.py
git commit -m "Add climate platform for current/target temperature and heating action"
```

---

### Task 16: Sensor platform

Sensors: filter status, ozone status, heater_n status (diagnostic), heater ADC, current ADC, pH, ORP, Cl Range.

**Files:**
- Create: `custom_components/arctic_spa/sensor.py`
- Test: `tests/components/arctic_spa/test_sensor.py`

- [ ] **Step 1: Create `sensor.py`**

```python
"""Sensor platform for Arctic Spa."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import (
    SpaSnapshot,
    SpaState,
    has_heater,
    has_onzen,
    has_ph_orp,
)


@dataclass(frozen=True)
class _SensorDef:
    description: SensorEntityDescription
    value_fn: Callable[[SpaState], object]
    available_fn: Callable[[SpaSnapshot], bool] = lambda _snap: True


_DEFS: tuple[_SensorDef, ...] = (
    _SensorDef(
        SensorEntityDescription(
            key="filter_status",
            name="Filter status",
            icon="mdi:filter",
        ),
        lambda s: s.filter,
    ),
    _SensorDef(
        SensorEntityDescription(
            key="ozone_status",
            name="Ozone status",
            icon="mdi:air-filter",
        ),
        lambda s: s.ozone,
    ),
    _SensorDef(
        SensorEntityDescription(
            key="heater_adc",
            name="Heater ADC",
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="ADC",
        ),
        lambda s: s.heater_adc,
    ),
    _SensorDef(
        SensorEntityDescription(
            key="current_adc",
            name="Current ADC",
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="ADC",
        ),
        lambda s: s.current_adc,
    ),
    _SensorDef(
        SensorEntityDescription(
            key="ph",
            name="pH",
            device_class=SensorDeviceClass.PH,
            suggested_display_precision=2,
        ),
        lambda s: s.ph,
        lambda snap: has_ph_orp(snap),
    ),
    _SensorDef(
        SensorEntityDescription(
            key="orp",
            name="ORP",
            native_unit_of_measurement="mV",
            icon="mdi:gauge",
            suggested_display_precision=0,
        ),
        lambda s: s.orp,
        lambda snap: has_ph_orp(snap),
    ),
    _SensorDef(
        SensorEntityDescription(
            key="cl_range",
            name="Cl range",
            icon="mdi:creation",
        ),
        lambda s: s.cl_range,
        lambda snap: has_onzen(snap),
    ),
    _SensorDef(
        SensorEntityDescription(
            key="heater_1_status",
            name="Heater 1 status",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
        lambda s: s.heater_1,
        lambda snap: has_heater(snap, 1),
    ),
    _SensorDef(
        SensorEntityDescription(
            key="heater_2_status",
            name="Heater 2 status",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:heat-wave",
        ),
        lambda s: s.heater_2,
        lambda snap: has_heater(snap, 2),
    ),
    _SensorDef(
        SensorEntityDescription(
            key="temperature",
            name="Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="°F",
        ),
        lambda s: s.temperature_fahrenheit,
    ),
    _SensorDef(
        SensorEntityDescription(
            key="setpoint",
            name="Setpoint",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement="°F",
        ),
        lambda s: s.temperature_setpoint_fahrenheit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    entities = [
        ArcticSpaSensor(coordinator, d) for d in _DEFS if d.available_fn(snap)
    ]
    async_add_entities(entities)


class ArcticSpaSensor(ArcticSpaEntity, SensorEntity):
    def __init__(self, coordinator: ArcticSpaCoordinator, definition: _SensorDef) -> None:
        super().__init__(coordinator, key=definition.description.key)
        self.entity_description = definition.description
        self._value_fn = definition.value_fn

    @property
    def native_value(self):
        if self._state is None:
            return None
        return self._value_fn(self._state)
```

- [ ] **Step 2: Write the test**

```python
"""Tests for sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import (
    SpaInfo,
    SpaSnapshot,
    SpaState,
)


@pytest.mark.asyncio
async def test_sensor_filter_status_value(hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(filter="ACTIVE", heater_adc=42, current_adc=137, ph=7.4, orp=650.0),
        info=SpaInfo(pack_serial_number="SERIAL"),
        config=None,
    )

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = snapshot
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.spa_filter_status").state == "ACTIVE"
    assert hass.states.get("sensor.spa_heater_adc").state == "42"
    assert hass.states.get("sensor.spa_current_adc").state == "137"
    assert float(hass.states.get("sensor.spa_ph").state) == pytest.approx(7.4)
    assert float(hass.states.get("sensor.spa_orp").state) == pytest.approx(650.0)
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_sensor.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/sensor.py \
        tests/components/arctic_spa/test_sensor.py
git commit -m "Add sensor platform for diagnostics, pH, ORP, Cl range"
```

---

### Task 17: Binary sensor platform

Heaters (heat), connection status (connectivity), exhaust fan, fogger, stereo, sauna.

**Files:**
- Create: `custom_components/arctic_spa/binary_sensor.py`
- Test: `tests/components/arctic_spa/test_binary_sensor.py`

- [ ] **Step 1: Create `binary_sensor.py`**

```python
"""Binary sensor platform for Arctic Spa."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import (
    SpaSnapshot,
    SpaState,
    has_exhaust_fan,
    has_fogger,
    has_heater,
    has_sauna,
    has_stereo,
)


@dataclass(frozen=True)
class _BinaryDef:
    description: BinarySensorEntityDescription
    is_on_fn: Callable[[SpaState], bool | None]
    available_fn: Callable[[SpaSnapshot], bool] = lambda _snap: True


def _heater_on(state: SpaState, n: int) -> bool | None:
    value = getattr(state, f"heater_{n}", None)
    if value is None:
        return None
    return value in ("HEATING", "WARMUP")


_DEFS: tuple[_BinaryDef, ...] = (
    _BinaryDef(
        BinarySensorEntityDescription(
            key="heater_1",
            name="Heater 1",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        lambda s: _heater_on(s, 1),
        lambda snap: has_heater(snap, 1),
    ),
    _BinaryDef(
        BinarySensorEntityDescription(
            key="heater_2",
            name="Heater 2",
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        lambda s: _heater_on(s, 2),
        lambda snap: has_heater(snap, 2),
    ),
    _BinaryDef(
        BinarySensorEntityDescription(
            key="exhaust_fan",
            name="Exhaust fan",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:fan",
        ),
        lambda s: s.exhaust_fan,
        lambda snap: has_exhaust_fan(snap),
    ),
    _BinaryDef(
        BinarySensorEntityDescription(
            key="fogger",
            name="Fogger",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:weather-fog",
        ),
        lambda s: s.fogger,
        lambda snap: has_fogger(snap),
    ),
    _BinaryDef(
        BinarySensorEntityDescription(
            key="stereo",
            name="Stereo",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:speaker",
        ),
        lambda s: s.stereo,
        lambda snap: has_stereo(snap),
    ),
    _BinaryDef(
        BinarySensorEntityDescription(
            key="sauna",
            name="Sauna",
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:radiator",
        ),
        lambda s: s.sauna not in (None, "OFF", "SAUNA_OFF") if s.sauna is not None else None,
        lambda snap: has_sauna(snap),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    entities: list[BinarySensorEntity] = [
        ArcticSpaBinarySensor(coordinator, d) for d in _DEFS if d.available_fn(snap)
    ]
    entities.append(ArcticSpaConnectionStatus(coordinator))
    async_add_entities(entities)


class ArcticSpaBinarySensor(ArcticSpaEntity, BinarySensorEntity):
    def __init__(self, coordinator: ArcticSpaCoordinator, definition: _BinaryDef) -> None:
        super().__init__(coordinator, key=definition.description.key)
        self.entity_description = definition.description
        self._is_on_fn = definition.is_on_fn

    @property
    def is_on(self) -> bool | None:
        if self._state is None:
            return None
        return self._is_on_fn(self._state)


class ArcticSpaConnectionStatus(ArcticSpaEntity, BinarySensorEntity):
    """Always-available connectivity sensor.

    Overrides `available` to True so automations can detect a disconnected
    spa via this entity even when other entities are unavailable.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Connection"

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="connection")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
```

- [ ] **Step 2: Write the test**

```python
"""Tests for binary sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import (
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
)


@pytest.mark.asyncio
async def test_heater_binary_sensor_reports_on_when_heating(hass, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="S", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(heater_1="HEATING", heater_2="IDLE"),
        info=SpaInfo(pack_serial_number="S"),
        config=SpaConfiguration(),
    )

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = snapshot
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.spa_heater_1").state == "on"
    assert hass.states.get("binary_sensor.spa_heater_2").state == "off"


@pytest.mark.asyncio
async def test_connection_sensor_stays_available_when_disconnected(hass, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="S", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = SpaSnapshot(
            state=SpaState(heater_1="IDLE"),
            info=SpaInfo(pack_serial_number="S"),
            config=SpaConfiguration(),
        )
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.spa_connection").state == "on"

    # Simulate disconnect
    coord = hass.data[DOMAIN][entry.entry_id]
    coord.async_set_update_error(ConnectionError("boom"))
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.spa_connection")
    assert state is not None
    assert state.state == "off"
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_binary_sensor.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/binary_sensor.py \
        tests/components/arctic_spa/test_binary_sensor.py
git commit -m "Add binary sensor platform with heaters and always-available connection sensor"
```

---

### Task 18: Switch platform

Pumps 2-5, blowers 1-2, lights.

**Files:**
- Create: `custom_components/arctic_spa/switch.py`
- Test: `tests/components/arctic_spa/test_switch.py`

- [ ] **Step 1: Create `switch.py`**

```python
"""Switch platform for Arctic Spa."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import (
    PumpStatus,
    SpaSnapshot,
    SpaState,
    build_command,
    has_blower,
    has_lights,
    has_pump,
)


@dataclass(frozen=True)
class _SwitchDef:
    description: SwitchEntityDescription
    is_on_fn: Callable[[SpaState], bool | None]
    on_command: Callable[[], dict[str, int]]
    off_command: Callable[[], dict[str, int]]
    available_fn: Callable[[SpaSnapshot], bool]


def _pump_on(state: SpaState, n: int) -> bool | None:
    value = getattr(state, f"pump_{n}", None)
    if value is None:
        return None
    return value != PumpStatus.OFF


def _blower_on(state: SpaState, n: int) -> bool | None:
    value = getattr(state, f"blower_{n}", None)
    if value is None:
        return None
    return value != PumpStatus.OFF


def _build_pump_defs() -> list[_SwitchDef]:
    defs: list[_SwitchDef] = []
    for n in (2, 3, 4, 5):
        defs.append(
            _SwitchDef(
                SwitchEntityDescription(key=f"pump_{n}", name=f"Pump {n}", icon="mdi:pump"),
                is_on_fn=lambda s, _n=n: _pump_on(s, _n),
                on_command=lambda _n=n: {f"set_pump_{_n}": 2},
                off_command=lambda _n=n: {f"set_pump_{_n}": 0},
                available_fn=lambda snap, _n=n: has_pump(snap, _n),
            )
        )
    return defs


def _build_blower_defs() -> list[_SwitchDef]:
    return [
        _SwitchDef(
            SwitchEntityDescription(key=f"blower_{n}", name=f"Blower {n}", icon="mdi:weather-windy"),
            is_on_fn=lambda s, _n=n: _blower_on(s, _n),
            on_command=lambda _n=n: {f"set_blower_{_n}": 2},
            off_command=lambda _n=n: {f"set_blower_{_n}": 0},
            available_fn=lambda snap, _n=n: has_blower(snap, _n),
        )
        for n in (1, 2)
    ]


_LIGHTS = _SwitchDef(
    SwitchEntityDescription(key="lights", name="Lights", icon="mdi:lightbulb"),
    is_on_fn=lambda s: s.lights,
    on_command=lambda: {"set_lights": 1},
    off_command=lambda: {"set_lights": 0},
    available_fn=lambda snap: has_lights(snap),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    defs = [*_build_pump_defs(), *_build_blower_defs(), _LIGHTS]
    async_add_entities(
        ArcticSpaSwitch(coordinator, d) for d in defs if d.available_fn(snap)
    )


class ArcticSpaSwitch(ArcticSpaEntity, SwitchEntity):
    def __init__(self, coordinator: ArcticSpaCoordinator, definition: _SwitchDef) -> None:
        super().__init__(coordinator, key=definition.description.key)
        self.entity_description = definition.description
        self._definition = definition

    @property
    def is_on(self) -> bool | None:
        if self._state is None:
            return None
        return self._definition.is_on_fn(self._state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.send_command(build_command(**self._definition.on_command()))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.send_command(build_command(**self._definition.off_command()))
```

- [ ] **Step 2: Write the test**

```python
"""Tests for switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import (
    PumpStatus,
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
)


@pytest.mark.asyncio
async def test_lights_switch_state_and_command(hass, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="S", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(lights=True, pump_2=PumpStatus.OFF, blower_1=PumpStatus.OFF),
        info=SpaInfo(pack_serial_number="S"),
        config=SpaConfiguration(),
    )

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = snapshot
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("switch.spa_lights").state == "on"
    assert hass.states.get("switch.spa_pump_2").state == "off"
    assert hass.states.get("switch.spa_blower_1").state == "off"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.spa_lights"}, blocking=True
    )
    mock_client.send_command.assert_awaited()
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_switch.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/switch.py \
        tests/components/arctic_spa/test_switch.py
git commit -m "Add switch platform for pumps 2-5, blowers, lights"
```

---

### Task 19: Select platform

Pump 1 (OFF/LOW/HIGH).

**Files:**
- Create: `custom_components/arctic_spa/select.py`
- Test: `tests/components/arctic_spa/test_select.py`

- [ ] **Step 1: Create `select.py`**

```python
"""Select platform for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import PumpStatus, SpaSnapshot, build_command, has_pump

_OPTIONS = [PumpStatus.OFF.value, PumpStatus.LOW.value, PumpStatus.HIGH.value]
_VALUE_FOR_OPTION = {
    PumpStatus.OFF.value: 0,
    PumpStatus.LOW.value: 1,
    PumpStatus.HIGH.value: 2,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    if has_pump(snap, 1):
        async_add_entities([ArcticSpaPump1Select(coordinator)])


class ArcticSpaPump1Select(ArcticSpaEntity, SelectEntity):
    entity_description = SelectEntityDescription(
        key="pump_1",
        name="Pump 1",
        icon="mdi:pump",
        options=_OPTIONS,
    )
    _attr_options = _OPTIONS

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="pump_1")

    @property
    def current_option(self) -> str | None:
        if self._state is None or self._state.pump_1 is None:
            return None
        return self._state.pump_1.value

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.send_command(
            build_command(set_pump_1=_VALUE_FOR_OPTION[option])
        )
```

- [ ] **Step 2: Write the test**

```python
"""Tests for select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import (
    PumpStatus,
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
)


@pytest.mark.asyncio
async def test_pump1_select_current_option(hass, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="S", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(pump_1=PumpStatus.HIGH),
        info=SpaInfo(pack_serial_number="S"),
        config=SpaConfiguration(),
    )

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = snapshot
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("select.spa_pump_1")
    assert state.state == "HIGH"

    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.spa_pump_1", "option": "LOW"},
        blocking=True,
    )
    mock_client.send_command.assert_awaited()
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_select.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/select.py \
        tests/components/arctic_spa/test_select.py
git commit -m "Add select platform for Pump 1 (OFF/LOW/HIGH)"
```

---

### Task 20: Button platform

Onzen Boost.

**Files:**
- Create: `custom_components/arctic_spa/button.py`
- Test: `tests/components/arctic_spa/test_button.py`

- [ ] **Step 1: Create `button.py`**

```python
"""Button platform for Arctic Spa."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import SpaSnapshot, build_command, has_onzen


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    if has_onzen(snap):
        async_add_entities([ArcticSpaBoostButton(coordinator)])


class ArcticSpaBoostButton(ArcticSpaEntity, ButtonEntity):
    entity_description = ButtonEntityDescription(
        key="onzen_boost",
        name="Onzen boost",
        icon="mdi:rocket-launch",
    )

    def __init__(self, coordinator: ArcticSpaCoordinator) -> None:
        super().__init__(coordinator, key="onzen_boost")

    async def async_press(self) -> None:
        await self.coordinator.send_command(build_command(set_onzen=1))
```

- [ ] **Step 2: Write the test**

```python
"""Tests for button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.pyarcticspa.models import (
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
)


@pytest.mark.asyncio
async def test_boost_button_sends_command(hass, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="S", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(onzen=False),
        info=SpaInfo(pack_serial_number="S"),
        config=SpaConfiguration(),
    )

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = snapshot
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "button", "press", {"entity_id": "button.spa_onzen_boost"}, blocking=True
        )

    mock_client.send_command.assert_awaited()
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_button.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/button.py \
        tests/components/arctic_spa/test_button.py
git commit -m "Add button platform with Onzen Boost"
```

---

## Phase 5: Diagnostics, CI, polish

### Task 21: Diagnostics download

**Files:**
- Create: `custom_components/arctic_spa/diagnostics.py`
- Test: `tests/components/arctic_spa/test_diagnostics.py`

- [ ] **Step 1: Create `diagnostics.py`**

```python
"""Diagnostics download for Arctic Spa."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator

_REDACT = {"pack_serial_number", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), _REDACT),
            "options": dict(entry.options),
            "unique_id": "**REDACTED**" if entry.unique_id else None,
        },
        "snapshot": async_redact_data(
            {
                "state": asdict(snapshot.state) if snapshot and snapshot.state else None,
                "info": asdict(snapshot.info) if snapshot and snapshot.info else None,
                "config": asdict(snapshot.config) if snapshot and snapshot.config else None,
            },
            _REDACT,
        ),
        "client": {
            "host": "**REDACTED**",
            "connect_count": coordinator.client.connect_count,
            "crc_failure_count": coordinator.client.crc_failure_count,
            "last_error": str(coordinator.client.last_error) if coordinator.client.last_error else None,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
        },
    }
```

- [ ] **Step 2: Write the test**

```python
"""Tests for diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.arctic_spa.const import DOMAIN
from custom_components.arctic_spa.diagnostics import async_get_config_entry_diagnostics
from custom_components.arctic_spa.pyarcticspa.models import (
    SpaConfiguration,
    SpaInfo,
    SpaSnapshot,
    SpaState,
)


@pytest.mark.asyncio
async def test_diagnostics_redacts_serial(hass: HomeAssistant, mock_client) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SECRET-123", data={"host": "192.0.2.50"}, title="Spa")
    entry.add_to_hass(hass)
    snapshot = SpaSnapshot(
        state=SpaState(temperature_fahrenheit=100),
        info=SpaInfo(pack_serial_number="SECRET-123", model_number="Cub"),
        config=SpaConfiguration(),
    )

    def _seed():
        coord = hass.data[DOMAIN][entry.entry_id]
        coord.data = snapshot
        coord.last_update_success = True

    with patch(
        "custom_components.arctic_spa.SpaClient", return_value=mock_client
    ), patch(
        "custom_components.arctic_spa.ArcticSpaCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(side_effect=_seed),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await async_get_config_entry_diagnostics(hass, entry)

    assert "SECRET-123" not in str(result)
    assert result["entry"]["unique_id"] == "**REDACTED**"
    assert result["snapshot"]["state"]["temperature_fahrenheit"] == 100
```

- [ ] **Step 3: Run test — expect pass**

```bash
PYTHONPATH=. pytest tests/components/arctic_spa/test_diagnostics.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add custom_components/arctic_spa/diagnostics.py \
        tests/components/arctic_spa/test_diagnostics.py
git commit -m "Add diagnostics download with serial redaction"
```

---

### Task 22: CI workflow

**Files:**
- Create: `.github/workflows/validate.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Validate

on:
  push:
    branches: [main]
  pull_request:

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration

  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install ruff mypy pytest pytest-asyncio pytest-homeassistant-custom-component homeassistant protobuf grpcio-tools
      - name: Ruff
        run: ruff check .
      - name: MyPy
        run: mypy custom_components/arctic_spa/pyarcticspa
      - name: Pytest
        run: PYTHONPATH=. pytest -v
```

- [ ] **Step 2: Run validation locally**

```bash
ruff check . && mypy custom_components/arctic_spa/pyarcticspa && PYTHONPATH=. pytest -v
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "Add CI workflow for hassfest, HACS, ruff, mypy, pytest"
```

---

### Task 23: Final smoke test against the live spa

This is the validation step that requires the user's spa.

- [ ] **Step 1: Install the integration into a development HA instance**

Either:
- Symlink `custom_components/arctic_spa/` into a running HA's `config/custom_components/`, or
- Use HACS in dev mode pointing at the local repo.

- [ ] **Step 2: Restart HA, add the integration via UI**

1. Settings → Devices & Services → Add Integration → "Arctic Spa".
2. Enter the spa's IP.
3. Confirm: integration entry appears, device card shows model/firmware, climate entity appears.

- [ ] **Step 3: Verify entities populate**

Check:
- `climate.<spa>` shows current/target temp.
- Pump/blower/lights entities exist and reflect spa state.
- Pressing controls in the UI causes physical spa response within ~2 s.
- pH/ORP sensors update if the spa is reporting them.

- [ ] **Step 4: Verify availability transitions**

1. Block the spa's IP at the router for 30 s.
2. Entities should go `unavailable`; `binary_sensor.<spa>_connection` should go `off`.
3. Restore connectivity.
4. Entities recover within ~10 s.

- [ ] **Step 5: Tag v0.1.0**

```bash
git tag -a v0.1.0 -m "Initial release"
```

(Don't push the tag until ready to publish to HACS.)

---

## Self-review checklist

After implementing all tasks:

1. **Spec coverage** — every section of `docs/superpowers/specs/2026-05-09-arctic-spa-integration-design.md` should be reachable through tasks above:
   - Repo layout — Tasks 1, 2, 11, 14
   - Pyarcticspa.SpaClient — Tasks 3-9
   - models.SpaState/SpaInfo/SpaConfiguration/has_* — Task 6
   - Coordinator — Task 12
   - Setup/teardown — Task 14
   - Config flow (user/reconfigure/options) — Task 13
   - Device representation — Task 14 (entity.py)
   - Climate — Task 15
   - Sensors / binary sensors / switches / select / button — Tasks 16-20
   - Availability + reconnect — Tasks 9, 12, 14, 17
   - Logging — Task 9 (logger configured)
   - Diagnostics — Task 21
   - Testing — every protocol task ships unit tests; every platform ships at least a smoke test
   - Distribution / manifest / hacs.json — Tasks 1, 11
   - v1 acceptance criteria — Task 23

2. **Verification** — run the full test suite:

   ```bash
   PYTHONPATH=. pytest -v
   ```

   Expected: all green.

3. **Static checks**:

   ```bash
   ruff check .
   mypy custom_components/arctic_spa/pyarcticspa
   ```

   Expected: clean.

4. **Library purity** — no HA imports in the library:

   ```bash
   grep -r "homeassistant" custom_components/arctic_spa/pyarcticspa/
   ```

   Expected: no output.
