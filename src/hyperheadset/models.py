from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryStatus:
    isCharging: bool
    chargePercent: int


@dataclass(frozen=True)
class HeadsetStatus:
    isDocked: bool
    isOn: bool
