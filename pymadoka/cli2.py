from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import time
from functools import wraps
from pprint import pformat as ppformat, pprint
from typing import Any, AsyncIterator, Callable

import bleak
import click
from bleak.backends.device import BLEDevice
from bleak.exc import BleakDeviceNotFoundError

from pymadoka.feature import Primitive

from . import FeatureStatus
from .consts import DEFAULT_BLUETOOTH_ADAPTER, DEFAULT_BLUETOOTH_TIMEOUT, TICK
from .controller import Controller, FeatureType, Status
from .features.clean_filter import (
    ResetCleanFilterTimerStatus,
)
from .features.fanspeed import FanSpeedEnum, FanSpeedStatus
from .features.operationmode import (
    OperationModeEnum,
    OperationModeStatus,
)
from .features.power import PowerStateStatus
from .features.setpoint import SetPointStatus


logging.basicConfig()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def dump_status(status: Status) -> dict:
    ret: dict[str, Primitive] = {}

    for ft in FeatureType:
        fname = ft.name.lower()
        if ft not in status:
            continue
        if status[ft] is None:
            ret[fname] = None
            continue

        try:
            ret[fname] = status[ft].as_primitive()  # type: ignore[union-attr]
            LOGGER.warning(f"as_primitive not implemented for {status[ft].__class__}")
        except NotImplementedError:
            ret[fname] = None

    return ret


def click_async_wrapper(f: Callable) -> Any:
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@dataclasses.dataclass
class CommonOptions:
    address: str
    adapter: str = DEFAULT_BLUETOOTH_ADAPTER
    verbose: bool = False
    bluetooth_timeout: int = DEFAULT_BLUETOOTH_TIMEOUT


@click.group(chain=False)
@click.pass_context
@click.option(
    "-a",
    "--address",
    required=True,
    type=str,
    help="Bluetooth MAC address of the thermostat",
)
@click.option(
    "-d",
    "--adapter",
    required=False,
    type=str,
    default=DEFAULT_BLUETOOTH_ADAPTER,
    show_default=True,
    help="Name of the Bluetooth adapter to be used for the connection",
)
@click.option(
    "-t",
    "--bluetooth-timeout",
    required=False,
    type=int,
    default=DEFAULT_BLUETOOTH_TIMEOUT,
    show_default=True,
    help="Timeout for bluetooth operations",
)
def cli(ctx: click.Context, address: str, adapter: str, bluetooth_timeout: int):
    ctx.obj = CommonOptions(
        address=address, adapter=adapter, bluetooth_timeout=bluetooth_timeout
    )


async def discover() -> list[BLEDevice]:
    scanner = bleak.BleakScanner()
    return await scanner.discover()


@contextlib.asynccontextmanager
async def get_controller_ctx_from_options(
    opts: CommonOptions,
) -> AsyncIterator[Controller]:
    async with get_controller_ctx(
        address=opts.address, adapter=opts.adapter
    ) as controller:
        yield controller


@contextlib.asynccontextmanager
async def get_controller_ctx(
    address: str, adapter: str = DEFAULT_BLUETOOTH_ADAPTER
) -> AsyncIterator[Controller]:
    madoka = Controller(address=address, adapter=adapter, reconnect=True)

    LOGGER.debug("connecting...")
    for _ in range(3):
        try:
            await madoka.start()

        except BleakDeviceNotFoundError:
            LOGGER.debug(
                "connection failed, trying to reinitialize "
                + f"connected={madoka.connection.client.is_connected}"
            )
            LOGGER.debug("Disconnecting client")
            await madoka.connection.client.disconnect()

            LOGGER.debug("Force BLE discover")
            await discover()
            continue

        break

    if not madoka.connection.client.is_connected:
        raise ConnectionError()

    LOGGER.debug("...done")

    yield madoka

    LOGGER.debug("cleaning up...")
    await madoka.stop()
    LOGGER.debug("...done")


@cli.command()
@click.pass_context
@click_async_wrapper
async def monitor(ctx: click.Context):
    last_update = 0.0

    async with get_controller_ctx_from_options(ctx.obj) as madoka:
        print(f"client is: {madoka.connection.client}")
        while True:
            now = time.monotonic()
            if now - last_update >= 30:
                LOGGER.info("Updating controller status")
                status = await madoka.refresh_status()
                LOGGER.info(ppformat(status))
                last_update = time.monotonic()

            await asyncio.sleep(TICK)


@cli.command()
@click.pass_context
@click_async_wrapper
async def get_status(ctx: click.Context):
    async with get_controller_ctx_from_options(ctx.obj) as madoka:
        status = await madoka.refresh_status()
        pprint(dump_status(status))


async def _query_feature(ctx: click.Context, feat_type: FeatureType) -> FeatureStatus:
    async with get_controller_ctx_from_options(ctx.obj) as madoka:
        print(f"client is: {madoka.connection.client}")
        resp = await madoka.features[feat_type].query()
        return resp


async def _update_feature(
    ctx: click.Context, feat_type: FeatureType, status: FeatureStatus
) -> FeatureStatus:
    async with get_controller_ctx_from_options(ctx.obj) as madoka:
        resp = await madoka.features[feat_type].update(status)
        return resp


#
# Fan speed get/set
#
@cli.command()
@click.pass_context
@click_async_wrapper
async def get_fan_speed(ctx: click.Context):
    resp = await _query_feature(ctx, FeatureType.FAN_SPEED)
    pprint(resp.as_primitive())


FanSpeedArgumentType = click.Choice([x.name for x in FanSpeedEnum], case_sensitive=True)


@cli.command()
@click.pass_context
@click_async_wrapper
@click.argument("cooling-speed", type=FanSpeedArgumentType)
@click.argument("heating-speed", type=FanSpeedArgumentType)
async def set_fan_speed(ctx: click.Context, cooling_speed: str, heating_speed: str):
    """Set cooling and heating fan speeds."""
    resp = await _update_feature(
        ctx,
        FeatureType.FAN_SPEED,
        FanSpeedStatus(FanSpeedEnum[cooling_speed], FanSpeedEnum[heating_speed]),
    )
    pprint(resp.as_primitive())


#
# Operation mode get/set
#
OperationModeArgumentType = click.Choice(
    [x.name for x in OperationModeEnum], case_sensitive=True
)


@cli.command()
@click.pass_context
@click_async_wrapper
async def get_operation_mode(ctx: click.Context):
    resp = await _query_feature(ctx, FeatureType.OPERATION_MODE)
    pprint(resp.as_primitive())


@cli.command()
@click.pass_context
@click_async_wrapper
@click.argument("operation-mode", type=OperationModeArgumentType)
async def set_operation_mode(ctx: click.Context, operation_mode: str):
    """Set cooling and heating fan speeds."""
    resp = await _update_feature(
        ctx,
        FeatureType.OPERATION_MODE,
        OperationModeStatus(OperationModeEnum[operation_mode]),
    )
    pprint(resp.as_primitive())


#
# Power state mode get/set
#
@cli.command()
@click.pass_context
@click_async_wrapper
async def get_power_state(ctx: click.Context):
    resp = await _query_feature(ctx, FeatureType.POWER_STATE)
    pprint(resp.as_primitive())


SetPowerStateArgumentType = click.Choice(["ON", "OFF"], case_sensitive=True)


@cli.command()
@click.pass_context
@click_async_wrapper
@click.argument("power-state-mode", type=SetPowerStateArgumentType)
async def set_power_state(ctx: click.Context, power_state_mode: str):
    """Turn ON or OFF the HVAC."""
    resp = await _update_feature(
        ctx, FeatureType.POWER_STATE, PowerStateStatus(power_state_mode == "ON")
    )
    pprint(resp.as_primitive())


#
# Set point mode get/set
#
@cli.command()
@click.pass_context
@click_async_wrapper
async def get_set_point(ctx: click.Context):
    resp = await _query_feature(ctx, FeatureType.SET_POINT)
    pprint(resp.as_primitive())


SetSetPointArgumentType = click.IntRange(0, 30, clamp=True)


@cli.command()
@click.pass_context
@click_async_wrapper
@click.argument("cooling-set-point", type=SetSetPointArgumentType)
@click.argument("heating-set-point", type=SetSetPointArgumentType)
async def set_set_point(
    ctx: click.Context, cooling_set_point: int, heating_set_point: int
):
    """Set cooling/heating target temperatures in Celsius degrees."""
    resp = await _update_feature(
        ctx, FeatureType.SET_POINT, SetPointStatus(cooling_set_point, heating_set_point)
    )
    pprint(resp.as_primitive())


#
# Temperatures mode get
# Note: 'temperatures' feature only implementes query, use 'set_point' feature to update
# temperatures
#
@cli.command()
@click.pass_context
@click_async_wrapper
async def get_temperatures(ctx: click.Context):
    resp = await _query_feature(ctx, FeatureType.TEMPERATURES)
    pprint(resp.as_primitive())


#
# get/reset clean filter
# Note: 'clean_filter_indicator' only implements query, while 'reset_clean_filter_timer'
# only implements update
#
@cli.command()
@click.pass_context
@click_async_wrapper
async def get_clean_filter_indicator(ctx: click.Context):
    resp = await _query_feature(ctx, FeatureType.CLEAN_FILTER_INDICATOR)
    pprint(resp.as_primitive())


@cli.command()
@click.pass_context
@click_async_wrapper
async def reset_clean_filter_timer(ctx: click.Context):
    """Set cooling/heating target temperatures in Celsius degrees."""
    resp = await _update_feature(
        ctx, FeatureType.RESET_CLEAN_FILTER_TIMER, ResetCleanFilterTimerStatus()
    )
    pprint(resp.as_primitive())
