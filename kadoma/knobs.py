from __future__ import annotations

import enum
import logging
from typing import final

from .transport import CommandParams, Transport


CommandParamMap = dict[str, int]

LOGGER = logging.getLogger(__name__)


class Knob:
    QUERY_CMD_ID: int
    UPDATE_CMD_ID: int
    DATA_KEYS: dict[str, int]
    DEFAULT_PARAMS: dict[str, int]

    def __init__(self, transport: Transport) -> None:
        super().__init__()
        self.transport = transport

    @classmethod
    def _as_param_list(cls, map: CommandParamMap) -> CommandParams:
        key_map = cls.DATA_KEYS
        return [(key_map[k], v) for k, v in map.items()]

    @classmethod
    def _as_param_map(cls, params: CommandParams) -> CommandParamMap:
        key_map = {v: k for k, v in cls.DATA_KEYS.items()}
        return {key_map[k]: v for k, v in params}

    async def _send(self, cmd: int, params: CommandParamMap) -> CommandParamMap:
        _, resp_params = await self.transport.send_command(
            cmd, self._as_param_list(params)
        )
        return self._as_param_map(resp_params)

    async def _query(self) -> CommandParamMap:
        return await self._send(self.QUERY_CMD_ID, self.DEFAULT_PARAMS)

    async def _update(self, **kwargs: int) -> CommandParamMap:
        params = self.DEFAULT_PARAMS | kwargs
        resp_params = await self._send(self.UPDATE_CMD_ID, params)

        # Little hack to return optimishtic data from device.
        # Yes, we override response params with requested params
        # Transport just passes response from the device which is NOT reflecting
        # updated data
        resp = resp_params | params
        return resp


##
# Power state
##


# class PowerStateValue(enum.Enum):
#     ON = 1
#     OFF = 0


@final
class PowerStateKnob(Knob):
    QUERY_CMD_ID = 32
    UPDATE_CMD_ID = 16416

    DATA_KEYS = {"state": 0x20}
    DEFAULT_PARAMS = {"state": 0x00}

    async def query(self) -> bool:
        reply = await self._query()
        return True if reply["state"] else False

    async def update(self, state: bool) -> bool:
        reply = await self._update(state=state)
        return True if reply["state"] else False


##
# Operation Mode
##


class OperationModeValue(enum.Enum):
    FAN = 0
    DRY = 1
    AUTO = 2
    COOL = 3
    HEAT = 4
    VENTILATION = 5


@final
class OperationModeKnob(Knob):
    QUERY_CMD_ID = 48
    UPDATE_CMD_ID = 16432

    DATA_KEYS = {"mode": 0x20}
    DEFAULT_PARAMS = {"mode": OperationModeValue.AUTO.value}

    async def query(self) -> OperationModeValue:
        reply = await self._query()
        return OperationModeValue(reply["mode"])

    async def update(self, mode: OperationModeValue) -> OperationModeValue:
        reply = await self._update(mode=mode.value)
        return OperationModeValue(reply["mode"])


##
# Fan speed
##


class FanSpeedValue(enum.Enum):
    HIGH = 5
    MID_HIGH = 4
    MID = 3
    MID_LOW = 2
    LOW = 1
    AUTO = 0


@final
class FanSpeedKnob(Knob):
    QUERY_CMD_ID = 80
    UPDATE_CMD_ID = 16464

    DATA_KEYS = {
        "cooling": 0x20,
        "heating": 0x21,
    }

    DEFAULT_PARAMS = {
        "cooling": FanSpeedValue.AUTO.value,
        "heating": FanSpeedValue.AUTO.value,
    }

    async def query(self) -> tuple[FanSpeedValue, FanSpeedValue]:
        reply = await self._query()
        return FanSpeedValue(reply["cooling"]), FanSpeedValue(reply["heating"])

    async def update(
        self, cooling: FanSpeedValue, heating: FanSpeedValue
    ) -> tuple[FanSpeedValue, FanSpeedValue]:
        reply = await self._update(cooling=cooling.value, heating=heating.value)
        return FanSpeedValue(reply["cooling"]), FanSpeedValue(reply["heating"])


##
# Set point
##


@final
class SetPointKnob(Knob):
    QUERY_CMD_ID = 64
    UPDATE_CMD_ID = 16448

    DATA_KEYS = {
        "cooling_set_point": 0x20,
        "heating_set_point": 0x21,
        "range_enabled": 0x30,
        "mode": 0x31,
        "minimum_differential": 0x32,
        "min_cooling_lowerlimit": 0xA0,
        "min_heating_lowerlimit": 0xA1,
        "cooling_lowerlimit": 0xA2,
        "heating_lowerlimit": 0xA3,
        "cooling_lowerlimit_symbol": 0xA4,
        "heating_lowerlimit_symbol": 0xA5,
        "max_cooling_upperlimit": 0xB0,
        "max_heating_upperlimit": 0xB1,
        "cooling_upperlimit": 0xB2,
        "heating_upperlimit": 0xB3,
        "cooling_upperlimit_symbol": 0xB4,
        "heating_upperlimit_symbol": 0xB5,
    }

    DEFAULT_PARAMS = {
        "cooling_set_point": 0,  # 2 bytes length?
        "heating_set_point": 0,  # 2 bytes length?
        "range_enabled": 0,  # 1 bytes length?
        "mode": 0,  # 1 bytes length?
        "minimum_differential": 0,  # 1 bytes length?
        "min_cooling_lowerlimit": 0,  # 1 bytes length?
        "min_heating_lowerlimit": 0,  # 1 bytes length?
        "cooling_lowerlimit": 0,  # 2 bytes length?
        "heating_lowerlimit": 0,  # 2 bytes length?
        "cooling_lowerlimit_symbol": 0,  # 1 bytes length?
        "heating_lowerlimit_symbol": 0,  # 1 bytes length?
        "max_cooling_upperlimit": 0,  # 1 bytes length?
        "max_heating_upperlimit": 0,  # 1 bytes length?
        "cooling_upperlimit": 0,  # 2 bytes length?
        "heating_upperlimit": 0,  # 2 bytes length?
        "cooling_upperlimit_symbol": 0,  # 1 bytes length?
        "heating_upperlimit_symbol": 0,  # 1 bytes length?
    }

    @staticmethod
    def convert_from_device(device_value: int | float) -> int:
        return round(device_value / 128.0)

    @staticmethod
    def convert_to_device(local_value: int | float) -> int:
        return round(local_value * 128.0)

    async def query(self) -> dict[str, int]:
        reply = await self._query()
        reply = {k: self.convert_from_device(v) for k, v in reply.items()}
        return reply

    async def update(self, cooling: int, heating: int) -> dict[str, int]:
        reply = await self._update(
            cooling_set_point_key=self.convert_to_device(cooling),
            heating_set_point_key=self.convert_to_device(heating),
        )
        reply = {
            k: self.convert_from_device(v)
            for k, v in reply.items()
            if k in ["cooling_set_point_key", "heating_set_point_key"]
        }
        return reply


##
# Sensors
##


@final
class SensorsKnob(Knob):
    QUERY_CMD_ID = 272
    # UPDATE_CMD_ID = -1  # Not implemented
    DATA_KEYS = {"indoor": 0x40, "outdoor": 0x41}

    DEFAULT_PARAMS = {"indoor": 0xFF, "outdoor": 0xFF}

    @staticmethod
    def convert_from_device(device_value: int) -> int | None:
        return None if device_value == 0xFF else device_value

    async def query(self) -> dict[str, int | None]:
        reply = await self._query()
        reply = {k: self.convert_from_device(v) for k, v in reply.items()}
        return reply


##
# Clean filter indicator
##


@final
class CleanFilterIndicatorKnob(Knob):
    QUERY_CMD_ID = 256
    # UPDATE_CMD_ID = -1  # Not implemented

    DATA_KEYS = {"clean_filter_indicator": 0x62}
    DEFAULT_PARAMS = {"clean_filter_indicator": 0}

    @staticmethod
    def convert_from_device(device_value: int) -> bool:
        return False if device_value == 0x00 else True

    async def query(self) -> bool:
        reply = await self._query()
        return self.convert_from_device(reply["clean_filter_indicator"])


##
# Reset clean filter indicator
##
@final
class CleanFilterTimerResetKnob(Knob):
    # QUERY_CMD_ID = 256
    UPDATE_CMD_ID = 16928  # Not implemented
    DATA_KEYS = {"clean_filter_timer_reset": 0xFE}
    DEFAULT_PARAMS = {"clean_filter_timer_reset": 0x01}

    async def update(self) -> None:
        await self._update()
