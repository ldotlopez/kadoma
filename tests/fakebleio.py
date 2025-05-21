from __future__ import annotations


class BLEIO:
    def __init__(self, address: str):
        # self.client = BleakClient(address)
        pass

    async def __aenter__(self) -> BLEIO:
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
