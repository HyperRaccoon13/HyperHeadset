# Hyperheadset

[![PyPI](https://img.shields.io/pypi/v/hyperheadset)](https://pypi.org/project/hyperheadset/)
[![Python](https://img.shields.io/pypi/pyversions/hyperheadset)](https://pypi.org/project/hyperheadset/)
[![License](https://img.shields.io/pypi/l/hyperheadset)](https://pypi.org/project/hyperheadset/)


A small Python CLI and library for reading live status data from the Astro
A50 base station over HID.

This started as a side project because I wanted to see battery %, dock
state, and sidetone levels without running the official Astro software
in the background. That turned into reverse-engineering the HID
protocol... which turned into this.

It talks directly to the base station, parses the response frames, and
exposes the useful bits in a clean way.

---

## What it can do
Right now it focuses on reading states.

- Read battery percentage + charging state
- Detect whether the headset is docked / powered
- Read sidetone slider values (active + saved)
- Output as JSON (compact or pretty)
- CSV logging
- Watch mode (with change detection)
- Filter specific fields (`--fields`)
- List matching HID devices
- Usable as both a CLI tool and a Python module

## Install

From PyPI:

```bash
pip install hyperheadset
```

Local install:

```bash
pip install .
```

Editable dev install:

```bash
pip install -e .
```

## CLI Usage

Default snapshot:

```bash
hyperheadset
```

Some common flags:

- Battery only → `--battery`
- JSON output → `--json`
- Pretty JSON → `--json --p`
- Watch mode → `--watch`
- Only show changes (watch mode) → `--changes-only`
- List matching HID devices → `--device-list`

### Examples

Watch only sidetone, and only print when it changes:
``` bash
hyperheadset --fields sidetone --watch --changes-only
```

Log everything to CSV every 2 seconds:
``` bash
hyperheadset --csv --watch --interval 2 > log.csv
```

Pretty JSON snapshot without timestamp:
``` bash
hyperheadset --json --p --no-timestamp
```

## Python Usage
You can also use it directly in code:

```python
from hyperheadset import AstroA50Client, SliderType

client = AstroA50Client()

battery = client.getBatteryStatus()
print(battery.chargePercent, battery.isCharging)

sidetone = client.getSliderValue(SliderType.sidetone)
print(sidetone)
```

Snapshot helper:
```python
snap = client.getSnapshot(battery=True, headset=True, sidetone=True)
print(snap)
```



## Requirements
- Python 3.10+
- `hidapi` bindings (`pip install hidapi`)
- Astro A50 base station connected over USB
- OS must expose the device as a standard HID interface

If your OS doesn't see it as HID, this won't work. No custom drivers
included here.

## Scope (and what this is *not*)

This project focuses on:

- Reading device state
- Protocol framing
- Simple query commands

It's **not**:
- A replacement for the official Astro software
- A firmware updater
- An EQ editor

Write/set commands *might* be added later, but only after making sure
they're safe. Bricking a headset is not on the roadmap.

## Credits / Prior Work
Huge credit to the [eh-fifty](https://github.com/tdryer/eh-fifty) project by Tom Dryer.

That project documents and reverse-engineers large parts of the Astro
A50 USB/HID protocol. I studied their research to understand the framing
and command structure, then re-implemented what I needed in a smaller
codebase focused purely on stats and queries.

No source code from [eh-fifty](https://github.com/tdryer/eh-fifty) is included here but their work made
this possible.

If you want broader device coverage or deeper protocol exploration,
definitely check that repository out.


## License

MIT


## Disclaimer

Not affiliated with or endorsed by Astro, Logitech, or the eh-fifty
project authors.
