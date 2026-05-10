"""Arctic Spa integration entry point.

The HA-specific imports below are wrapped so that this package can still
be imported by the protocol-library test suite without Home Assistant
being installed. At HA runtime, all imports succeed. The functions in
this module are only invoked by HA, so they only matter when HA is
present.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

try:
    from homeassistant.const import Platform
    from homeassistant.exceptions import ConfigEntryNotReady

    PLATFORMS: list[Platform] = [
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.CLIMATE,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ]
except ImportError:  # pragma: no cover - HA is required at runtime
    PLATFORMS = []  # type: ignore[assignment]
    ConfigEntryNotReady = Exception  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import ArcticSpaCoordinator

from .const import (
    CONF_HOST,
    CONF_INFO_INTERVAL_TICKS,
    CONF_SCAN_INTERVAL,
    DEFAULT_INFO_INTERVAL_TICKS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .coordinator import ArcticSpaCoordinator
    from .pyarcticspa import SpaClient

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
    except Exception as err:
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
