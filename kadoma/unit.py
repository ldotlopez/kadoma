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

from .knobs import (
    CleanFilterIndicatorKnob,
    FanSpeedKnob,
    OperationModeKnob,
    PowerStateKnob,
    SensorsKnob,
    SetPointKnob,
)
from .transport import Transport

UnitInfo = dict[str, dict[str, str]]


LOGGER = logging.getLogger(__name__)


class DeviceNotFoundError(Exception):
    pass


# async def get_ble_device(address: str, scanner: BleakScanner|None) -> BLEDevice:
#     scanner = scanner or BleakScanner()
#     devices = await scanner.discover()
#     devices_by_addr = {x.address.upper(): x for x in devices}

#     try:
#         return devices_by_addr[address.upper()]
#     except KeyError as e:
#         raise DeviceNotFoundError(address) from e


class Unit:
    # def __init__(
    #     self,
    #     ble_device_or_client_: BLEDevice | BleakClient | None = None,
    #     transport: Transport | None = None,
    #     delay: float = 0,
    #     timeout: float = BLUETOOTH_TIMEOUT,
    # ) -> None:
    #     self.info: UnitInfo | None = None

    #     if isinstance(ble_device_or_client, BLEDevice):
    #         client = BleakClient(ble_device_or_client)
    #     elif isinstance(ble_device_or_client, BleakClient):
    #         client = ble_device_or_client
    #     else:
    #         raise TypeError(ble_device_or_client)

    #     self.delay = delay
    #     self.transport = Transport(client, timeout=timeout)
    #     self.clean_filter_indicator = CleanFilterIndicatorKnob(self.transport)
    #     self.fan_speed = FanSpeedKnob(self.transport)
    #     self.operation_mode = OperationModeKnob(self.transport)
    #     self.power_state = PowerStateKnob(self.transport)
    #     self.sensors = SensorsKnob(self.transport)
    #     self.set_point = SetPointKnob(self.transport)
    def __init__(
        self,
        transport: Transport,
        delay: float = 0,
    ) -> None:
        self.info: UnitInfo | None = None

        self.delay = delay
        self.transport = transport
        self.clean_filter_indicator = CleanFilterIndicatorKnob(self.transport)
        self.fan_speed = FanSpeedKnob(self.transport)
        self.operation_mode = OperationModeKnob(self.transport)
        self.power_state = PowerStateKnob(self.transport)
        self.sensors = SensorsKnob(self.transport)
        self.set_point = SetPointKnob(self.transport)

    async def start(self):
        await self.transport.start()
        if self.info is None:
            await self.get_info()

    async def stop(self):
        await self.transport.stop()
        self.info = None

    async def reset(self):
        await self.stop()
        await self._delay()
        await self.start()

    async def get_status(self) -> dict:
        knobs = {
            "clean_filter_indicator": self.clean_filter_indicator,
            "fan_speed": self.fan_speed,
            "operation_mode": self.operation_mode,
            "power_state": self.power_state,
            "sensors": self.sensors,
            "set_point": self.set_point,
        }

        ret = {}
        for k, knob in knobs.items():
            try:
                value = await knob.query()
            except Exception as e:
                LOGGER.error(
                    f"error '{e.__class__.__module__}.{e.__class__.__name__}' "
                    f"while querying '{k}' ({e!r})"
                )
                raise

            ret[k] = value

            await self._delay()

        return ret

    async def get_info(self) -> UnitInfo:
        if self.info is not None:
            return self.info

        client = self.transport.client
        info: dict[str, dict[str, str]] = {}

        for service in client.services:
            LOGGER.debug(f"{service.uuid}: {service.description}")
            if service.description not in info:
                info[service.description] = {}

            sub_info = {}
            for char in service.characteristics:
                if "read" not in char.properties:
                    continue

                value = await client.read_gatt_char(char.uuid)
                try:
                    value = value.decode()
                except UnicodeDecodeError:
                    value = value.hex(":")

                sub_info[char.description] = value
                LOGGER.debug(
                    f"{char.uuid}:"
                    + f" handle='{char.handle}'"
                    + f" properties='{','.join(char.properties)}'"
                    + f" name='{char.description}'"
                    + f" value='{value}'"
                )

                await self._delay()

            if sub_info:
                info[service.description] = sub_info

        self.info = info
        return info

    async def _delay(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
