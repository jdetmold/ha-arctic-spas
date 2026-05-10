"""Sensor platform for Arctic Spa."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
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
    value_fn: Callable[[SpaState], Any]
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
            native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        ),
        lambda s: s.temperature_fahrenheit,
    ),
    _SensorDef(
        SensorEntityDescription(
            key="setpoint",
            name="Setpoint",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        ),
        lambda s: s.temperature_setpoint_fahrenheit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    async_add_entities(
        ArcticSpaSensor(coordinator, d) for d in _DEFS if d.available_fn(snap)
    )


class ArcticSpaSensor(ArcticSpaEntity, SensorEntity):
    def __init__(self, coordinator: ArcticSpaCoordinator, definition: _SensorDef) -> None:
        super().__init__(coordinator, key=definition.description.key)
        self.entity_description = definition.description
        self._value_fn = definition.value_fn

    @property
    def native_value(self) -> Any:
        if self._state is None:
            return None
        return self._value_fn(self._state)
