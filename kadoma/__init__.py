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

import logging

from .knobs import (
    CleanFilterIndicatorKnob,
    CleanFilterTimerResetKnob,
    FanSpeedKnob,
    FanSpeedValue,
    OperationModeKnob,
    OperationModeValue,
    PowerStateKnob,
    SensorsKnob,
    SetPointKnob,
)
from .unit import Unit, UnitInfo

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

__major_version__ = 0
__minor_version__ = 0
__micro_version__ = 1

__version__ = f"{__major_version__}.{__minor_version__}.{__micro_version__}"

__all__ = [
    "CleanFilterIndicatorKnob",
    "PowerStateKnob",
    "OperationModeKnob",
    "PowerStateKnob",
    "CleanFilterIndicatorKnob",
    "CleanFilterTimerResetKnob",
    "FanSpeedKnob",
    "FanSpeedValue",
    "OperationModeValue",
    "SensorsKnob",
    "SetPointKnob",
    "Unit",
    "UnitInfo",
]
