from enum import IntEnum


class Command(IntEnum):
    getHeadsetStatus = 0x54
    getSliderValue = 0x68
    getNoiseGateMode = 0x6A
    getActiveEqPreset = 0x6C
    getBalance = 0x72
    getDefaultBalance = 0x77
    getAlertVolume = 0x7A
    getMicEq = 0x7B
    getBatteryStatus = 0x7C


class SliderType(IntEnum):
    streamMic = 0x00
    streamChat = 0x01
    streamGame = 0x02
    streamAux = 0x03
    mic = 0x04
    sidetone = 0x05
