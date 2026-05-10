"""Tests for the asyncio SpaClient."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from custom_components.arctic_spa_local.pyarcticspa.client import SpaClient
from custom_components.arctic_spa_local.pyarcticspa.proto import (
    SpaInformation_pb2,
    spa_live_pb2,
)
from custom_components.arctic_spa_local.pyarcticspa.protocol.messages import MessageType
from custom_components.arctic_spa_local.pyarcticspa.protocol.packet import LevvenPacket


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
    try:
        yield port
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_client_receives_live_state_via_callback() -> None:
    states_received: list = []
    received_event = asyncio.Event()

    async def server_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            # Read the first ping (any), then push a LIVE packet
            await asyncio.wait_for(reader.read(1024), timeout=2.0)
            writer.write(_live_packet(102))
            await writer.drain()
            # Hold the connection open until the test releases it
            await reader.read(1024)
        except (TimeoutError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

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
        try:
            await asyncio.wait_for(reader.read(1024), timeout=2.0)
            writer.write(_info_packet("SERIAL-1"))
            await writer.drain()
            await asyncio.sleep(0.5)
        except (TimeoutError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async with fake_spa(server_handler) as port:
        client = SpaClient(host="127.0.0.1", port=port)
        info = await client.probe_once(timeout=2.0)
        assert info.pack_serial_number == "SERIAL-1"


@pytest.mark.asyncio
async def test_probe_once_raises_on_timeout_when_server_silent() -> None:
    async def server_handler(reader, writer) -> None:
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            raise
        finally:
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
        try:
            while True:
                chunk = await reader.read(1024)
                if not chunk:
                    break
                bytes_received.extend(chunk)
                if len(bytes_received) > 60:
                    received_event.set()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    async with fake_spa(server_handler) as port:
        client = SpaClient(host="127.0.0.1", port=port, scan_interval=0.1)
        await client.start()
        await asyncio.sleep(0.3)  # let the connection establish + ping
        await client.send_command_raw(MessageType.COMMAND, b"\x42\x42")
        await asyncio.wait_for(received_event.wait(), timeout=2.0)
        await client.stop()

    assert b"\xab\xad\x1d\x3a" in bytes(bytes_received)
