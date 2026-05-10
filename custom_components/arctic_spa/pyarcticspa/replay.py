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
