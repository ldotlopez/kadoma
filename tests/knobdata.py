import unittest

from kadoma.knobs import (
    FanSpeedValue,
    FanSpeedParams,
    FanSpeedKnob,
    Knob,
    KnobParams,
    PowerStateKnob,
    PowerStateParams,
    PowerStateValue,
)
from kadoma.transport import build_packet, parse_packet


def bytearray_from_hex(s: str) -> bytearray:
    return bytearray.fromhex(s.replace(":", ""))


class TestKnob(unittest.TestCase):
    KnobCls: type[Knob]
    KnobParams: type[KnobParams]

    def get_query_payload_hex(self):
        return build_packet(
            self.KnobCls.QUERY_CMD_ID,
            self.KnobParams().pack(),
        ).hex(":")

    def get_update_payload_hex(self, **kwargs):
        return build_packet(
            self.KnobCls.UPDATE_CMD_ID,
            self.KnobParams(**kwargs).pack(),
        ).hex(":")


class TestPowerStateKnob(TestKnob):
    KnobCls = PowerStateKnob
    KnobParams = PowerStateParams

    def test_get_power_state_payload(self):
        self.assertEqual(self.get_query_payload_hex(), "07:00:00:20:20:01:00")

    def test_set_power_state_on_payload(self):
        self.assertEqual(
            self.get_update_payload_hex(state=True), "07:00:40:20:20:01:01"
        )

    def test_set_power_state_off_payload(self):
        self.assertEqual(
            self.get_update_payload_hex(state=False), "07:00:40:20:20:01:00"
        )


# class TestOperationModeKnob(TestKnob):
#     KnobCls = OperationModeKnob
#     KnobParams = OperationModeParams

#     # get_operation_mode 07000030200102
#     # set_operation_mode_cool 07004030200103


class TestFanSpeedKnob(TestKnob):
    KnobCls = FanSpeedKnob
    KnobParams = FanSpeedParams

    def test_get_fan_speed_payload(self):
        self.assertEqual(self.get_query_payload_hex(), "0a:00:00:50:20:01:00:21:01:00")

    def test_set_fan_speed_payload(self):
        self.assertEqual(
            self.get_update_payload_hex(
                cooling=FanSpeedValue.AUTO, heating=FanSpeedValue.AUTO
            ),
            "0a:00:40:50:20:01:00:21:01:00",
        )

    def test_set_fan_speed_payload_2(self):
        self.assertEqual(
            self.get_update_payload_hex(
                cooling=FanSpeedValue.HIGH, heating=FanSpeedValue.LOW
            ),
            "0a:00:40:50:20:01:05:21:01:01",
        )


class TestParsers(unittest.TestCase):
    def test_parse_packet(self):
        data = bytearray_from_hex("0a:00:00:50:20:01:01:21:01:01")
        cmd, params = parse_packet(data)

        self.assertEqual(cmd, 0x50)
        self.assertEqual(params, [(0x20, 1), (0x21, 1)])

    def test_packet_building_2(self):
        data = bytearray_from_hex(
            "3d0000402002000021020000300100310102320100a00100a10100a2020000a3020000a40100a50100b00100b10100b2020000b3020000b40100b50100"
        )  # noqa: E501
        cmd, params = parse_packet(data)

        self.assertTrue(cmd, 64)
        self.assertEqual(
            params,
            [
                (32, 0),
                (33, 0),
                (48, 0),
                (49, 2),
                (50, 0),
                (160, 0),
                (161, 0),
                (162, 0),
                (163, 0),
                (164, 0),
                (165, 0),
                (176, 0),
                (177, 0),
                (178, 0),
                (179, 0),
                (180, 0),
                (181, 0),
            ],
        )

    def test_get_fan_speed(self):
        data = bytearray_from_hex("0a:00:00:50:20:01:01:21:01:01")
        _, params = parse_packet(data)

        speeds = FanSpeedParams.unpack(params)
        self.assertEqual(speeds.cooling, FanSpeedValue.LOW)
        self.assertEqual(speeds.heating, FanSpeedValue.LOW)


# class TestTransport(unittest.TestCase):
#     def test_chunks(self):
#         payload = "3d0000402002000021020000300100310102320100a00100a10100a2020000a3020000a40100a50100b00100b10100b2020000b3020000b40100b50100"  # noqa: E501
#         expected = [
#             "3d000040200200002102000030010031010232",
#             "0100a00100a10100a2020000a3020000a40100",
#             "a50100b00100b10100b2020000b3020000b401",
#             "00b50100",
#         ]
#         transport = Transport()
#         got = transport.chunkerize(payload)

#         self.assertEqual(got, expected)


# Test chunk this
# 3d0000402002000021020000300100310102320100a00100a10100a2020000a3020000a40100a50100b00100b10100b2020000b3020000b40100b50100
# into

# DEBUG:pymadoka.connection:CMD 64. payload=003d000040200200002102000030010031010232 Chunk #1/4 sent with size 20 bytes
# DEBUG:pymadoka.connection:CMD 64. payload=010100a00100a10100a2020000a3020000a40100 Chunk #2/4 sent with size 20 bytes
# DEBUG:pymadoka.connection:CMD 64. payload=02a50100b00100b10100b2020000b3020000b401 Chunk #3/4 sent with size 20 bytes
# DEBUG:pymadoka.connection:CMD 64. payload=0300b50100 Chunk #4/4 sent with size 5 bytes
if __name__ == "__main__":
    unittest.main()
