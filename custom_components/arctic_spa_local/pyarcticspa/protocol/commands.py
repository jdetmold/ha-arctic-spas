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
