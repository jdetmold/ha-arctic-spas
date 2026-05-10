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
    decode_configuration,
    decode_information_full,
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
        self._task = asyncio.create_task(self._run_forever(), name=f"arctic_spa_local[{self.host}]")

    async def stop(self) -> None:
        self._stop_event.set()
        writer = self._writer
        if writer is not None:
            try:
                writer.close()
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
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            connection_started = loop.time()
            try:
                await self._connect_and_run()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.last_error = exc
                _LOGGER.warning("Arctic Spa %s: connection lost: %s", self.host, exc)
                if self.on_disconnect is not None:
                    self.on_disconnect(exc)

            duration = loop.time() - connection_started
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
                info, ph, orp = decode_information_full(bytes(packet.payload))
            except Exception:  # noqa: BLE001
                self.crc_failure_count += 1
                _LOGGER.debug("Failed to decode INFORMATION payload", exc_info=True)
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
                _LOGGER.debug("Failed to decode CONFIGURATION payload", exc_info=True)
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

    async def probe_once(self, timeout: float = 10.0) -> SpaInfo:  # noqa: ASYNC109
        """One-shot connect → request INFORMATION → return → disconnect.

        Returns the first INFORMATION packet decoded from the spa, even if
        ``pack_serial_number`` is empty. Some Arctic Spa controllers do not
        populate the serial in their INFORMATION packets; the config flow
        is responsible for falling back to a different unique identifier
        (usually the host address) when this happens.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self._connect_timeout,
        )
        try:
            # Send INFORMATION ping immediately
            writer.write(LevvenPacket(MessageType.INFORMATION, b"").serialize())
            await writer.drain()

            parser = StreamParser()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError("probe timed out waiting for INFORMATION packet")
                try:
                    chunk = await asyncio.wait_for(reader.read(2048), timeout=remaining)
                except TimeoutError as exc:
                    raise TimeoutError(
                        "probe timed out waiting for INFORMATION packet"
                    ) from exc
                if not chunk:
                    raise ConnectionError("spa closed connection during probe")
                for packet in parser.feed(chunk):
                    if packet.type == MessageType.INFORMATION:
                        info, _ph, _orp = decode_information_full(bytes(packet.payload))
                        return info
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
