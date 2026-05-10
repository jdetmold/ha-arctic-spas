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
