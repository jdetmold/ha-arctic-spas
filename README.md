# Arctic Spa for Home Assistant

A HACS-installable Home Assistant custom integration for Arctic Spa hot tubs.
Connects directly to your spa over your local network — no MQTT broker, no
cloud account, no Supervisor add-on.

## Status

Early development. See `docs/superpowers/specs/` for the design and
`docs/superpowers/plans/` for the implementation plan.

## Installation (HACS)

1. In HACS, add this repository as a custom integration repository.
2. Install "Arctic Spa".
3. Restart Home Assistant.
4. Settings → Devices & Services → Add Integration → search "Arctic Spa".
5. Enter your spa's local IP address.

## Credit

Reverse-engineering work originated in
[SpaBoii](https://github.com/Patrick-Ohlson/SpaBoii) by Patrick Ohlson.
