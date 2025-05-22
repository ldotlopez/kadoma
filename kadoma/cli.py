from __future__ import annotations

import asyncio
import logging
import sys
from functools import wraps
from typing import Any, Callable

import click
from bleak import BleakClient, BleakScanner
from kadoma.transport import Transport

##
# Power state
##
from .knobs import (
    CleanFilterIndicatorKnob,
    FanSpeedKnob,
    FanSpeedValue,
    OperationModeKnob,
    OperationModeValue,
    PowerStateKnob,
    SensorsKnob,
    SetPointKnob,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def click_async_wrapper(f: Callable) -> Any:
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@click.group()
def cli():
    pass


@cli.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("payload")
@click_async_wrapper
async def sender(address: str, payload: str):
    payload = payload.replace(":", "")
    payloadb = bytearray.fromhex(payload)

    device = await BleakScanner.find_device_by_address(address)
    if not device:
        print(f"Device {address} not found, try restaring bluetooth", file=sys.stderr)
        return -1

    async with BleakClient(device) as client:
        tr = Transport(client)
        await tr.start()
        resp = await tr.send_bytes(payloadb)
        print(resp.hex(":"))


@cli.group()
@click_async_wrapper
async def client():
    pass


##
# Power state
##


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_power_state(address: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = PowerStateKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("state", type=click.Choice(["ON", "OFF"]))
@click_async_wrapper
async def set_power_state(address: str, state: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = PowerStateKnob(transport)
            res = await knob.update(state=True if state == "ON" else False)
            print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_operation_mode(address: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = OperationModeKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("mode", type=click.Choice([x.name for x in OperationModeValue]))
@click_async_wrapper
async def set_operation_mode(address: str, mode: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = OperationModeKnob(transport)
            res = await knob.update(mode=OperationModeValue[mode])
            print(f"Response data: {res}")


##
# Fan speed
##


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_fan_speed(address: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = FanSpeedKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("cooling-speed", type=click.Choice([x.name for x in FanSpeedValue]))
@click.argument("heating-speed", type=click.Choice([x.name for x in FanSpeedValue]))
@click_async_wrapper
async def set_fan_speed(address: str, cooling_speed: str, heating_speed: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:

            knob = FanSpeedKnob(transport)
            res = await knob.update(
                cooling=FanSpeedValue[cooling_speed],
                heating=FanSpeedValue[cooling_speed],
            )
            print(f"Response data: {res}")


##
# set point
##
@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_set_point(address: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = SetPointKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("cooling", type=int)
@click.argument("heating", type=int)
@click_async_wrapper
async def set_set_point(address: str, cooling: int, heating: int):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = SetPointKnob(transport)
            res = await knob.update(cooling, heating)
            print(f"Response data: {res}")


##
# sensors
##
@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_sensors(address: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = SensorsKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")


##
# clean filter indicator
##
@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_clean_filter_indicator(address: str):
    async with BleakClient(address) as client:
        async with Transport(client) as transport:
            knob = CleanFilterIndicatorKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")
