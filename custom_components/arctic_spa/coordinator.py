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
            update_interval=None,
        )
        self.entry = entry
        self.client = client
        self.data = SpaSnapshot()

        client.on_state = self._handle_state
        client.on_info = self._handle_info
        client.on_config = self._handle_config
        client.on_connect = self._handle_connect
        client.on_disconnect = self._handle_disconnect

    @callback
    def _handle_state(self, state: SpaState) -> None:
        merged = _merge_states(self.data.state if self.data else None, state)
        self.async_set_updated_data(
            SpaSnapshot(
                state=merged,
                info=self.data.info if self.data else None,
                config=self.data.config if self.data else None,
            )
        )

    @callback
    def _handle_info(self, info: SpaInfo) -> None:
        self.async_set_updated_data(
            SpaSnapshot(
                state=self.data.state if self.data else None,
                info=info,
                config=self.data.config if self.data else None,
            )
        )

    @callback
    def _handle_config(self, config: SpaConfiguration) -> None:
        self.async_set_updated_data(
            SpaSnapshot(
                state=self.data.state if self.data else None,
                info=self.data.info if self.data else None,
                config=config,
            )
        )

    @callback
    def _handle_connect(self) -> None:
        _LOGGER.info("Arctic Spa %s: connected", self.entry.data["host"])

    @callback
    def _handle_disconnect(self, exc: Exception | None) -> None:
        self.async_set_update_error(exc or ConnectionError("disconnected"))

    async def _async_update_data(self) -> SpaSnapshot:
        # Push-driven; this is invoked by async_config_entry_first_refresh
        # before the listeners are wired. Return whatever is currently in self.data.
        if self.data is None:
            return SpaSnapshot()
        return self.data

    async def send_command(self, payload: bytes) -> None:
        if not self.last_update_success:
            raise HomeAssistantError("Spa is not connected")
        await self.client.send_command(payload)
