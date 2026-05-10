# Arctic Spa — Home Assistant Integration Design

**Status:** Approved
**Date:** 2026-05-09
**Repo:** `ha-arctic-spa`
**Integration domain:** `arctic_spa`

## Goals

A HACS-installable Home Assistant custom integration that talks directly to an Arctic Spa hot tub over its local TCP protocol and creates native HA entities — no MQTT broker, no add-on container.

The reference implementation is the existing [SpaBoii](https://github.com/Patrick-Ohlson/SpaBoii) project, which has reverse-engineered the wire protocol. We keep the protocol logic and discard the MQTT bridge.

## Non-goals (v1)

- Cloud / remote-access support.
- HA Supervisor add-on packaging.
- Onzen settings writes beyond the existing Boost button (chemistry safety).
- Energy / power calculations from `current_adc` (calibration unknown).
- Stereo/sauna/fogger control writes.
- Translations beyond English.

## Architecture overview

A push-driven integration that holds a persistent TCP connection to the spa and exposes its state through a `DataUpdateCoordinator`-backed entity tree.

```
HA Core
  └── ConfigEntry (one per spa)
       └── ArcticSpaCoordinator (DataUpdateCoordinator)
            ├── SpaClient (vendored library, asyncio)
            │     └── persistent TCP socket :65534
            │         ↕ Levven framing + CRC32 + protobuf payloads
            └── Entities: climate / sensor / switch / select / button / binary_sensor
```

The protocol code lives in a vendored library (`custom_components/arctic_spa/pyarcticspa/`) with no Home Assistant imports. The library is structured so it can be extracted to PyPI later without rewriting.

## Repo layout

```
custom_components/
  arctic_spa/
    __init__.py              # async_setup_entry / async_unload_entry
    manifest.json
    config_flow.py           # User & DHCP config flows + reconfigure + options
    const.py
    coordinator.py           # ArcticSpaCoordinator
    entity.py                # ArcticSpaEntity base class
    climate.py
    sensor.py
    binary_sensor.py
    switch.py
    select.py
    button.py
    diagnostics.py
    strings.json
    translations/en.json
    pyarcticspa/
      __init__.py            # Public API
      client.py              # Async TCP client, reconnect, command queue
      models.py              # SpaSnapshot, SpaState, SpaInfo, SpaConfiguration dataclasses + has_* helpers
      protocol/
        __init__.py
        packet.py            # LevvenPacket (from levven_packet.py)
        bytebuffer.py        # ByteBuffer helper
        parser.py            # Stream parser (state machine)
        messages.py          # MessageType enum
      proto/
        *.proto              # Source schemas (reference)
        *_pb2.py             # Pre-compiled, committed
      __main__.py            # `python -m pyarcticspa <ip>` live-dump tool
      replay.py              # `python -m pyarcticspa.replay <capture>` offline tool
hacs.json
README.md
LICENSE
.github/workflows/           # ruff, hassfest, hacs validation, pytest
tests/
  components/arctic_spa/     # HA-side tests via pytest-homeassistant-custom-component
  pyarcticspa/               # Library unit tests
docs/superpowers/specs/      # This document
```

## Component design

### `pyarcticspa.SpaClient`

Async TCP client. No HA imports.

```python
class SpaClient:
    def __init__(
        self,
        host: str,
        port: int = 65534,
        *,
        scan_interval: float = 2.0,
        info_interval_ticks: int = 4,
    ) -> None: ...

    # Callback hooks set by the coordinator
    on_state: Callable[[SpaState], None] | None
    on_info: Callable[[SpaInfo], None] | None
    on_config: Callable[[SpaConfiguration], None] | None
    on_connect: Callable[[], None] | None
    on_disconnect: Callable[[Exception | None], None] | None

    async def start(self) -> None: ...        # spawns _run_forever() task
    async def stop(self) -> None: ...
    async def send_command(self, cmd: SpaCommand) -> None: ...

    async def probe_once(self, timeout: float = 10.0) -> SpaInfo:
        """One-shot connect → send INFORMATION ping immediately → return → disconnect.
        Used by the config flow to validate setup and get the pack serial.

        Sends the INFORMATION ping at connect time (does not wait for the
        normal 4-tick cadence). Returns the first SpaInfo received with a
        non-empty pack_serial_number, or raises on timeout."""
```

`_run_forever()`:
- Connects, on success runs the read/ping loop.
- On loss, calls `on_disconnect(exc)`, sleeps with exponential backoff (1 → 2 → 4 → 8 → 16 → 32 → 60 s), reconnects.
- Backoff resets to 1 s after a connection lasts > 30 s.
- Cancellation-clean: `stop()` cancels the task and closes the socket.

Read side: `asyncio.StreamReader` + the framing parser from `protocol/parser.py`. The parser is the same state machine SpaBoii uses (`handle_packets` in `SpaBoii.py`), rewritten to consume bytes and yield complete packets.

Write side: an `asyncio.Queue` so concurrent command sends from entity callbacks are serialized.

Ping cadence (matches SpaBoii):
- Tick `i = 0`: CONFIGURATION ping.
- Tick `i % 4 == 0` (after 0): INFORMATION ping.
- Otherwise: LIVE ping.
- Inter-tick gap: `scan_interval` (default 2 s).

### `pyarcticspa.models`

```python
@dataclass(frozen=True)
class SpaState:
    temperature_fahrenheit: int | None
    temperature_setpoint_fahrenheit: int | None
    pump_1: PumpStatus | None
    pump_2: PumpStatus | None
    # ... full mirror of spa_live proto plus pH/ORP fields
    ph: float | None
    orp: float | None

@dataclass(frozen=True)
class SpaInfo:
    pack_serial_number: str | None
    model_number: str | None
    firmware_version: str | None
    # ...

@dataclass(frozen=True)
class SpaConfiguration:
    exhaust_fan: bool
    fogger: bool
    breaker_size: int | None
    # ... presence flags for hardware

@dataclass(frozen=True)
class SpaSnapshot:
    state: SpaState | None
    info: SpaInfo | None
    config: SpaConfiguration | None

# Hardware presence helpers — single source of truth for "create this entity?"
def has_pump(snapshot: SpaSnapshot, n: int) -> bool: ...
def has_blower(snapshot: SpaSnapshot, n: int) -> bool: ...
def has_lights(snapshot: SpaSnapshot) -> bool: ...
def has_onzen(snapshot: SpaSnapshot) -> bool: ...
def has_ph_orp(snapshot: SpaSnapshot) -> bool: ...
def has_heater(snapshot: SpaSnapshot, n: int) -> bool: ...
def has_exhaust_fan(snapshot: SpaSnapshot) -> bool: ...
def has_fogger(snapshot: SpaSnapshot) -> bool: ...
def has_stereo(snapshot: SpaSnapshot) -> bool: ...
def has_sauna(snapshot: SpaSnapshot) -> bool: ...
```

The `has_*` helpers are the single source of truth for hardware detection. If we refine detection later, we change one place.

### `coordinator.ArcticSpaCoordinator`

```python
class ArcticSpaCoordinator(DataUpdateCoordinator[SpaSnapshot]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SpaClient):
        super().__init__(
            hass,
            _LOGGER,
            name=f"arctic_spa@{entry.data['host']}",
            update_interval=None,  # push-driven
        )
        self.entry = entry
        self.client = client
        self._latest = SpaSnapshot(state=None, info=None, config=None)

        client.on_state = self._handle_state
        client.on_info = self._handle_info
        client.on_config = self._handle_config
        client.on_connect = self._handle_connect
        client.on_disconnect = self._handle_disconnect

    async def _async_update_data(self) -> SpaSnapshot:
        # Called by async_config_entry_first_refresh; waits for the first state push.
        ...

    async def send_command(self, **fields) -> None:
        if not self.last_update_success:
            raise HomeAssistantError("Spa is not connected")
        await self.client.send_command(build_command(**fields))
```

`update_interval=None` → coordinator does not poll. We push updates via `async_set_updated_data` when the client delivers state, and signal failures via `async_set_update_error`. The base class still handles availability propagation via `CoordinatorEntity`.

### Setup / teardown (`__init__.py`)

```python
PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]

async def async_setup_entry(hass, entry):
    client = SpaClient(
        host=entry.data["host"],
        scan_interval=entry.options.get("scan_interval", 2.0),
        info_interval_ticks=entry.options.get("info_interval_ticks", 4),
    )
    coordinator = ArcticSpaCoordinator(hass, entry, client)
    await client.start()
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.stop()
        raise
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True

async def async_unload_entry(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await coordinator.client.stop()
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False

async def _options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
```

### Config flow (`config_flow.py`)

**`async_step_user`:**
1. Form: `host` (required), `name` (optional, default "Arctic Spa").
2. Validate by calling `SpaClient.probe_once(host)` with a 10 s timeout.
3. On success: `await self.async_set_unique_id(spa_info.pack_serial_number)`, `self._abort_if_unique_id_configured(updates={"host": host})` — both dedupes and lets a re-run update an existing entry's IP.
4. Create entry with `data={"host": host}` and `title=name`.

**Errors surfaced to the form:**
- `cannot_connect` — TCP connect or read failed.
- `invalid_response` — connected but no valid Levven packets within timeout.
- `no_serial` — got packets but `spa_information.pack_serial_number` was missing.

**`async_step_dhcp`:**
- Triggered by `manifest.json["dhcp"]` matchers.
- Receives `DhcpServiceInfo(ip, macaddress, hostname)`.
- Sets unique_id from MAC initially, then runs `probe_once` to get the real serial and reconciles via `_abort_if_unique_id_configured(updates={"host": ip})`.
- Shows a confirmation step with the discovered IP.
- DHCP matchers ship empty in v1; populated once the OUI/hostname pattern is confirmed.

**`async_step_reconfigure`:**
- Lets the user change the IP without removing the entry.
- Re-runs `probe_once`, asserts the returned serial matches the entry's unique_id (otherwise → `wrong_spa` error), then updates `entry.data["host"]`.

**`OptionsFlowHandler`:**
- `scan_interval` (float, 1.0–10.0, default 2.0).
- `info_interval_ticks` (int, 1–20, default 4).
- `temperature_unit` (`F` | `C`, default `F`).

### Device representation

One device per config entry:
- `identifiers={(DOMAIN, pack_serial_number)}`
- `manufacturer="Arctic Spa"`
- `model=info.model_number or "Arctic Spa"`
- `sw_version=info.firmware_version`
- `connections={(CONNECTION_NETWORK_MAC, mac)}` if discoverable
- `name=entry.title`

All entities attach via `device_info` on the base entity class.

## Entity catalog

### Climate (`climate.py`)

`ArcticSpaClimate` — the headliner.

| Attribute | Value |
|---|---|
| `_attr_supported_features` | `ClimateEntityFeature.TARGET_TEMPERATURE` |
| `_attr_temperature_unit` | `°F` (or `°C` per option) |
| `_attr_min_temp` / `_attr_max_temp` | 80 / 104 |
| `_attr_target_temperature_step` | 1 |
| `_attr_hvac_modes` | `[HVACMode.HEAT]` |
| `_attr_hvac_mode` | `HVACMode.HEAT` (constant) |
| `_attr_hvac_action` | `HVACAction.HEATING` if any heater in HEATING/WARMUP, else `HVACAction.IDLE` |
| `_attr_current_temperature` | `state.temperature_fahrenheit` (or °C) |
| `_attr_target_temperature` | `state.temperature_setpoint_fahrenheit` |
| `async_set_temperature` | `coordinator.send_command(set_temperature_setpoint_fahrenheit=int(round(temp_f)))` |
| `_attr_name` | `None` — becomes the device's primary entity |

### Other entities (created based on `has_*` helpers)

| Detected via | Entity | Platform | Notes |
|---|---|---|---|
| Always | Connection status | `binary_sensor` | `device_class=connectivity`, mirrors coordinator availability |
| `has_pump(snap, 1)` | Pump 1 | `select` | `OFF` / `LOW` / `HIGH` |
| `has_pump(snap, n)` for n in 2..5 | Pump N | `switch` | Sends `set_pump_n=2` for ON, `0` for OFF |
| `has_blower(snap, n)` for n in 1..2 | Blower N | `switch` | |
| `has_lights(snap)` | Lights | `switch` | |
| `has_onzen(snap)` | Onzen Boost | `button` | Sends `set_onzen=1` (matches SpaBoii) |
| `has_onzen(snap)` | Cl Range | `sensor` | **Read-only** (Low / Mid / High) — write disabled per safety decision |
| `has_ph_orp(snap)` | pH | `sensor` | `device_class=ph`, precision 2 |
| `has_ph_orp(snap)` | ORP | `sensor` | `unit=mV`, precision 0 |
| Always | Filter status | `sensor` | Enum string |
| Always | Ozone status | `sensor` | Enum string |
| `has_heater(snap, n)` for n in 1..2 | Heater N | `binary_sensor` | `device_class=heat`, on when HEATING/WARMUP |
| `has_heater(snap, n)` for n in 1..2 | Heater N status | `sensor` | Diagnostic, raw enum |
| Always | Heater ADC | `sensor` | Diagnostic, unit `ADC` |
| Always | Current ADC | `sensor` | Diagnostic, unit `ADC` |
| `has_exhaust_fan(snap)` | Exhaust fan | `binary_sensor` | Diagnostic, read-only |
| `has_fogger(snap)` | Fogger | `binary_sensor` | Diagnostic |
| `has_stereo(snap)` | Stereo | `binary_sensor` | Diagnostic |
| `has_sauna(snap)` | Sauna | `binary_sensor` | Diagnostic |

All diagnostic-class entities use `_attr_entity_category = EntityCategory.DIAGNOSTIC`.

### Base entity (`entity.py`)

```python
class ArcticSpaEntity(CoordinatorEntity[ArcticSpaCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ArcticSpaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{key}"
        info = coordinator.data.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.unique_id)},
            manufacturer="Arctic Spa",
            model=(info.model_number if info else None) or "Arctic Spa",
            sw_version=info.firmware_version if info else None,
            name=coordinator.entry.title,
        )

    @property
    def _state(self) -> SpaState | None:
        return self.coordinator.data.state if self.coordinator.data else None
```

`has_entity_name = True` means each platform sets a short `_attr_name` (e.g. "Pump 1", "Setpoint") and HA composes it with the device name.

### Fallback when configuration is unknown at platform setup

If `coordinator.data.config` is `None` at platform setup time (i.e. no `spa_configuration` packet arrived during `async_config_entry_first_refresh`), each `has_*` helper returns `True` (rather than `False`) so all entities in the catalog are created. Log a WARNING that hardware presence could not be confirmed. Subsequent reloads (after a configuration packet arrives in steady state) will prune correctly. This matches SpaBoii's static-superset behavior as a worst-case floor.

## Error handling & availability

### Availability

`CoordinatorEntity.available` returns `coordinator.last_update_success and super().available`. Mapping:

- Connection healthy → `last_update_success = True` → entities available.
- Connection drops → `coordinator.async_set_update_error(exc)` → `last_update_success = False` → entities `unavailable`.
- Connection restored → next state push restores availability.

The dedicated `connection_status` binary sensor flips alongside, exposing a stable target for connectivity automations. Its entity overrides `available` to always return `True` (regardless of `coordinator.last_update_success`) so that automations can detect "spa is disconnected" — otherwise the sensor would itself go `unavailable` and could not report `off`.

### Reconnect

- Exponential backoff in `SpaClient._run_forever`: 1, 2, 4, 8, 16, 32, 60 s.
- Reset to 1 s after a connection lasts > 30 s.
- WARN on first failure, INFO on subsequent reconnect attempts, ERROR once if disconnected for > 5 minutes.
- `async_setup_entry` waits for the first packet via `async_config_entry_first_refresh`. If that fails, raise `ConfigEntryNotReady` so HA retries setup with its own backoff.

### Commands

- If `coordinator.last_update_success` is `False` when an action fires → raise `HomeAssistantError("Spa is not connected")`. User sees a UI toast.
- If the connection drops mid-write → command is dropped, error logged. **No queueing across reconnects** — stale commands could fire late and surprise the user.
- After a successful send we do **not** optimistically update entity state. The next LIVE packet (≤ scan_interval seconds away) carries the real new state.

### Edge cases

- **Two HA instances on the same spa.** Spa allows one TCP client at a time. We make no attempt to detect this — we just keep reconnecting with backoff. Documented as a "don't do that".
- **Spa power cycles.** Pack serial doesn't change → entry remains valid → reconnect closes the loop.
- **IP changes.** Integration goes unavailable. User uses reconfigure flow (or DHCP discovery if reachable).
- **Setpoint clamping.** Enforced at the climate entity level via `min_temp`/`max_temp`.
- **Temperature units.** Spa reports both °F and °C in LIVE; we pick by entity unit. Setpoint command is °F-only in the proto — we convert °C → °F before sending.
- **CRC failures.** Parser silently resets (matches SpaBoii). DEBUG log + counter exposed via diagnostics.
- **Onzen safety.** No writes to `SpaOnzen` proto. Only the Boost button (`set_onzen=1`) is shipped — same as SpaBoii's tested behavior.

### Logging

Logger names: `custom_components.arctic_spa` and `custom_components.arctic_spa.pyarcticspa.*`.

```yaml
logger:
  logs:
    custom_components.arctic_spa: debug
```

DEBUG includes hex packet dumps and parsed protobuf contents. INFO covers connect/disconnect transitions. WARN for first failure, ERROR for sustained disconnect.

### Diagnostics download (`diagnostics.py`)

`async_get_config_entry_diagnostics` returns a JSON blob:
- `entry.data` with `pack_serial_number` redacted via `async_redact_data`.
- Latest `SpaInfo`, `SpaConfiguration`, `SpaState` snapshots (serials redacted).
- Reconnect counter, last error string, uptime since last successful connect.
- CRC failure counter.

## Testing strategy

### Library (`pyarcticspa/`) — unit tests

- `protocol/packet.py`: round-trip serialize/parse, CRC validation, magic-byte handling. Pure-function tests.
- `protocol/parser.py`: feed canned byte sequences (good packet, leading garbage, two packets back-to-back, packet split across read boundaries) and assert output. Use SpaBoii's `handle_packets` as the test oracle for cross-checking.
- `client.py`: spin up a fake spa server with `asyncio.start_server`, drive connect → read → disconnect → reconnect, assert callback invocations and backoff timing.
- `models.py`: `has_*` helpers — table-driven tests covering presence/absence of every relevant proto field.

### Integration (`tests/components/arctic_spa/`)

Use `pytest-homeassistant-custom-component`.

- `test_config_flow.py`: happy path, `cannot_connect`, `invalid_response`, `no_serial`, unique_id dedupe, reconfigure flow, options flow.
- `test_init.py`: setup → unload → reload cycles.
- `test_coordinator.py`: push state arrives → entities update; disconnect → entities go unavailable.
- `test_climate.py`, `test_switch.py`, `test_select.py`, etc.: per-platform state mapping and command dispatch using a mocked `SpaClient`.

### Replay harness

```bash
python -m pyarcticspa 192.168.1.50            # live-dump packets
python -m pyarcticspa.replay capture.bin      # parse a captured stream
```

Used for ad-hoc validation against a real spa. Also doubles as the path for offline iteration if the user provides packet captures.

### CI

GitHub Actions:
- `ruff` + `black --check` + `mypy`.
- `hassfest` (HA's static integration validator).
- HACS validation action (`hacs/action`).
- `pytest` against both the library and HA-side tests.

## Distribution

**HACS install:**
1. Repo `ha-arctic-spa` registered as a HACS custom integration repository.
2. User adds the repo URL → installs → restarts HA.
3. Settings → Devices & Services → Add Integration → "Arctic Spa" → enter IP.

**`manifest.json`:**

```json
{
  "domain": "arctic_spa",
  "name": "Arctic Spa",
  "version": "0.1.0",
  "config_flow": true,
  "integration_type": "device",
  "iot_class": "local_push",
  "documentation": "https://github.com/<user>/ha-arctic-spa",
  "issue_tracker": "https://github.com/<user>/ha-arctic-spa/issues",
  "codeowners": ["@<user>"],
  "requirements": ["protobuf>=4.21,<6"],
  "dhcp": []
}
```

**`hacs.json`:**

```json
{
  "name": "Arctic Spa",
  "render_readme": true,
  "homeassistant": "2024.11.0"
}
```

Minimum HA version is 2024.11 because that's when `async_step_reconfigure` stabilized.

## v1 acceptance criteria

1. User installs via HACS, runs the config flow with a Spa IP, gets a working integration with at least the entities SpaBoii ships today.
2. Climate entity controls setpoint, shows current temperature and heating action.
3. Connection drops → entities `unavailable` → connection restored → entities recover. No HA restart needed.
4. Reconfigure flow lets the user change IP without losing the device entry.
5. `hassfest` and HACS validation pass in CI.
6. Diagnostics download produces useful redacted output.

## Future work (out of v1)

- Onzen settings writes (Cl Range, manual chemistry) behind an explicit advanced option.
- mDNS auto-discovery (research-pending).
- Stereo / sauna / fogger control writes.
- Multi-language translations.
- Energy / power calculations from `current_adc` once calibration is known.
- PyPI extraction of `pyarcticspa` as a standalone library.
