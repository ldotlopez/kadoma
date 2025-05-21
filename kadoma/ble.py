from __future__ import annotations


from bleak import BleakClient
import logging

LOGGER = logging.getLogger(__name__)


class ActiveBleIO:
    def __init__(self, address: str):
        self.client = BleakClient(address)

    async def __aenter__(self) -> ActiveBleIO:
        await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.client.disconnect()

    async def send(
        self, characteristic_uuid: str, payload: str | bytearray, response: bool
    ) -> bytearray | None:
        if isinstance(payload, str):
            payload = bytearray.fromhex(payload)
        elif isinstance(payload, bytearray):
            pass
        else:
            raise TypeError(payload)

        # print(f"Send {bytearray_as_str(payload)}")

        resp = await self.client.write_gatt_char(
            characteristic_uuid, payload, response=response
        )
        if response is False:
            return None

        if resp is None:
            resp = await self.client.read_gatt_char(characteristic_uuid)

        return resp


class FakeBleIO:
    def __init__(self, address: str):
        self.client = BleakClient(address)

    async def __aenter__(self) -> FakeBleIO:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def send(
        self, characteristic_uuid: str, payload: str | bytearray, response: bool
    ) -> bytearray | None:
        if isinstance(payload, str):
            payload = bytearray.fromhex(payload)
        elif isinstance(payload, bytearray):
            pass
        else:
            raise TypeError(payload)

        return bytearray()

        # resp = await self.client.write_gatt_char(
        #     characteristic_uuid, payload, response=response
        # )
        # if response is False:
        #     return None
        #
        # if resp is None:
        #     resp = await self.client.read_gatt_char(characteristic_uuid)
        #
        # return resp


BleIO = ActiveBleIO
