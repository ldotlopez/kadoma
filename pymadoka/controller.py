"""This module contains the device controller."""

import asyncio
import logging
import enum

from pymadoka.connection import Connection, ConnectionException
from pymadoka.feature import Feature, NotImplementedException
from pymadoka.features.clean_filter import CleanFilterIndicator, ResetCleanFilterTimer
from pymadoka.features.fanspeed import FanSpeed
from pymadoka.features.operationmode import OperationMode
from pymadoka.features.power import PowerState
from pymadoka.features.setpoint import SetPoint
from pymadoka.features.temperatures import Temperatures

from . import feature
from .feature import FeatureStatus
from .consts import DEFAULT_BLUETOOTH_ADAPTER, DBUS_DELAY

logger = logging.getLogger(__name__)


class FeatureType(enum.Enum):
    CLEAN_FILTER_INDICATOR = "clean_filter_indicator"
    FAN_SPEED = "fan_speed"
    OPERATION_MODE = "operation_mode"
    POWER_STATE = "power_state"
    RESET_CLEAN_FILTER_TIMER = "reset_clean_filter_timer"
    SET_POINT = "set_point"
    TEMPERATURES = "temperatures"


Info = dict[str, str]
Status = dict[FeatureType, FeatureStatus | None]


class Controller:
    """This class implements the device controller.
    It stores all the features supported by the device and provides methods to operate
    globally on all the features.
    However, each feature can be queried/updated independently by accesing the feature
    attributes.

    Attributes:
        status (dict[string,FeatureStatus]): Last status collected from the features
        connection (Connection): Connection used to communicate with the device
        fan_speed (Feature): Feature used to control the fan speed
        operation_mode (Feature): Feature used to control the fan speed
        power_state (Feature): Feature used to control the fan speed
        set_point (Feature): Feature used to control the fan speed
        set_point (Feature): Feature used to control the fan speed
        clean_filter_indicator (Feature): Feature used to control the fan speed
    """

    def __init__(
        self, address: str, adapter: str = DEFAULT_BLUETOOTH_ADAPTER, reconnect: bool = False
    ):
        """Inits the controller with the device address.

        Args:
            address (str): MAC address of the device
            adapter (str): Bluetooth adapter for the connection
        """

        self.status: Status = Status()
        self.info: Info = {}
        self.connection = Connection(address, adapter=adapter, reconnect=reconnect)

        self.fan_speed = FanSpeed(self.connection)
        self.operation_mode = OperationMode(self.connection)
        self.power_state = PowerState(self.connection)
        self.set_point = SetPoint(self.connection)
        self.temperatures = Temperatures(self.connection)
        self.clean_filter_indicator = CleanFilterIndicator(self.connection)
        self.reset_clean_filter_timer = ResetCleanFilterTimer(self.connection)

    @property
    def features(self) -> dict[FeatureType, Feature]:
        return {
            FeatureType.CLEAN_FILTER_INDICATOR: self.clean_filter_indicator,
            FeatureType.FAN_SPEED: self.fan_speed,
            FeatureType.OPERATION_MODE: self.operation_mode,
            FeatureType.POWER_STATE: self.power_state,
            FeatureType.RESET_CLEAN_FILTER_TIMER: self.reset_clean_filter_timer,
            FeatureType.SET_POINT: self.set_point,
            FeatureType.TEMPERATURES: self.temperatures,
        }

    async def start(self) -> None:
        """Start the connection to the device."""
        await self.connection.start()

    async def stop(self) -> None:
        """Stop the connection."""
        await self.connection.cleanup()

    # async def update(self) -> None:
    #     """Iterate over all the features and query their status."""
    #
    #     for var in vars(self).values():
    #         if isinstance(var, Feature):
    #             try:
    #                 # Small delay to avoid DBUS errors produced when calls are too quick
    #                 await asyncio.sleep(DBUS_DELAY)
    #                 await var.query()
    #             except NotImplementedException as e:
    #                 if not isinstance(var, ResetCleanFilterTimer):
    #                     raise e
    #             except ConnectionAbortedError as e:
    #                 logger.debug(f"Connection aborted: {str(e)}")
    #                 raise e
    #             except ConnectionException as e:
    #                 logger.debug(f"Connection error: {str(e)}")
    #                 raise e
    #             except Exception as e:
    #                 logger.error(f"Failed to update {var.__class__.__name__}: {str(e)}")

    # def refresh_status(self) -> Status:
    #     """Collect the status from all the features into a single status dictionary with
    #     basic types.
    #
    #     Returns:
    #         Status: Dictionary with the status of each feature represented with basic types
    #     """
    #     for k, v in vars(self).items():
    #         if isinstance(v, Feature):
    #             if v.status is not None:
    #                 self.status[k] = vars(v.status)
    #
    #     return self.status

    # def get_status(self) -> Status:
    #     return self.status

    async def refresh_status(self) -> Status:
        for ft, feat in self.features.items():
            logger.debug(f"query {ft}")
            try:
                res = await feat.query()
            except feature.NotImplementedException:
                logger.debug(f"query {ft}: None")
                res = None
                continue

            logger.debug(f"query {ft}: {res}")
            await asyncio.sleep(DBUS_DELAY)

            self.status[ft] = res

        return self.status

    async def read_info(self) -> Info:
        """Reads the device info (Hardware revision, Software revision, Model,
        Manufacturer, etc)

        Returns:
            dict[str, str]: Dictionary with the device info
        """
        self.info = await self.connection.read_info()
        return self.info
