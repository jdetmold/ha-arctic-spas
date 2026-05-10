"""Switch platform for Arctic Spa."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArcticSpaCoordinator
from .entity import ArcticSpaEntity
from .pyarcticspa import (
    PumpStatus,
    SpaSnapshot,
    SpaState,
    build_command,
    has_blower,
    has_lights,
    has_pump,
)


@dataclass(frozen=True)
class _SwitchDef:
    description: SwitchEntityDescription
    is_on_fn: Callable[[SpaState], bool | None]
    on_command: Callable[[], dict[str, int]]
    off_command: Callable[[], dict[str, int]]
    available_fn: Callable[[SpaSnapshot], bool]


def _pump_on(state: SpaState, n: int) -> bool | None:
    value = getattr(state, f"pump_{n}", None)
    if value is None:
        return None
    return value != PumpStatus.OFF


def _blower_on(state: SpaState, n: int) -> bool | None:
    value = getattr(state, f"blower_{n}", None)
    if value is None:
        return None
    return value != PumpStatus.OFF


def _build_pump_defs() -> list[_SwitchDef]:
    defs: list[_SwitchDef] = []
    for n in (2, 3, 4, 5):
        defs.append(
            _SwitchDef(
                SwitchEntityDescription(
                    key=f"pump_{n}", name=f"Pump {n}", icon="mdi:pump"
                ),
                is_on_fn=lambda s, _n=n: _pump_on(s, _n),
                on_command=lambda _n=n: {f"set_pump_{_n}": 2},
                off_command=lambda _n=n: {f"set_pump_{_n}": 0},
                available_fn=lambda snap, _n=n: has_pump(snap, _n),
            )
        )
    return defs


def _build_blower_defs() -> list[_SwitchDef]:
    return [
        _SwitchDef(
            SwitchEntityDescription(
                key=f"blower_{n}", name=f"Blower {n}", icon="mdi:weather-windy"
            ),
            is_on_fn=lambda s, _n=n: _blower_on(s, _n),
            on_command=lambda _n=n: {f"set_blower_{_n}": 2},
            off_command=lambda _n=n: {f"set_blower_{_n}": 0},
            available_fn=lambda snap, _n=n: has_blower(snap, _n),
        )
        for n in (1, 2)
    ]


_LIGHTS = _SwitchDef(
    SwitchEntityDescription(key="lights", name="Lights", icon="mdi:lightbulb"),
    is_on_fn=lambda s: s.lights,
    on_command=lambda: {"set_lights": 1},
    off_command=lambda: {"set_lights": 0},
    available_fn=lambda snap: has_lights(snap),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ArcticSpaCoordinator = hass.data[DOMAIN][entry.entry_id]
    snap = coordinator.data or SpaSnapshot()
    defs = [*_build_pump_defs(), *_build_blower_defs(), _LIGHTS]
    async_add_entities(
        ArcticSpaSwitch(coordinator, d) for d in defs if d.available_fn(snap)
    )


class ArcticSpaSwitch(ArcticSpaEntity, SwitchEntity):
    def __init__(self, coordinator: ArcticSpaCoordinator, definition: _SwitchDef) -> None:
        super().__init__(coordinator, key=definition.description.key)
        self.entity_description = definition.description
        self._definition = definition

    @property
    def is_on(self) -> bool | None:
        if self._state is None:
            return None
        return self._definition.is_on_fn(self._state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.send_command(
            build_command(**self._definition.on_command())
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.send_command(
            build_command(**self._definition.off_command())
        )
