#!/usr/bin/env python3

# Copyright (C) 2019-2024 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

import click
from bleak import BleakScanner
from bleak.exc import BleakDeviceNotFoundError

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
from .transport import get_int_size, get_transport, parse_packet
from .unit import Unit

logging.basicConfig()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def click_async_wrapper(f: Callable) -> Any:
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


async def runner(fn: Awaitable):
    try:
        return await fn
    except BleakDeviceNotFoundError as e:
        print_error(f"{e.identifier}: device NOT found")


def print_error(*args, **kwargs):
    kwargs["file"] = sys.stderr
    print(*args, **kwargs)


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

    async with get_transport(device) as transport:
        resp = await transport.send_bytes(payloadb)
        print(resp.hex(":"))


@cli.group()
@click_async_wrapper
async def client():
    pass


##
# Unit
##


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_status(address: str):
    async def g():
        async with get_transport(address) as transport:
            ctlr = Unit(transport)
            res = await ctlr.get_status()
            print(f"Response data: {res}")

    return await runner(g())


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_info(address: str):
    async def g():
        async with get_transport(address) as transport:
            ctlr = Unit(transport)
            res = await ctlr.get_info()
            print(f"Response data: {res}")

    return await runner(g())


##
# Power state
##


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_power_state(address: str):
    async def g():
        async with get_transport(address) as transport:
            knob = PowerStateKnob(transport)
            res = await knob.query()
            print(f"Response data: {res}")

    return await runner(g())


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("state", type=click.Choice(["ON", "OFF"]))
@click_async_wrapper
async def set_power_state(address: str, state: str):
    async with get_transport(address) as transport:
        knob = PowerStateKnob(transport)
        res = await knob.update(state=True if state == "ON" else False)
        print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click_async_wrapper
async def get_operation_mode(address: str):
    async with get_transport(address) as transport:
        knob = OperationModeKnob(transport)
        res = await knob.query()
        print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("mode", type=click.Choice([x.name for x in OperationModeValue]))
@click_async_wrapper
async def set_operation_mode(address: str, mode: str):
    async with get_transport(address) as transport:
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
    async with get_transport(address) as transport:
        knob = FanSpeedKnob(transport)
        res = await knob.query()
        print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("cooling-speed", type=click.Choice([x.name for x in FanSpeedValue]))
@click.argument("heating-speed", type=click.Choice([x.name for x in FanSpeedValue]))
@click_async_wrapper
async def set_fan_speed(address: str, cooling_speed: str, heating_speed: str):
    async with get_transport(address) as transport:
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
    async with get_transport(address) as transport:
        knob = SetPointKnob(transport)
        res = await knob.query()
        print(f"Response data: {res}")


@client.command
@click.option("--address", "-a", required=True, help="BLE device address")
@click.argument("cooling", type=int)
@click.argument("heating", type=int)
@click_async_wrapper
async def set_set_point(address: str, cooling: int, heating: int):
    async with get_transport(address) as transport:
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
    async with get_transport(address) as transport:
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
    async with get_transport(address) as transport:
        knob = CleanFilterIndicatorKnob(transport)
        res = await knob.query()
        print(f"Response data: {res}")


@cli.command
@click.argument("hex_packet")
@click_async_wrapper
async def parse(hex_packet: str):
    hex_packet = hex_packet.replace(":", "")
    packet = bytearray.fromhex(hex_packet)
    cmd, params = parse_packet(packet)
    print(f"Command: {hex(cmd)}")
    for k, v in params:
        print(f"  key={hex(k)}, value={v}, size={get_int_size(v)}")
