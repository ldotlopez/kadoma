from __future__ import annotations

import enum
import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, final

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
