from __future__ import annotations

import enum
import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, final

from .transport import CommandParams, Transport

LOGGER = logging.getLogger(__name__)


class KnobParams(ABC):
    # VALUES_CLS: type[enum.Enum]

    # DATA_KEYS: list[tuple[str, int]]

    # @classmethod
    # def unpack(cls, params: CommandParams) -> KnobParams:
    #     value_to_name = {v: k for k, v in cls.DATA_KEYS}

    #     kwargs = {}
    #     for k, v in params:
    #         if k not in value_to_name:
    #             LOGGER.warning(f"not matching key for value {k}")
    #             continue

    #         kwargs[value_to_name[k]] = cls.VALUES_CLS(v)

    #     return cls(**kwargs)

    @classmethod
    @abstractmethod
    def unpack(cls, params: CommandParams) -> KnobParams: ...

    @abstractmethod
    def pack(self) -> CommandParams: ...


KnobParams_T = TypeVar("KnobParams_T", bound=KnobParams)
KnobValue_T = TypeVar("KnobValue_T", bound=enum.Enum)


class Knob(Generic[KnobParams_T, KnobValue_T]):
    QUERY_CMD_ID: int
    UPDATE_CMD_ID: int

    def __init__(self, transport: Transport) -> None:
        super().__init__()
        self.transport = transport

    async def _send(self, cmd: int, params: KnobParams_T) -> CommandParams:
        _, raw_params = await self.transport.send_command(cmd, params.pack())
        return raw_params

    async def _query(self, params: KnobParams_T) -> CommandParams:
        return await self._send(self.QUERY_CMD_ID, params)

    async def _update(self, params: KnobParams_T) -> CommandParams:
        return await self._send(self.UPDATE_CMD_ID, params)

    # @abstractmethod
    # def unpack(cls, params: CommandParams) -> KnobParams_T: ...

    # @abstractmethod
    # def pack(self, **kwargs: Any)-> CommandParams: ...


##
# Power state
##


class PowerStateValue(enum.Enum):
    ON = 1
    OFF = 0


class PowerStateParams(KnobParams):
    STATE_KEY = 0x20

    def __init__(self, state: bool = False):
        self.state = state

    @classmethod
    def unpack(cls, params: CommandParams):
        kwargs = {}

        for k, v in params:
            if k == cls.STATE_KEY:
                kwargs["state"] = True if v else False
            else:
                # Warning
                pass

        return cls(**kwargs)

    def pack(self) -> CommandParams:
        return [(self.STATE_KEY, 1 if self.state else 0)]


@final
class PowerStateKnob(Knob[PowerStateParams, PowerStateValue]):
    QUERY_CMD_ID = 32
    UPDATE_CMD_ID = 16416

    async def query(self) -> bool:
        raw_params = await self._query(PowerStateParams())
        params = PowerStateParams.unpack(raw_params)
        return params.state

    async def update(self, state: bool) -> bool:
        raw_params = await self._update(PowerStateParams(state=state))
        params = PowerStateParams.unpack(raw_params)
        return params.state


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


class OperationModeParams(KnobParams):
    MODE_KEY = 0x20

    def __init__(self, mode: OperationModeValue = OperationModeValue.AUTO):
        self.mode = mode

    @classmethod
    def unpack(cls, params: CommandParams) -> OperationModeParams:
        kwargs = {}
        for k, v in params:
            if k == cls.MODE_KEY:
                kwargs["mode"] = OperationModeValue(v)
            else:
                pass  # FIXME: warning

        return cls(**kwargs)

    def pack(self) -> CommandParams:
        return [
            (self.MODE_KEY, self.mode.value),
        ]


@final
class OperationModeKnob(Knob[OperationModeParams, OperationModeValue]):
    QUERY_CMD_ID = 48
    UPDATE_CMD_ID = 16432

    async def query(self) -> OperationModeValue:
        raw_params = await self._query(OperationModeParams())
        params = OperationModeParams.unpack(raw_params)
        return params.mode

    async def update(self, mode: OperationModeValue) -> OperationModeValue:
        raw_params = await self._update(OperationModeParams(mode=mode))
        params = OperationModeParams.unpack(raw_params)
        return params.mode


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


class FanSpeedParams(KnobParams):
    COOLING_KEY = 0x20
    HEATING_KEY = 0x21

    def __init__(
        self,
        cooling: FanSpeedValue = FanSpeedValue.AUTO,
        heating: FanSpeedValue = FanSpeedValue.AUTO,
    ):
        self.cooling = cooling
        self.heating = heating

    @classmethod
    def unpack(cls, params: CommandParams) -> FanSpeedParams:
        kwargs = {}
        for k, v in params:
            if k == cls.COOLING_KEY:
                kwargs["cooling"] = FanSpeedValue(v)
            elif k == cls.HEATING_KEY:
                kwargs["heating"] = FanSpeedValue(v)
                pass  # FIXME: warning

        return cls(**kwargs)

    def pack(self) -> CommandParams:
        return [
            (self.COOLING_KEY, self.cooling.value),
            (self.HEATING_KEY, self.heating.value),
        ]


@final
class FanSpeedKnob(Knob[FanSpeedParams, FanSpeedValue]):
    QUERY_CMD_ID = 80
    UPDATE_CMD_ID = 16464

    async def query(self) -> tuple[FanSpeedValue, FanSpeedValue]:
        raw_params = await self._query(FanSpeedParams())
        params = FanSpeedParams.unpack(raw_params)
        return params.cooling, params.heating

    async def update(
        self, cooling: FanSpeedValue, heating: FanSpeedValue
    ) -> tuple[FanSpeedValue, FanSpeedValue]:
        raw_params = await self._update(
            FanSpeedParams(cooling=cooling, heating=heating)
        )
        params = FanSpeedParams.unpack(raw_params)
        return params.cooling, params.heating


##
# Set point speed
##


# class FanSpeedValue(enum.Enum):
#     HIGH = 5
#     MID_HIGH = 4
#     MID = 3
#     MID_LOW = 2
#     LOW = 1
#     AUTO = 0


class SetPointParams(KnobParams):
    COOLING_SET_POINT_KEY = (0x20, 2)
    HEATING_SET_POINT_KEY = (0x21, 2)
    RANGE_ENABLED_KEY = (0x30, 1)
    MODE_KEY = (0x31, 1)
    MINIMUM_DIFFERENTIAL_KEY = (0x32, 1)
    MIN_COOLING_LOWERLIMIT_KEY = (0xA0, 1)
    MIN_HEATING_LOWERLIMIT_KEY = (0xA1, 1)
    COOLING_LOWERLIMIT_KEY = (0xA2, 2)
    HEATING_LOWERLIMIT_KEY = (0xA3, 2)
    COOLING_LOWERLIMIT_SYMBOL_KEY = (0xA4, 1)
    HEATING_LOWERLIMIT_SYMBOL_KEY = (0xA5, 1)
    MAX_COOLING_UPPERLIMIT_KEY = (0xB0, 1)
    MAX_HEATING_UPPERLIMIT_KEY = (0xB1, 1)
    COOLING_UPPERLIMIT_KEY = (0xB2, 2)
    HEATING_UPPERLIMIT_KEY = (0xB3, 2)
    COOLING_UPPERLIMIT_SYMBOL_KEY = (0xB4, 1)
    HEATING_UPPERLIMIT_SYMBOL_KEY = (0xB5, 1)

    def __init__(
        self,
        cooling_set_point: int = 0,
        heating_set_point: int = 0,
        range_enabled: int = 0,
        mode: int = 0,
        minimum_differential: int = 0,
        min_cooling_lowerlimit: int = 0,
        min_heating_lowerlimit: int = 0,
        cooling_lowerlimit: int = 0,
        heating_lowerlimit: int = 0,
        cooling_lowerlimit_symbol: int = 0,
        heating_lowerlimit_symbol: int = 0,
        max_cooling_upperlimit: int = 0,
        max_heating_upperlimit: int = 0,
        cooling_upperlimit: int = 0,
        heating_upperlimit: int = 0,
        cooling_upperlimit_symbol: int = 0,
        heating_upperlimit_symbol: int = 0,
    ):

        self.cooling_set_point = cooling_set_point
        self.heating_set_point = heating_set_point
        self.range_enabled = range_enabled
        self.mode = mode
        self.minimum_differential = minimum_differential
        self.min_cooling_lowerlimit = min_cooling_lowerlimit
        self.min_heating_lowerlimit = min_heating_lowerlimit
        self.cooling_lowerlimit = cooling_lowerlimit
        self.heating_lowerlimit = heating_lowerlimit
        self.cooling_lowerlimit_symbol = cooling_lowerlimit_symbol
        self.heating_lowerlimit_symbol = heating_lowerlimit_symbol
        self.max_cooling_upperlimit = max_cooling_upperlimit
        self.max_heating_upperlimit = max_heating_upperlimit
        self.cooling_upperlimit = cooling_upperlimit
        self.heating_upperlimit = heating_upperlimit
        self.cooling_upperlimit_symbol = cooling_upperlimit_symbol
        self.heating_upperlimit_symbol = heating_upperlimit_symbol

    @classmethod
    def unpack(cls, params: CommandParams) -> SetPointParams:
        def from_dev(v) -> int:
            return round(v / 128.0)

        kwargs = {}

        for k, v in params:
            if k == cls.COOLING_SET_POINT_KEY[0]:
                kwargs["cooling_set_point"] = from_dev(v)

            elif k == cls.HEATING_SET_POINT_KEY[0]:
                kwargs["heating_set_point"] = from_dev(v)

            elif k == cls.RANGE_ENABLED_KEY[0]:
                kwargs["range_enabled"] = from_dev(v)

            elif k == cls.MODE_KEY[0]:
                kwargs["mode"] = from_dev(v)

            elif k == cls.MINIMUM_DIFFERENTIAL_KEY[0]:
                kwargs["minimum_differential"] = from_dev(v)

            elif k == cls.MIN_COOLING_LOWERLIMIT_KEY[0]:
                kwargs["min_cooling_lowerlimit"] = from_dev(v)

            elif k == cls.MIN_HEATING_LOWERLIMIT_KEY[0]:
                kwargs["min_heating_lowerlimit"] = from_dev(v)

            elif k == cls.COOLING_LOWERLIMIT_KEY[0]:
                kwargs["cooling_lowerlimit"] = from_dev(v)

            elif k == cls.HEATING_LOWERLIMIT_KEY[0]:
                kwargs["heating_lowerlimit"] = from_dev(v)

            elif k == cls.COOLING_LOWERLIMIT_SYMBOL_KEY[0]:
                kwargs["cooling_lowerlimit_symbol"] = from_dev(v)

            elif k == cls.HEATING_LOWERLIMIT_SYMBOL_KEY[0]:
                kwargs["heating_lowerlimit_symbol"] = from_dev(v)

            elif k == cls.MAX_COOLING_UPPERLIMIT_KEY[0]:
                kwargs["max_cooling_upperlimit"] = from_dev(v)

            elif k == cls.MAX_HEATING_UPPERLIMIT_KEY[0]:
                kwargs["max_heating_upperlimit"] = from_dev(v)

            elif k == cls.COOLING_UPPERLIMIT_KEY[0]:
                kwargs["cooling_upperlimit"] = from_dev(v)

            elif k == cls.HEATING_UPPERLIMIT_KEY[0]:
                kwargs["heating_upperlimit"] = from_dev(v)

            elif k == cls.COOLING_UPPERLIMIT_SYMBOL_KEY[0]:
                kwargs["cooling_upperlimit_symbol"] = from_dev(v)

            elif k == cls.HEATING_UPPERLIMIT_SYMBOL_KEY[0]:
                kwargs["heating_upperlimit_symbol"] = from_dev(v)

            else:
                pass  # Warning

        return cls(**kwargs)

    def pack(self) -> CommandParams:
        return [
            (self.COOLING_SET_POINT_KEY[0], self.cooling_set_point * 128),
            (self.HEATING_SET_POINT_KEY[0], self.heating_set_point * 128),
            (self.RANGE_ENABLED_KEY[0], self.range_enabled),
            (self.MODE_KEY[0], self.mode),
            (self.MINIMUM_DIFFERENTIAL_KEY[0], self.minimum_differential),
            (self.MIN_COOLING_LOWERLIMIT_KEY[0], self.min_cooling_lowerlimit),
            (self.MIN_HEATING_LOWERLIMIT_KEY[0], self.min_heating_lowerlimit),
            (self.HEATING_LOWERLIMIT_KEY[0], self.heating_lowerlimit),
            (self.COOLING_LOWERLIMIT_SYMBOL_KEY[0], self.cooling_lowerlimit_symbol),
            (self.HEATING_LOWERLIMIT_SYMBOL_KEY[0], self.heating_lowerlimit_symbol),
            (self.MAX_COOLING_UPPERLIMIT_KEY[0], self.max_cooling_upperlimit),
            (self.MAX_HEATING_UPPERLIMIT_KEY[0], self.max_heating_upperlimit),
            (self.COOLING_UPPERLIMIT_KEY[0], self.cooling_upperlimit),
            (self.HEATING_UPPERLIMIT_KEY[0], self.heating_upperlimit),
            (self.COOLING_UPPERLIMIT_SYMBOL_KEY[0], self.cooling_upperlimit_symbol),
            (self.HEATING_UPPERLIMIT_SYMBOL_KEY[0], self.heating_upperlimit_symbol),
        ]


@final
class SetPointKnob(Knob[SetPointParams, enum.Enum]):
    QUERY_CMD_ID = 64
    UPDATE_CMD_ID = 16448

    async def query(self) -> tuple[int, int]:
        raw_params = await self._query(SetPointParams())
        params = SetPointParams.unpack(raw_params)
        return params.cooling_set_point, params.heating_set_point

    async def update(self, cooling: int, heating: int) -> tuple[int, int]:
        raw_params = await self._update(
            SetPointParams(cooling_set_point=cooling, heating_set_point=heating)
        )
        params = SetPointParams.unpack(raw_params)
        return params.cooling_set_point, params.heating_set_point


##
# Sensors
##


class SensorsParams(KnobParams):

    INDOOR_KEY = 0x40
    OUTDOOR_KEY = 0x41

    def __init__(self, indoor: int | None = None, outdoor: int | None = None):
        self.indoor = indoor
        self.outdoor = outdoor

    @classmethod
    def unpack(cls, params: CommandParams) -> SensorsParams:
        def from_dev(v) -> int | None:
            return None if v == 255 else v

        kwargs = {}

        for k, v in params:
            if k == cls.INDOOR_KEY:
                kwargs["indoor"] = from_dev(v)

            elif k == cls.OUTDOOR_KEY:
                kwargs["outdoor"] = from_dev(v)

            else:
                pass  # Warning

        return cls(**kwargs)

    def pack(self) -> CommandParams:
        def to_dev(v):
            return 255 if v is None else v

        return [
            (self.INDOOR_KEY, to_dev(self.indoor)),
            (self.OUTDOOR_KEY, to_dev(self.outdoor)),
        ]


@final
class SensorsKnob(Knob[SensorsParams, enum.Enum]):
    QUERY_CMD_ID = 272
    # UPDATE_CMD_ID = -1  # Not implemented

    async def query(self) -> tuple[int, int]:
        raw_params = await self._query(SensorsParams())
        params = SensorsParams.unpack(raw_params)
        return params.indoor, params.outdoor


##
# Clean filter timer
##


class CleanFilterIndicatorParams(KnobParams):
    CLEAN_FILTER_KEY = 0x62

    def __init__(self, state: bool = False):
        self.state = state

    def pack(self):
        return [(self.CLEAN_FILTER_KEY, 0 if True else 1)]  # Yes, oposited

    @classmethod
    def unpack(cls, params: CommandParams) -> CleanFilterIndicatorParams:
        kwargs = {}
        for k, v in params:

            if k == cls.CLEAN_FILTER_KEY:
                kwargs["state"] = False if v == 0 else True

            else:
                pass  # Warning

        return cls(**kwargs)


@final
class CleanFilterIndicatorKnob(Knob):
    QUERY_CMD_ID = 256
    # UPDATE_CMD_ID = -1  # Not implemented

    async def query(self) -> bool:
        raw_params = await self._query(CleanFilterIndicatorParams())
        params = CleanFilterIndicatorParams.unpack(raw_params)
        return params.state


##
# Reset clean filter indicator
##
class CleanFilterTimerResetParams(KnobParams):
    CLEAN_FILTER_TIMER_RESET_KEY = 0xFE

    def pack(self):
        return [(self.CLEAN_FILTER_TIMER_RESET_KEY, 1)]

    @classmethod
    def unpack(cls, params: CommandParams) -> CleanFilterTimerResetParams:
        return cls()


@final
class CleanFilterTimerResetKnob(Knob):
    # QUERY_CMD_ID = 256
    UPDATE_CMD_ID = 16928  # Not implemented

    async def update(self) -> None:
        await self._update(CleanFilterTimerResetParams())
