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
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from types import TracebackType

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakDeviceNotFoundError

from .consts import BLUETOOTH_TIMEOUT, NOTIFY_CHAR_UUID, WRITE_CHAR_UUID

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

CommandCode = int
CommandParams = list[tuple[int, int]]


@asynccontextmanager
async def get_transport(
    address_or_ble_device: str | BLEDevice,
) -> AsyncIterator[Transport]:
    if isinstance(address_or_ble_device, str):
        LOGGER.debug(f"scanning for BLE device with address '{address_or_ble_device}'")
        ble_device = await BleakScanner.find_device_by_address(
            address_or_ble_device, timeout=BLUETOOTH_TIMEOUT
        )
        if ble_device is None:
            raise BleakDeviceNotFoundError(address_or_ble_device)

        address_or_ble_device = ble_device

    elif isinstance(address_or_ble_device, BLEDevice) and hasattr(
        address_or_ble_device, "name"
    ):
        pass
    else:
        raise TypeError(address_or_ble_device)

    async with BleakClient(address_or_ble_device, timeout=BLUETOOTH_TIMEOUT) as client:
        # Little hack to make property' name' available on the BleakClient
        setattr(client, "name", getattr(client, "name", address_or_ble_device.name))

        async with Transport(client) as transport:
            yield transport


class Transport:
    def __init__(self, client: BleakClient) -> None:
        self.client = client
        self.futures: dict[CommandCode, asyncio.Future] = {}
        self.partial: PartialPacket | None = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        await self.stop()

    async def start(self):
        if self.client._backend.__class__.__name__ == "BleakClientBlueZDBus":  # type: ignore
            await self.client._backend._acquire_mtu()  # type: ignore

        await self.client.start_notify(NOTIFY_CHAR_UUID, self.notify_handler)

    async def stop(self):
        await self.client.stop_notify(NOTIFY_CHAR_UUID)
        while self.futures:
            future = self.futures.pop(next(iter(self.futures.keys())))
            future.cancel()

    async def send_command(
        self, cmd: CommandCode, params: CommandParams | None = None
    ) -> tuple[int, CommandParams]:
        lenght, cmdb, paramsb = build_packet_parts(cmd, params)
        data = lenght + cmdb + paramsb

        LOGGER.debug(f"send cmd={cmdb.hex(':')}, params={paramsb.hex(':')}")

        # Use command ID has key
        futurekey = get_command_id_from_packet(data)

        if futurekey in self.futures:
            LOGGER.debug("+- canceling exisisting task")
            self.futures[futurekey].cancel()
            self.futures.pop(futurekey)

        self.futures[futurekey] = asyncio.Future()

        LOGGER.debug("+- sending data")
        async with asyncio.timeout(BLUETOOTH_TIMEOUT):
            await self.send_bytes(data)

        LOGGER.debug("+- waiting for response")
        async with asyncio.timeout(BLUETOOTH_TIMEOUT):
            await self.futures[futurekey]

        response = self.futures[futurekey].result()
        del self.futures[futurekey]

        LOGGER.debug("+- got response")
        return response

    async def send_bytes(self, data: bytearray):
        LOGGER.debug(f"send packet: {data.hex(':')}")

        for idx, chunk in enumerate(self.packet_chunk_it(data)):
            chunk.insert(0, idx)
            LOGGER.debug(f"+- send chunk: {chunk.hex(':')}")
            await self.client.write_gatt_char(WRITE_CHAR_UUID, chunk)

    def packet_chunk_it(self, data: bytearray) -> Iterable[bytearray]:
        # Reserve one byte for chunk enumeration, see
        # https://github.com/hbldh/bleak/blob/develop/examples/mtu_size.py
        chunk_size = self.client.mtu_size - 3 - 1
        yield from chunkerize_packet(data, max_size=chunk_size)

    def notify_handler(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        LOGGER.debug(f"+- recv chunk: {data.hex(':')}")

        if data[0] == 0x00 and self.partial:
            LOGGER.warning(
                "got start chunk while expecting a continuation chunk,"
                + " it will be discarded"
                + f" ({data[:10].hex(':')})"
            )
            return

        if data[0] != 0x00 and not self.partial:
            LOGGER.warning(
                "got continuation chunk while expecting a start chunk,"
                + " it will be discarded"
                + f" ({data[:10].hex(':')})"
            )
            return

        if data[0] == 0x00:
            self.partial = PartialPacket(data)
        else:
            self.partial.add_chunk(data)  # type: ignore[union-attr]

        if not self.partial.is_complete:  # type: ignore[union-attr]
            return

        packet = self.partial.get_data()  # type: ignore[union-attr]
        futurekey = get_command_id_from_packet(packet)
        future = self.futures.get(futurekey)

        if not future:
            LOGGER.error(
                f"got unexpected packet with key={futurekey}, ignoring."
                + f" ({data[:10].hex(':')})"
            )
            self.partial = None
            return

        if future.done():
            LOGGER.error("Internal state error, this should not happend.")
            self.partial = None
            return

        cmd, params = parse_packet(packet)
        LOGGER.debug(f"recv packet: {packet.hex(':')}")
        future.set_result((cmd, params))
        self.partial = None


class PartialPacket:
    def __init__(self, chunk: bytearray):
        self.chunks: dict[int, bytearray] = {}
        self.add_chunk(chunk)

    def add_chunk(self, chunk: bytearray):
        if not chunk:
            raise ValueError("chunk can't be empty")

        if len(chunk) < 2:
            raise ValueError("chunk is too small")

        chunk_idx, chunk_data = chunk[0], chunk[1:]
        self.chunks[chunk_idx] = chunk_data

    @property
    def current_size(self) -> int:
        return sum(len(x) for x in self.chunks.values())

    @property
    def expected_size(self) -> int | None:
        return self.chunks[0][0]

    @property
    def is_complete(self) -> bool:
        return self.current_size == self.expected_size

    def get_data(self) -> bytearray:
        if not self.is_complete:
            raise ValueError

        ret = bytearray()
        for idx in range(len(self.chunks)):
            ret.extend(self.chunks[idx])

        return ret


def build_packet(cmd: CommandCode, params: CommandParams | None = None) -> bytearray:
    preludeb, cmdb, paramsb = build_packet_parts(cmd, params)
    return preludeb + cmdb + paramsb


def build_packet_parts(
    cmd: CommandCode, params: CommandParams | None = None
) -> tuple[bytearray, bytearray, bytearray]:
    cmd_subpck = bytearray(cmd.to_bytes(2, "big"))

    if params:
        params_subpck = bytearray()
        for k, v in params:
            v_size = get_int_size(v)  # max(1, (v.bit_length() + 7) // 8)
            params_subpck.append(k)
            params_subpck.append(v_size)
            params_subpck.extend(v.to_bytes(v_size, "big"))
    else:
        params_subpck = bytearray([0x00, 0x00])

    pcklen = 2 + len(cmd_subpck) + len(params_subpck)
    return bytearray([pcklen, 0x00]), cmd_subpck, params_subpck


def parse_packet(data: bytearray) -> tuple[CommandCode, CommandParams]:
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


def chunkerize_packet(data, *, max_size: int) -> Iterable[bytearray]:
    yield from (
        bytearray(data[i : i + max_size]) for i in range(0, len(data), max_size)
    )


def get_command_id_from_packet(data: bytearray) -> int:
    return int.from_bytes(data[3:5], "big")


def get_int_size(i: int) -> int:
    return max(1, (i.bit_length() + 7) // 8)
