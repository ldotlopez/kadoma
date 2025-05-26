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
