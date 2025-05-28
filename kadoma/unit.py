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

import logging

from kadoma.transport import Transport

from .knobs import (
    CleanFilterIndicatorKnob,
    FanSpeedKnob,
    OperationModeKnob,
    PowerStateKnob,
    SensorsKnob,
    SetPointKnob,
)

UnitInfo = dict[str, dict[str, str]]
LOGGER = logging.getLogger(__name__)


class Unit:
    def __init__(self, transport: Transport):
        self.transport = transport

        self.clean_filter_indicator = CleanFilterIndicatorKnob(transport)
        self.fan_speed = FanSpeedKnob(transport)
        self.operation_mode = OperationModeKnob(transport)
        self.power_state = PowerStateKnob(transport)
        self.sensors = SensorsKnob(transport)
        self.set_point = SetPointKnob(transport)

        self.info: UnitInfo | None = None

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
                LOGGER.error(f"error while query '{k}' ({e!r})")
                value = None

            ret[k] = value

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

            if sub_info:
                info[service.description] = sub_info

        self.info = info
        return info
