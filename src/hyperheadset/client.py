import time
from typing import Any, Dict, Optional, Sequence

import hid

from .enums import Command, SliderType
from .models import BatteryStatus, HeadsetStatus


class AstroA50Client:
    """
    Minimal HID client for Astro A50 base station.
    """

    def __init__(self, vendorId: int = 0x9886, reportLengths: Sequence[int] = (64, 65), commandDelaySeconds: float = 0.08) -> None:
        self.vendorId = vendorId
        self.reportLengths = tuple(int(value) for value in reportLengths)
        self.commandDelaySeconds = float(commandDelaySeconds)
        self.lastGoodBatteryStatus: Optional[BatteryStatus] = None

    def __enter__(self) -> "AstroA50Client":
        return self

    def __exit__(self, excType, exc, tb) -> bool:
        #TODO not implemented, may do one day
        return False

    #?HID Helpers
    def _findDevicePath(self) -> bytes:
        devices = [device for device in hid.enumerate() if device.get("vendor_id") == self.vendorId]
        if not devices:
            raise RuntimeError("Astro A50 HID interface not found (driver should be 'USB Input Device').")
        return devices[0]["path"]

    def _buildRequestFrame(self, commandId: int, payloadBytes: Optional[Sequence[int]], reportLength: int) -> bytes:
        
        frameBytes = [0x02, commandId & 0xFF, 0x00]

        if payloadBytes:
            frameBytes[2] = len(payloadBytes) & 0xFF
            frameBytes.extend([(value & 0xFF) for value in payloadBytes])

        if reportLength == 65:
            paddedBody = frameBytes + [0] * (64 - len(frameBytes))
            return bytes([0x00]) + bytes(paddedBody)

        paddedBody = frameBytes + [0] * (reportLength - len(frameBytes))
        return bytes(paddedBody)

    def _normalizeResponseFrame(self, responseFrame: bytes) -> bytes:
        if (responseFrame and responseFrame[0] == 0x00 and len(responseFrame) > 1 and responseFrame[1] == 0x02):
            return responseFrame[1:]
        return responseFrame

    def _extractPayload(self, responseFrame: bytes) -> Optional[bytes]:
        if len(responseFrame) < 3:
            return None

        frameStartByte = responseFrame[0]
        statusCodeByte = responseFrame[1]

        if frameStartByte != 0x02 or statusCodeByte != 0x02:
            return None

        payloadLength = responseFrame[2]
        payloadLength = min(payloadLength, max(0, len(responseFrame) - 3))
        return responseFrame[3 : 3 + payloadLength]

    def _sendCommandOnce(self, devicePath: bytes, commandId: int, payloadBytes: Optional[Sequence[int]]) -> Optional[bytes]:
        for reportLength in self.reportLengths:
            deviceHandle = hid.device()
            try:
                deviceHandle.open_path(devicePath)
                deviceHandle.set_nonblocking(0)

                requestFrame = self._buildRequestFrame(commandId, payloadBytes, reportLength)

                try:
                    deviceHandle.send_feature_report(requestFrame)
                    time.sleep(0.03)
                    featureResponse = deviceHandle.get_feature_report(0, reportLength)
                    if featureResponse:
                        return self._normalizeResponseFrame(bytes(featureResponse))
                except OSError:
                    pass

                try:
                    deviceHandle.write(requestFrame)
                    interruptResponse = deviceHandle.read(reportLength, timeout_ms=250)
                    if interruptResponse:
                        return self._normalizeResponseFrame(bytes(interruptResponse))
                except OSError:
                    pass

            finally:
                try:
                    deviceHandle.close()
                except Exception:
                    pass

        return None

    def _query(self, commandId: int, payloadBytes: Optional[Sequence[int]] = None, retries: int = 4) -> bytes:
        devicePath = self._findDevicePath()
        lastError: Optional[Exception] = None

        for _ in range(int(retries)):
            try:
                responseFrame = self._sendCommandOnce(devicePath, int(commandId), payloadBytes)
                if responseFrame:
                    payloadFromDevice = self._extractPayload(responseFrame)
                    if payloadFromDevice is not None:
                        time.sleep(self.commandDelaySeconds)
                        return payloadFromDevice
            except Exception as error:
                lastError = error

            time.sleep(0.06)

        raise RuntimeError(f"No valid response for cmd 0x{int(commandId):02X}") from lastError

    #*Main Public API
    def getBatteryStatus(self, retries: int = 6) -> BatteryStatus:
        """
        Battery payload is 1 byte:
          isCharging = bool(byte & 0x80)
          percent    = byte & 0x7F
        """
        for _ in range(int(retries)):
            payloadBytes = self._query(Command.getBatteryStatus)

            if len(payloadBytes) >= 1:
                statusByte = payloadBytes[0]
                batteryStatus = BatteryStatus(isCharging=bool(statusByte & 0x80), chargePercent=int(statusByte & 0x7F))

                if 0 <= batteryStatus.chargePercent <= 100:
                    self.lastGoodBatteryStatus = batteryStatus
                    return batteryStatus

            time.sleep(0.05)

        if self.lastGoodBatteryStatus is not None:
            return self.lastGoodBatteryStatus

        raise RuntimeError("Could not read a sane battery value")

    def getHeadsetStatus(self) -> HeadsetStatus:
        payloadBytes = self._query(Command.getHeadsetStatus)
        if len(payloadBytes) < 1:
            raise RuntimeError(f"Unexpected headset status payload: {payloadBytes!r}")

        statusByte = payloadBytes[0]
        return HeadsetStatus(isDocked=bool(statusByte & 0x01), isOn=bool(statusByte & 0x02))

    def getSliderValue(self, sliderType: int | SliderType, saved: bool = False) -> int:
        """
        Expects payload like:
          [0x68, sliderType, activeValue, savedValue]
        """
        sliderId = int(sliderType) & 0xFF
        payloadBytes = self._query(Command.getSliderValue, [sliderId])

        if (len(payloadBytes) < 4 or payloadBytes[0] != int(Command.getSliderValue) or payloadBytes[1] != sliderId):
            raise RuntimeError(f"Unexpected slider payload: {payloadBytes!r}")

        valueIndex = 2 + int(saved)
        return int(payloadBytes[valueIndex])

    def getActiveEqPreset(self) -> int:
        payloadBytes = self._query(Command.getActiveEqPreset)
        if not payloadBytes:
            raise RuntimeError(f"Unexpected EQ payload: {payloadBytes!r}")
        return int(payloadBytes[0])

    def getBalance(self) -> int:
        payloadBytes = self._query(Command.getBalance)
        if not payloadBytes:
            raise RuntimeError(f"Unexpected balance payload: {payloadBytes!r}")
        return int(payloadBytes[0])

    def getDefaultBalance(self, saved: bool = False) -> int:
        payloadBytes = self._query(Command.getDefaultBalance, [int(saved)])
        if not payloadBytes:
            raise RuntimeError(f"Unexpected default balance payload: {payloadBytes!r}")
        return int(payloadBytes[0])

    def getAlertVolume(self, saved: bool = False) -> int:
        payloadBytes = self._query(Command.getAlertVolume, [int(saved)])
        if not payloadBytes:
            raise RuntimeError(f"Unexpected alert volume payload: {payloadBytes!r}")
        return int(payloadBytes[0])

    def getMicEq(self, saved: bool = False) -> int:
        payloadBytes = self._query(Command.getMicEq, [int(saved)])
        if not payloadBytes:
            raise RuntimeError(f"Unexpected mic EQ payload: {payloadBytes!r}")
        return int(payloadBytes[0])

    def getNoiseGateMode(self, saved: bool = False) -> int:
        """
        Payload like: [0x6A, activeMode, savedMode]
        """
        payloadBytes = self._query(Command.getNoiseGateMode)

        if len(payloadBytes) < 3 or payloadBytes[0] != int(Command.getNoiseGateMode):
            raise RuntimeError(f"Unexpected noise gate payload: {payloadBytes!r}")

        return int(payloadBytes[1 + int(saved)])

    def getSnapshot(self, battery: bool = True, headset: bool = True, sidetone: bool = False, includeTimestamp: bool = True) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {}

        if includeTimestamp:
            snapshot["timestamp"] = time.time()

        if battery:
            batteryStatus = self.getBatteryStatus()
            snapshot["battery"] = {"isCharging": batteryStatus.isCharging, "chargePercent": batteryStatus.chargePercent}

        if headset:
            headsetStatus = self.getHeadsetStatus()
            snapshot["headset"] = {"isDocked": headsetStatus.isDocked, "isOn": headsetStatus.isOn}

        if sidetone:
            sidetoneActive = self.getSliderValue(SliderType.sidetone, saved=False)
            sidetoneSaved = self.getSliderValue(SliderType.sidetone, saved=True)
            snapshot["sidetone"] = {"activePercent": int(sidetoneActive), "savedPercent": int(sidetoneSaved)}

        return snapshot
