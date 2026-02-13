import argparse
import csv
import json
import sys
import time
from importlib.metadata import version as packageVersion
from typing import Any, Dict, Optional, Set

import hid

from .client import AstroA50Client

#*Helpers
def _stableSignatureForChangeDetection(snapshot: Dict[str, Any]) -> str:
    comparable = dict(snapshot)
    comparable.pop("timestamp", None)
    return json.dumps(comparable, sort_keys=True, separators=(",", ":"))


def _printSnapshot(snapshot: Dict[str, Any], asJson: bool, prettyJson: bool, asCsv: bool, csvWriter: Optional[csv.DictWriter]) -> None:
    if asCsv:
        row: Dict[str, Any] = {}

        if "timestamp" in snapshot:
            row["timestamp"] = snapshot["timestamp"]

        battery = snapshot.get("battery")
        if isinstance(battery, dict):
            row["batteryChargePercent"] = battery.get("chargePercent")
            row["batteryIsCharging"] = battery.get("isCharging")

        headset = snapshot.get("headset")
        if isinstance(headset, dict):
            row["headsetIsDocked"] = headset.get("isDocked")
            row["headsetIsOn"] = headset.get("isOn")

        sidetone = snapshot.get("sidetone")
        if isinstance(sidetone, dict):
            row["sidetoneActivePercent"] = sidetone.get("activePercent")
            row["sidetoneSavedPercent"] = sidetone.get("savedPercent")

        if csvWriter is None:
            raise RuntimeError("csvWriter is None in CSV mode")

        csvWriter.writerow(row)
        sys.stdout.flush()
        return

    if asJson:
        if prettyJson:
            print(json.dumps(snapshot, indent=2, sort_keys=True))
        else:
            print(json.dumps(snapshot, separators=(",", ":"), sort_keys=True))
        return

    #*Human Readable
    battery = snapshot.get("battery")
    if isinstance(battery, dict):
        print(f"Battery: {battery.get('chargePercent')}% charging={battery.get('isCharging')}")

    headset = snapshot.get("headset")
    if isinstance(headset, dict):
        print(f"Headset: docked={headset.get('isDocked')} on={headset.get('isOn')}")

    sidetone = snapshot.get("sidetone")
    if isinstance(sidetone, dict):
        print(f"Sidetone: active={sidetone.get('activePercent')}% saved={sidetone.get('savedPercent')}%")


def _printDeviceList(vendorId: int) -> int:
    devices = [d for d in hid.enumerate() if d.get("vendor_id") == vendorId]

    if not devices:
        print(f"No HID devices found for vendor_id=0x{vendorId:04X}")
        return 1

    for i, device in enumerate(devices, start=1):
        print(
            f"[{i}] "
            f"vendor=0x{vendorId:04X} "
            f"product=0x{int(device.get('product_id')):04X} "
            f"mfg={device.get('manufacturer_string')!r} "
            f"product={device.get('product_string')!r} "
            f"path={device.get('path')!r}"
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="hyperheadset", description="Hyper's headset tooling: Astro A50 base station stats via HID")

    #?Meta
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--device-list", action="store_true")
    parser.add_argument("--vendor-id", type=lambda s: int(s, 0), default=0x9886)

    #?Field selection
    parser.add_argument("--battery", action="store_true")
    parser.add_argument("--headset", action="store_true")
    parser.add_argument("--sidetone", action="store_true")
    parser.add_argument("--fields", type=str, default="")

    #?Output
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--p", action="store_true", help="Pretty JSON")
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--no-timestamp", action="store_true")

    #?Watch
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--changes-only", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--count", type=int, default=0)

    args = parser.parse_args()

    #?version
    if args.version:
        print(packageVersion("hyperheadset"))
        return 0

    vendorId = int(args.vendor_id)

    if args.device_list:
        return _printDeviceList(vendorId)

    if args.interval <= 0:
        raise SystemExit("--interval must be > 0")

    intervalSeconds = max(args.interval, 0.25)

    allowedFields: Set[str] = {"battery", "headset", "sidetone"}

    if args.fields.strip():
        requested = {x.strip().lower() for x in args.fields.split(",") if x.strip()}
        unknown = requested - allowedFields
        if unknown:
            raise SystemExit(f"Unknown fields: {', '.join(sorted(unknown))}")

        includeBattery = "battery" in requested
        includeHeadset = "headset" in requested
        includeSidetone = "sidetone" in requested
    else:
        includeBattery = args.battery
        includeHeadset = args.headset
        includeSidetone = args.sidetone

        if not (includeBattery or includeHeadset or includeSidetone):
            includeBattery = True
            includeHeadset = True

    asCsv = bool(args.csv)
    asJson = bool(args.json) and not asCsv
    prettyJson = bool(args.p)
    includeTimestamp = not args.no_timestamp

    csvWriter: Optional[csv.DictWriter] = None
    if asCsv:
        fieldnames = [
            "timestamp",
            "batteryChargePercent",
            "batteryIsCharging",
            "headsetIsDocked",
            "headsetIsOn",
            "sidetoneActivePercent",
            "sidetoneSavedPercent"
        ]
        csvWriter = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        csvWriter.writeheader()

    lastSignature: Optional[str] = None

    with AstroA50Client(vendorId=vendorId) as client:

        def emitOnce() -> bool:
            nonlocal lastSignature

            snapshot = client.getSnapshot(battery=includeBattery, headset=includeHeadset, sidetone=includeSidetone, includeTimestamp=includeTimestamp)

            if args.watch and args.changes_only:
                sig = _stableSignatureForChangeDetection(snapshot)
                if sig == lastSignature:
                    return False
                lastSignature = sig

            _printSnapshot(snapshot, asJson, prettyJson, asCsv, csvWriter)
            return True

        if args.watch:
            emitted = 0
            try:
                while True:
                    if emitOnce():
                        emitted += 1
                        if args.count and emitted >= args.count:
                            return 0
                    time.sleep(intervalSeconds)
            except KeyboardInterrupt:
                if not asCsv:
                    print("\nStopped.")
                return 0

        emitOnce()
        return 0
    return 0