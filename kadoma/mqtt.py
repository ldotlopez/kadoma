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
import json
import logging
import re
from functools import cached_property, lru_cache
from pathlib import Path

import aiomqtt
import click
import pydantic
import yaml

from .cli import click_async_wrapper, print_error
from .consts import UNIT_MANUFACTURER, UNIT_MODEL
from .knobs import FanSpeedValue, OperationModeValue
from .transport import get_transport
from .unit import Unit, UnitInfo

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
try:
    YAML_LOADER = yaml.CLoader
except AttributeError:
    YAML_LOADER = yaml.Loader


class Config(pydantic.BaseModel):
    daemon: ConfigDaemon
    mqtt: ConfigMqtt
    homeassistant: ConfigHomeAssistant


class ConfigDaemon(pydantic.BaseModel):
    address: str
    update_interval: int = 30


class ConfigMqtt(pydantic.BaseModel):
    hostname: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    ssl: bool = False
    root_topic: str = "kadoma/{address}"


class ConfigHomeAssistant(pydantic.BaseModel):
    enable: bool = True
    discovery_topic: str = "homeassistant/climate/{address}/config"
    friendly_name: str = "Main unit"


class MqttUnit:
    def __init__(self, name: str, address: str, cfg: ConfigMqtt):
        self.name = name
        self.address = address.upper()
        self.root_topic = cfg.root_topic.format(address=self.uaddress)
        self.payload_on = "ON"
        self.payload_off = "OFF"

    @cached_property
    def uaddress(self) -> str:
        return slugify(self.address.lower())

    @cached_property
    def power_command_topic(self) -> str:
        return f"{self.root_topic}/power/set"

    @cached_property
    def mode_state_topic(self) -> str:
        return f"{self.root_topic}/mode"

    @cached_property
    def mode_command_topic(self) -> str:
        return f"{self.root_topic}/mode/set"

    @cached_property
    def fan_mode_state_topic(self) -> str:
        return f"{self.root_topic}/fan"

    @cached_property
    def fan_mode_command_topic(self) -> str:
        return f"{self.root_topic}/fan/set"

    @cached_property
    def temperature_state_topic(self) -> str:
        return f"{self.root_topic}/target_temperature"

    @cached_property
    def temperature_command_topic(self) -> str:
        return f"{self.root_topic}/target_temperature/set"

    @cached_property
    def current_temperature_topic(self) -> str:
        return f"{self.root_topic}/current_temperature"

    @cached_property
    def discovery_topic(self) -> str:
        return f"homeassistant/climate/{self.uaddress}/config"

    @lru_cache
    def unit_operation_mode_as_ha_mode(self, operation_mode: OperationModeValue) -> str:
        repls = {"fan": "fan_only"}

        mode = operation_mode.name.lower()
        mode = repls.get(mode, mode)
        return mode

    @lru_cache
    def ha_mode_as_unit_operation_mode(self, mode: str) -> OperationModeValue:
        repls = {"fan_only": "fan"}
        mode = repls.get(mode, mode).upper()

        return OperationModeValue[mode]

    @lru_cache
    def unit_fan_speed_as_ha_fan_mode(self, fanspeed: FanSpeedValue) -> str:
        repls = {
            "mid_high": "medium_high",
            "mid": "medium",
            "mid_low": "medium_low",
        }
        ret = fanspeed.name.lower()
        return repls.get(ret, ret)

    @lru_cache
    def ha_fan_mode_as_unit_fan_speed(self, fan_mode: str) -> FanSpeedValue:
        repls = {"medium": "mid"}
        fan_mode = repls.get(fan_mode, fan_mode).upper()

        return FanSpeedValue[fan_mode]

    def discovery_payload(self, unit_info: UnitInfo) -> str:
        #
        # Build device info
        #
        device_unit_info = unit_info.get("Device Information", {})

        model = UNIT_MODEL
        if model_number := device_unit_info.get("Model Number String"):
            model = f"{model} {model_number}"

        sw_version = device_unit_info.get("Software Revision String", None)

        ids = [device_unit_info.get(k) for k in ["System ID"]]
        ids = [x for x in ids if x is not None]

        device = {
            "name": self.name,
            "manufacturer": UNIT_MANUFACTURER,
            "model": model,
            "sw_version": sw_version,
            "identifiers": ids,  # type: ignore[arg-type]
        }
        # modes = [x.name.lower() for x in knobs.OperationModeValue]
        # modes.remove("fan")
        # modes.remove("ventilation")
        # modes.append("fan_only")
        modes = ["auto", "off", "cool", "heat", "dry", "fan_only"]

        # fan_modes = [x.name.lower() for x in knobs.FanSpeedValue]
        fan_modes = ["auto", "high", "medium_high", "medium", "medium_low", "low"]

        d = {
            # properties
            "address": self.address,
            "name": self.name,
            "device": device,
            "object_id": slugify(self.name),
            "unique_id": slugify(self.name),
            "modes": modes,
            "fan_modes": fan_modes,
            # topics
            "payload_on": self.payload_on,
            "payload_off": self.payload_off,
            "power_command_topic": self.power_command_topic,
            "mode_state_topic": self.mode_state_topic,
            "mode_command_topic": self.mode_command_topic,
            "fan_mode_state_topic": self.fan_mode_state_topic,
            "fan_mode_command_topic": self.fan_mode_command_topic,
            "temperature_state_topic": self.temperature_state_topic,
            "temperature_command_topic": self.temperature_command_topic,
            "current_temperature_topic": self.current_temperature_topic,
            # options
            "optimistic": True,
        }

        return json.dumps(d)


def slugify(s: str) -> str:
    s_ = s.lower()
    s_ = re.sub("[^a-z0-9_]", "_", s_)
    s_ = re.sub("_+", "_", s_)

    return s_


async def unit_to_mqtt(
    *, cfg: Config, unit: Unit, mqtt: aiomqtt.Client, mqtt_info: MqttUnit
) -> None:

    unit_info = await unit.get_info()

    discovery_payload = mqtt_info.discovery_payload(unit_info)
    await mqtt.publish(topic=mqtt_info.discovery_topic, payload=discovery_payload)

    while True:
        status = await unit.get_status()

        # Update mode
        power_state = status.get("power_state", False)
        if power_state is True:
            operation_mode = status["operation_mode"]
            mode = mqtt_info.unit_operation_mode_as_ha_mode(operation_mode)
        else:
            mode = "off"

        await mqtt.publish(mqtt_info.mode_state_topic, mode)

        # Update fan speed
        if fans := status.get("fan_speed"):
            # Fixme: cooling vs. heating
            fan_mode = mqtt_info.unit_fan_speed_as_ha_fan_mode(fans[0])
        else:
            fan_mode = None

        await mqtt.publish(mqtt_info.fan_mode_state_topic, fan_mode)

        # target temperature
        if set_point := status.get("set_point", {}):
            # Fixme: cooling vs. heating
            temp = set_point.get("cooling_set_point")
        else:
            temp = None

        await mqtt.publish(mqtt_info.temperature_state_topic, temp)

        # # current temperature
        indoor_temp = status.get("sensors", {}).get("indoor")
        await mqtt.publish(mqtt_info.current_temperature_topic, indoor_temp)

        # Sleep
        await asyncio.sleep(cfg.daemon.update_interval)


async def mqtt_to_kadoma(
    *, cfg: Config, unit: Unit, mqtt: aiomqtt.Client, mqtt_info: MqttUnit
):

    # operation_mode_repl = {"fan_only": "fan"}
    # fan_speed_repl = {"medium": "mid"}

    await mqtt.subscribe(mqtt_info.power_command_topic)
    await mqtt.subscribe(mqtt_info.mode_command_topic)
    await mqtt.subscribe(mqtt_info.fan_mode_command_topic)
    await mqtt.subscribe(mqtt_info.temperature_command_topic)

    async for message in mqtt.messages:
        LOGGER.info(
            f"Got update: topic='{message.topic.value}' payload='{message.payload!r}'"
        )

        if message.topic.value == mqtt_info.power_command_topic:
            value = message.payload.decode()
            value = True if value == mqtt_info.payload_on else False
            LOGGER.info(f"Setting Unit power state to: {value}")
            await unit.power_state.update(value)

        elif message.topic.value == mqtt_info.mode_command_topic:
            value = message.payload.decode()
            if value == "off":
                await unit.power_state.update(False)
            else:
                operation_mode = mqtt_info.ha_mode_as_unit_operation_mode(value)
                await unit.power_state.update(True)
                await unit.operation_mode.update(operation_mode)

        elif message.topic.value == mqtt_info.fan_mode_command_topic:
            value = message.payload.decode()
            fan_speed = mqtt_info.ha_fan_mode_as_unit_fan_speed(value)

            LOGGER.info(f"Setting Unit fan speed: {fan_speed}")
            await unit.fan_speed.update(cooling=fan_speed, heating=fan_speed)

        elif message.topic.value == mqtt_info.temperature_command_topic:
            value = message.payload.decode()
            try:
                value = round(float(message.payload.decode()))
            except (ValueError, TypeError):
                LOGGER.error(f"Invalid temperature value '{message.payload!r}'")
                continue

            LOGGER.info(f"Setting Unit target temperature: {value}")
            await unit.set_point.update(cooling=value, heating=value)

        else:
            LOGGER.warning(f"Unknow topic {message.topic.value}")


@click.command
@click.option("--config", "-c", type=Path, required=True, help="BLE device address")
@click.option("--address", "-a", type=str, required=False, help="BLE device address")
@click_async_wrapper
async def main(config: Path, address: str | None):
    data = yaml.load(config.read_text(), Loader=YAML_LOADER)
    if address:
        daemoncfg = data.get("daemon", {}) | {"address": address}
        data = data | {"daemon": daemoncfg}

    cfg = Config(**data)
    address_slug = slugify(cfg.daemon.address.lower())

    cfg.daemon.address = cfg.daemon.address.upper()
    cfg.mqtt.root_topic = cfg.mqtt.root_topic.format(address=address_slug)
    cfg.homeassistant.discovery_topic = cfg.mqtt.root_topic.format(address=address_slug)

    async with aiomqtt.Client(cfg.mqtt.hostname, port=cfg.mqtt.port) as mqtt:
        async with get_transport(cfg.daemon.address) as transport:
            unit = Unit(transport)

            mqtt_info = MqttUnit(
                cfg=cfg.mqtt,
                address=unit.transport.client.address,
                name=unit.transport.client.name,
            )

            await asyncio.gather(
                unit_to_mqtt(cfg=cfg, mqtt=mqtt, unit=unit, mqtt_info=mqtt_info),
                mqtt_to_kadoma(cfg=cfg, mqtt=mqtt, unit=unit, mqtt_info=mqtt_info),
            )


if __name__ == "__main__":
    main()
