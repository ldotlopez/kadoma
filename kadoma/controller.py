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

from kadoma.transport import Transport

from .knobs import (
    CleanFilterIndicatorKnob,
    FanSpeedKnob,
    OperationModeKnob,
    PowerStateKnob,
    SensorsKnob,
    SetPointKnob,
)


class Controller:
    def __init__(self, transport: Transport):
        self.transport = transport
        self.knobs = {
            "clean_filter_indicator": CleanFilterIndicatorKnob(transport),
            "fan_speed": FanSpeedKnob(transport),
            "operation_mode": OperationModeKnob(transport),
            "power_state": PowerStateKnob(transport),
            "sensors": SensorsKnob(transport),
            "set_point": SetPointKnob(transport),
        }

    async def get_status(self) -> dict:
        ret = {}
        for key, knob in self.knobs.items():
            # FIXME: Handle exceptions and set None values
            ret[key] = await knob.query()

        return ret
