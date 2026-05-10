# Arctic Spa (Local) for Home Assistant

A HACS-installable Home Assistant custom integration that talks directly to
Arctic Spa hot tubs over your local network. No MQTT broker, no cloud
account, no Supervisor add-on.

> **Unofficial.** This integration is **not affiliated with, endorsed by, or
> supported by Blue Falls Manufacturing Ltd., Arctic Spa, or Levven Networks.**
> All product names, logos, and brands are property of their respective
> owners. Use at your own risk.

## What it does

- Connects to a single Arctic Spa controller on your LAN over its native TCP
  protocol (port 65534, Levven framing + protobuf payloads).
- Creates native Home Assistant entities — climate, sensors, switches,
  selects, button, binary sensors — based on the hardware your spa
  reports as installed.
- Push-driven: state updates arrive within ~2 seconds of changes; commands
  fire within ~1 second.
- Works entirely offline (no internet required).

## What it does not do

- It does **not** talk to Arctic Spa's cloud. If you want cloud-based
  control or remote access, see
  [`jensenbox/ha-arctic-spa`](https://github.com/jensenbox/ha-arctic-spa)
  (a separate project).
- It does **not** control the Onzen salt-water chlorine generator beyond
  the read-only Cl Range sensor and the existing Boost button. Onzen
  writes are intentionally disabled for chemistry-safety reasons.
- It does **not** support multi-spa setups via auto-discovery yet —
  manual IP entry only. Multiple spas can be added if each is given a
  distinct name.

## Installation (HACS)

1. In HACS, top-right ⋮ → **Custom repositories**.
2. **Repository:** `https://github.com/jdetmold/ha-arctic-spas`,
   **Type:** `Integration`. Click **Add**.
3. Search for **Arctic Spa (Local)** in HACS → **Download**.
4. Restart Home Assistant.
5. Settings → Devices & Services → **Add Integration** → search
   **Arctic Spa (Local)**.
6. Enter the spa's local IP address and a name. The name uniquely
   identifies the spa within Home Assistant — pick something distinct
   if you have more than one.

## Configuration options

After setup, **Configure** on the integration card lets you tune:

- **Live update interval** (seconds, default 2). How often we ping the
  spa for a state update. Lower = more responsive UI, higher = less
  network/CPU.
- **Information packets every N ticks** (default 4). How often we ask
  for the slower-changing INFORMATION packet (model, firmware, pH/ORP).
- **Temperature unit** (`F` or `C`).

## Credit

The Arctic Spa local-protocol reverse-engineering originated in
[SpaBoii](https://github.com/Patrick-Ohlson/SpaBoii) by Patrick Ohlson.
This project keeps the protocol code and replaces SpaBoii's MQTT bridge
with native HA entity platforms.

## License

MIT. See [`LICENSE`](LICENSE).
