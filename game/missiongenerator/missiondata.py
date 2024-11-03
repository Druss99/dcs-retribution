from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from game.dcs.aircrafttype import AircraftType
from game.dcs.groundunittype import GroundUnitType
from game.missiongenerator.aircraft.flightdata import FlightData
from game.runways import RunwayData

if TYPE_CHECKING:
    from game.radio.radios import RadioFrequency
    from game.radio.tacan import TacanChannel
    from game.utils import Distance
    from uuid import UUID


@dataclass
class GroupInfo:
    group_name: str
    callsign: str
    freq: RadioFrequency
    blue: bool


@dataclass
class UnitInfo(GroupInfo):
    unit_name: str


@dataclass
class AwacsInfo(GroupInfo):
    """AWACS information for the kneeboard."""

    depature_location: Optional[str]
    start_time: datetime
    end_time: datetime


@dataclass
class TankerInfo(GroupInfo):
    """Tanker information for the kneeboard."""

    variant: str
    tacan: Optional[TacanChannel]
    start_time: datetime
    end_time: datetime


@dataclass
class CarrierInfo(UnitInfo):
    """Carrier information."""

    tacan: TacanChannel
    icls_channel: int | None
    link4_freq: RadioFrequency | None


@dataclass
class JtacInfo(UnitInfo):
    """JTAC information."""

    region: str
    code: str


@dataclass
class CargoInfo:
    """Cargo information."""

    unit_type: str = field(default_factory=str)
    spawn_zone: str = field(default_factory=str)
    amount: int = field(default=1)


@dataclass
class LogisticsInfo:
    """Logistics information."""

    pilot_names: list[str]
    transport: AircraftType
    blue: bool

    logistic_unit: str = field(default_factory=str)
    pickup_zone: str = field(default_factory=str)
    drop_off_zone: str = field(default_factory=str)
    target_zone: str = field(default_factory=str)
    cargo: list[CargoInfo] = field(default_factory=list)
    preload: bool = field(default=False)


@dataclass
class FrontlineUnitGroupsInfo:
    group_name: str
    unit_type: GroundUnitType


@dataclass
class MissionData:
    awacs: list[AwacsInfo] = field(default_factory=list)
    runways: list[RunwayData] = field(default_factory=list)
    carriers: list[CarrierInfo] = field(default_factory=list)
    flights: list[FlightData] = field(default_factory=list)
    tankers: list[TankerInfo] = field(default_factory=list)
    jtacs: list[JtacInfo] = field(default_factory=list)
    logistics: list[LogisticsInfo] = field(default_factory=list)
    cp_stack: dict[UUID, Distance] = field(default_factory=dict)
    player_frontline_groups: list[FrontlineUnitGroupsInfo] = field(default_factory=list)
    enemy_frontline_groups: list[FrontlineUnitGroupsInfo] = field(default_factory=list)
