"""Tests for the SpaCommand builder."""

import pytest

from custom_components.arctic_spa.pyarcticspa.proto import SpaCommand_pb2
from custom_components.arctic_spa.pyarcticspa.protocol.commands import build_command


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
    with pytest.raises(ValueError, match="Unknown command field"):
        build_command(set_self_destruct=1)
