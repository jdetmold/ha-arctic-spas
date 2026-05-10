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


def _sauna_active(state: SpaState) -> bool | None:
    if state.sauna is None:
        return None
    return state.sauna != "SAUNA_STATUS_IDLE"


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
        _sauna_active,
        lambda snap: has_sauna(snap),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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

    Overrides ``available`` to True so automations can detect a disconnected
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
