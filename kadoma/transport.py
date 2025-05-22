from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable, Type

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from types import TracebackType
from .consts import NOTIFY_CHAR_UUID, WRITE_CHAR_UUID

LOGGER = logging.getLogger(__name__)

Command = int
CommandParams = list[tuple[int, int]]


class PartialPacket:
    def __init__(self, chunk: bytearray):
        self.chunks: dict[int, bytearray] = {}
        self.add_chunk(chunk)

    def add_chunk(self, chunk: bytearray):
        self.chunks[chunk[0]] = chunk[1:]

    @property
    def current_size(self) -> int:
        return sum([len(x) for x in self.chunks.values()])

    @property
    def expected_size(self) -> int | None:
        if 0 not in self.chunks:
            return None

        return self.chunks[0][0]

    @property
    def is_complete(self) -> bool:
        return self.current_size == self.expected_size

    def get_data(self) -> bytearray:
        if not self.is_complete:
            raise ValueError

        ret = bytearray()
        for idx in range(0, len(self.chunks)):
            ret += self.chunks[idx]

        return ret


class Transport:
    def __init__(self, client: BleakClient) -> None:
        self.client = client
        self.futures: dict[Any, asyncio.Future] = {}
        self.partial: PartialPacket | None = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        await self.stop()

    async def start(self):
        await self.client.start_notify(NOTIFY_CHAR_UUID, self.notify_handler)
        LOGGER.debug("notify_handler ready")
        if self.client._backend.__class__.__name__ == "BleakClientBlueZDBus":  # type: ignore
            await self.client._backend._acquire_mtu()  # type: ignore

    async def stop(self):
        await self.client.stop_notify(NOTIFY_CHAR_UUID)
        for future in self.futures.values():
            future.cancel()

    def notify_handler(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        LOGGER.debug(f"notified with: {data.hex(':')}")

        if data[0] == 0x00 and self.partial:
            LOGGER.warning("OOB packet, discard")
            return

        if data[0] != 0x00 and not self.partial:
            LOGGER.error("Received continuation packet without a start packet.")
            return

        if data[0] == 0x00:
            self.partial = PartialPacket(data)
        else:
            self.partial.add_chunk(data)  # type: ignore[union-attr]

        if not self.partial.is_complete:  # type: ignore[union-attr]
            return

        packet = self.partial.get_data()  # type: ignore[union-attr]
        LOGGER.debug(f"Packet rebuilded: {packet.hex(':')}")
        futurekey = get_command_id_from_packet(packet)

        future = self.futures.get(futurekey)
        if not future:
            LOGGER.error("packet rebuilded but not expected, ignoring (not in futures)")
            self.partial = None
            return

        if future.done():
            LOGGER.error("internal state error")
            self.partial = None
            return

        cmd, params = parse_packet(packet)
        future.set_result((cmd, params))
        self.partial = None

    async def send_command(
        self, cmd: Command, params: CommandParams | None = None
    ) -> tuple[int, CommandParams]:
        lenght, cmdb, paramsb = build_packet_parts(cmd, params)
        data = lenght + cmdb + paramsb

        LOGGER.info(
            f"send data {data.hex(':')}"
            + f" (cmd_id={cmdb.hex(':')}, params={paramsb.hex(':')})"
        )

        # Use command ID has key
        futurekey = get_command_id_from_packet(data)

        if futurekey in self.futures:
            LOGGER.debug(
                "previous future associated with this command found, canceling it."
            )
            self.futures[futurekey].cancel()
            self.futures.pop(futurekey)

        self.futures[futurekey] = (
            asyncio.Future()
        )  # asyncio.get_running_loop().create_future()
        await self.send_bytes(data)
        LOGGER.info(f"waiting for response to command {cmd}")
        await self.futures[futurekey]

        response = self.futures[futurekey].result()
        del self.futures[futurekey]

        LOGGER.info(f"got response: {response}")
        return response

    async def send_bytes(self, data: bytearray):
        LOGGER.info(f"sending data {data.hex(':')}")

        for idx, chunk in enumerate(self.packet_chunk_it(data)):
            chunk.insert(0, idx)
            LOGGER.info(f"+- sending chunk {chunk.hex(':')}")
            await self.client.write_gatt_char(WRITE_CHAR_UUID, chunk)

    def packet_chunk_it(self, data: bytearray) -> Iterable[bytearray]:
        # Reserve one byte for chunk enumeration, see
        # https://github.com/hbldh/bleak/blob/develop/examples/mtu_size.py
        chunk_size = self.client.mtu_size - 3 - 1
        yield from chunkerize_packet(data, max_size=chunk_size)


def build_packet(cmd: Command, params: CommandParams | None = None) -> bytearray:
    preludeb, cmdb, paramsb = build_packet_parts(cmd, params)
    return preludeb + cmdb + paramsb


def build_packet_parts(
    cmd: Command, params: CommandParams | None = None
) -> tuple[bytearray, bytearray, bytearray]:
    cmd_subpck = bytearray(cmd.to_bytes(2, "big"))

    if params:
        params_subpck = bytearray()
        for k, v in params:
            v_size = max(1, (v.bit_length() + 7) // 8)
            params_subpck.append(k)
            params_subpck.append(v_size)
            params_subpck.extend(v.to_bytes(v_size, "big"))
    else:
        params_subpck = bytearray([0x00, 0x00])

    pcklen = 2 + len(cmd_subpck) + len(params_subpck)
    return bytearray([pcklen, 0x00]), cmd_subpck, params_subpck


def parse_packet(data: bytearray) -> tuple[Command, CommandParams]:
    if not data:
        raise ValueError("data is empty", data)

    if len(data) < 4:
        raise ValueError("data is too small", data)

    if len(data) != data[0]:
        raise ValueError(f"expected packet length {data[0]}, got {len(data)}", data)

    cmd = int.from_bytes(data[2:4])
    params = []

    idx = 4
    while idx < data[0]:
        key = data[idx]
        v_size = data[idx + 1]
        value = int.from_bytes(data[idx + 2 : idx + 2 + v_size], "big")
        params.append((key, value))

        idx = idx + 1 + 1 + v_size

    return cmd, params


def get_command_id_from_packet(data: bytearray) -> int:
    return int.from_bytes(data[3:5], "big")


def chunkerize_packet(data, *, max_size: int) -> Iterable[bytearray]:
    yield from (
        bytearray(data[i : i + max_size]) for i in range(0, len(data), max_size)
    )
