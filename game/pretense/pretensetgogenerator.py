"""Generators for creating the groups for ground objectives.

The classes in this file are responsible for creating the vehicle groups, ship
groups, statics, missile sites, and AA sites for the mission. Each of these
objectives is defined in the Theater by a TheaterGroundObject. These classes
create the pydcs groups and statics for those areas and add them to the mission.
"""

from __future__ import annotations

import random
import logging
from collections import defaultdict
from typing import Dict, Optional, TYPE_CHECKING, Tuple, Type, Iterator

from dcs import Mission, Point
from dcs.countries import *
from dcs.country import Country
from dcs.ships import Stennis, CVN_71, CVN_72, CVN_73, CVN_75, Forrestal, LHA_Tarawa
from dcs.unitgroup import StaticGroup, VehicleGroup
from dcs.unittype import VehicleType

from game.coalition import Coalition
from game.data.units import UnitClass
from game.dcs.groundunittype import GroundUnitType
from game.missiongenerator.groundforcepainter import (
    GroundForcePainter,
)
from game.missiongenerator.missiondata import MissionData, CarrierInfo
from game.missiongenerator.tgogenerator import (
    TgoGenerator,
    HelipadGenerator,
    GroundSpawnRoadbaseGenerator,
    GroundSpawnGenerator,
    GroundObjectGenerator,
    CarrierGenerator,
    LhaGenerator,
    MissileSiteGenerator,
    GenericCarrierGenerator,
)
from game.point_with_heading import PointWithHeading
from game.pretense.pretenseflightgroupspawner import PretenseNameGenerator
from game.radio.radios import RadioRegistry
from game.radio.tacan import TacanRegistry, TacanBand, TacanUsage
from game.runways import RunwayData
from game.theater import (
    ControlPoint,
    TheaterGroundObject,
    TheaterUnit,
    NavalControlPoint,
    PresetLocation,
    Player,
)
from game.theater.theatergroundobject import (
    CarrierGroundObject,
    LhaGroundObject,
    MissileSiteGroundObject,
    BuildingGroundObject,
    VehicleGroupGroundObject,
    GenericCarrierGroundObject,
)
from game.theater.theatergroup import TheaterGroup
from game.unitmap import UnitMap
from game.utils import Heading
from pydcs_extensions import (
    Char_M551_Sheridan,
    CH_BVS10,
    RBS_70,
    RBS_90,
    VAB__50,
    VAB_T20_13,
)

if TYPE_CHECKING:
    from game import Game

FARP_FRONTLINE_DISTANCE = 10000
AA_CP_MIN_DISTANCE = 40000
PRETENSE_GROUND_UNIT_GROUP_SIZE = 5
PRETENSE_GROUND_UNITS_TO_REMOVE_FROM_ASSAULT = [
    vehicles.Armor.Stug_III,
    vehicles.Artillery.Grad_URAL,
]
PRETENSE_AMPHIBIOUS_UNITS = [
    vehicles.Unarmed.LARC_V,
    vehicles.Armor.AAV7,
    vehicles.Armor.LAV_25,
    vehicles.Armor.TPZ,
    vehicles.Armor.PT_76,
    vehicles.Armor.BMD_1,
    vehicles.Armor.BMP_1,
    vehicles.Armor.BMP_2,
    vehicles.Armor.BMP_3,
    vehicles.Armor.BTR_80,
    vehicles.Armor.BTR_82A,
    vehicles.Armor.BRDM_2,
    vehicles.Armor.BTR_D,
    vehicles.Armor.MTLB,
    vehicles.Armor.ZBD04A,
    vehicles.Armor.VAB_Mephisto,
    VAB__50,
    VAB_T20_13,
    Char_M551_Sheridan,
]


class PretenseGroundObjectGenerator(GroundObjectGenerator):
    """generates the DCS groups and units from the TheaterGroundObject"""

    def __init__(
        self,
        ground_object: TheaterGroundObject,
        country: Country,
        game: Game,
        mission: Mission,
        unit_map: UnitMap,
    ) -> None:
        super().__init__(
            ground_object,
            country,
            game,
            mission,
            unit_map,
        )

        self.ground_object = ground_object
        self.country = country
        self.game = game
        self.m = mission
        self.unit_map = unit_map
        self.coalition = ground_object.coalition

    @property
    def culled(self) -> bool:
        return self.game.iads_considerate_culling(self.ground_object)

    @staticmethod
    def ground_unit_of_class(
        coalition: Coalition, unit_class: UnitClass
    ) -> Optional[GroundUnitType]:
        """
        Returns a GroundUnitType of the specified class that belongs to the
        TheaterGroundObject faction.

        Units, which are known to have pathfinding issues in Pretense missions
        are removed based on a pre-defined list.

        Args:
            coalition: Coalition to return the unit for.
            unit_class: Class of unit to return.
        """
        faction_units = (
            set(coalition.faction.frontline_units)
            | set(coalition.faction.artillery_units)
            | set(coalition.faction.air_defense_units)
            | set(coalition.faction.logistics_units)
        )
        of_class = list({u for u in faction_units if u.unit_class is unit_class})

        # Remove units from list with known pathfinding issues in Pretense missions
        for unit_to_remove in PRETENSE_GROUND_UNITS_TO_REMOVE_FROM_ASSAULT:
            for groundunittype_to_remove in GroundUnitType.for_dcs_type(unit_to_remove):
                if groundunittype_to_remove in of_class:
                    of_class.remove(groundunittype_to_remove)

        if len(of_class) > 0:
            return random.choice(of_class)
        else:
            return None

    def generate_ground_unit_of_class(
        self,
        unit_class: UnitClass,
        group: TheaterGroup,
        vehicle_units: list[TheaterUnit],
        cp_name: str,
        group_role: str,
        max_num: int,
    ) -> None:
        """
        Generates a single land based TheaterUnit for a Pretense unit group
        for a specific TheaterGroup, provided that the group still has room
        (defined by the max_num argument). Land based groups don't have
        restrictions on the unit types, other than that they must be
        accessible by the faction and must be of the specified class.

        Generated units are placed 30 meters from the TheaterGroup
        position in a random direction.

        Args:
            unit_class: Class of unit to generate.
            group: The TheaterGroup to generate the unit/group for.
            vehicle_units: List of TheaterUnits. The new unit will be appended to this list.
            cp_name: Name of the Control Point.
            group_role: Pretense group role, "support" or "assault".
            max_num: Maximum number of units to generate per group.
        """

        if self.coalition.faction.has_access_to_unit_class(unit_class):
            unit_type = self.ground_unit_of_class(self.coalition, unit_class)
            if unit_type is not None and len(vehicle_units) < max_num:
                unit_id = self.game.next_unit_id()
                unit_name = f"{cp_name}-{group_role}-{unit_id}"

                spread_out_heading = random.randrange(1, 360)
                spread_out_position = group.position.point_from_heading(
                    spread_out_heading, 30
                )
                ground_unit_pos = PointWithHeading.from_point(
                    spread_out_position, group.position.heading
                )

                theater_unit = TheaterUnit(
                    unit_id,
                    unit_name,
                    unit_type.dcs_unit_type,
                    ground_unit_pos,
                    group.ground_object,
                )
                vehicle_units.append(theater_unit)

    def generate_amphibious_unit_of_class(
        self,
        unit_class: UnitClass,
        group: TheaterGroup,
        vehicle_units: list[TheaterUnit],
        cp_name: str,
        group_role: str,
        max_num: int,
    ) -> None:
        """
        Generates a single amphibious TheaterUnit for a Pretense unit group
        for a specific TheaterGroup, provided that the group still has room
        (defined by the max_num argument). Amphibious units are selected
        out of a pre-defined list. Units which the faction has access to
        are preferred, but certain default unit types are selected as
        a fall-back to ensure that all the generated units can swim.

        Generated units are placed 30 meters from the TheaterGroup
        position in a random direction.

        Args:
            unit_class: Class of unit to generate.
            group: The TheaterGroup to generate the unit/group for.
            vehicle_units: List of TheaterUnits. The new unit will be appended to this list.
            cp_name: Name of the Control Point.
            group_role: Pretense group role, "support" or "assault".
            max_num: Maximum number of units to generate per group.
        """
        unit_type = None
        faction = self.coalition.faction
        is_player = Player.BLUE
        side = (
            2
            if self.country == self.game.coalition_for(is_player).faction.country
            else 1
        )
        default_amphibious_unit = unit_type
        default_logistics_unit = unit_type
        default_tank_unit_blue = unit_type
        default_apc_unit_blue = unit_type
        default_ifv_unit_blue = unit_type
        default_recon_unit_blue = unit_type
        default_atgm_unit_blue = unit_type
        default_tank_unit_red = unit_type
        default_apc_unit_red = unit_type
        default_ifv_unit_red = unit_type
        default_recon_unit_red = unit_type
        default_atgm_unit_red = unit_type
        default_ifv_unit_chinese = unit_type
        pretense_amphibious_units = PRETENSE_AMPHIBIOUS_UNITS
        random.shuffle(pretense_amphibious_units)
        for unit in pretense_amphibious_units:
            for groundunittype in GroundUnitType.for_dcs_type(unit):
                if unit == vehicles.Unarmed.LARC_V:
                    default_logistics_unit = groundunittype
                elif unit == Char_M551_Sheridan:
                    default_tank_unit_blue = groundunittype
                elif unit == vehicles.Armor.AAV7:
                    default_apc_unit_blue = groundunittype
                elif unit == vehicles.Armor.LAV_25:
                    default_ifv_unit_blue = groundunittype
                elif unit == vehicles.Armor.TPZ:
                    default_recon_unit_blue = groundunittype
                elif unit == vehicles.Armor.VAB_Mephisto:
                    default_atgm_unit_blue = groundunittype
                elif unit == vehicles.Armor.PT_76:
                    default_tank_unit_red = groundunittype
                elif unit == vehicles.Armor.BTR_80:
                    default_apc_unit_red = groundunittype
                elif unit == vehicles.Armor.BMD_1:
                    default_ifv_unit_red = groundunittype
                elif unit == vehicles.Armor.BRDM_2:
                    default_recon_unit_red = groundunittype
                elif unit == vehicles.Armor.BTR_D:
                    default_atgm_unit_red = groundunittype
                elif unit == vehicles.Armor.ZBD04A:
                    default_ifv_unit_chinese = groundunittype
                elif unit == vehicles.Armor.MTLB:
                    default_amphibious_unit = groundunittype
                if self.coalition.faction.has_access_to_dcs_type(unit):
                    if groundunittype.unit_class == unit_class:
                        unit_type = groundunittype
                        break
        if unit_type is None:
            if unit_class == UnitClass.LOGISTICS:
                unit_type = default_logistics_unit
            elif faction.country.id == China.id:
                unit_type = default_ifv_unit_chinese
            elif side == 2 and unit_class == UnitClass.TANK:
                if faction.mod_settings is not None and faction.mod_settings.frenchpack:
                    unit_type = default_tank_unit_blue
                else:
                    unit_type = default_apc_unit_blue
            elif side == 2 and unit_class == UnitClass.IFV:
                unit_type = default_ifv_unit_blue
            elif side == 2 and unit_class == UnitClass.APC:
                unit_type = default_apc_unit_blue
            elif side == 2 and unit_class == UnitClass.ATGM:
                unit_type = default_atgm_unit_blue
            elif side == 2 and unit_class == UnitClass.RECON:
                unit_type = default_recon_unit_blue
            elif side == 1 and unit_class == UnitClass.TANK:
                unit_type = default_tank_unit_red
            elif side == 1 and unit_class == UnitClass.IFV:
                unit_type = default_ifv_unit_red
            elif side == 1 and unit_class == UnitClass.APC:
                unit_type = default_apc_unit_red
            elif side == 1 and unit_class == UnitClass.ATGM:
                unit_type = default_atgm_unit_red
            elif side == 1 and unit_class == UnitClass.RECON:
                unit_type = default_recon_unit_red
            else:
                unit_type = default_amphibious_unit
        if unit_type is not None and len(vehicle_units) < max_num:
            unit_id = self.game.next_unit_id()
            unit_name = f"{cp_name}-{group_role}-{unit_id}"

            spread_out_heading = random.randrange(1, 360)
            spread_out_position = group.position.point_from_heading(
                spread_out_heading, 30
            )
            ground_unit_pos = PointWithHeading.from_point(
                spread_out_position, group.position.heading
            )

            theater_unit = TheaterUnit(
                unit_id,
                unit_name,
                unit_type.dcs_unit_type,
                ground_unit_pos,
                group.ground_object,
            )
            vehicle_units.append(theater_unit)

    def generate(self) -> None:
        if self.culled:
            return
        cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(
            self.ground_object.control_point.name
        )
        country_name_trimmed = "".join(
            [i for i in self.country.shortname.lower() if i.isalpha()]
        )

        for group in self.ground_object.groups:
            vehicle_units: list[TheaterUnit] = []

            for unit in group.units:
                if unit.is_static:
                    # Add supply convoy
                    group_role = "supply"
                    group_name = f"{cp_name_trimmed}-{country_name_trimmed}-{group_role}-{group.id}"
                    group.name = group_name

                    self.generate_ground_unit_of_class(
                        UnitClass.LOGISTICS,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE,
                    )
                elif unit.is_vehicle and unit.alive:
                    # Add armor group
                    group_role = "assault"
                    group_name = f"{cp_name_trimmed}-{country_name_trimmed}-{group_role}-{group.id}"
                    group.name = group_name

                    self.generate_ground_unit_of_class(
                        UnitClass.TANK,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE - 4,
                    )
                    self.generate_ground_unit_of_class(
                        UnitClass.TANK,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE - 3,
                    )
                    self.generate_ground_unit_of_class(
                        UnitClass.ATGM,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE - 2,
                    )
                    self.generate_ground_unit_of_class(
                        UnitClass.APC,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE - 1,
                    )
                    self.generate_ground_unit_of_class(
                        UnitClass.IFV,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE,
                    )
                    self.generate_ground_unit_of_class(
                        UnitClass.RECON,
                        group,
                        vehicle_units,
                        cp_name_trimmed,
                        group_role,
                        PRETENSE_GROUND_UNIT_GROUP_SIZE,
                    )
                    if random.randrange(0, 100) > 75:
                        self.generate_ground_unit_of_class(
                            UnitClass.SHORAD,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE,
                        )
                elif unit.is_ship and unit.alive:
                    # Attach this group to the closest naval group, if available
                    control_point = self.ground_object.control_point
                    for (
                        other_cp
                    ) in self.game.theater.closest_friendly_control_points_to(
                        self.ground_object.control_point
                    ):
                        if other_cp.is_fleet:
                            control_point = other_cp
                            break

                    cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(
                        control_point.name
                    )
                    is_player = Player.BLUE
                    side = (
                        2
                        if self.country
                        == self.game.coalition_for(is_player).faction.country
                        else 1
                    )

                    try:
                        number_of_supply_groups = len(
                            self.game.pretense_ground_supply[side][cp_name_trimmed]
                        )
                    except KeyError:
                        number_of_supply_groups = 0
                        self.game.pretense_ground_supply[side][cp_name_trimmed] = list()
                        self.game.pretense_ground_assault[side][
                            cp_name_trimmed
                        ] = list()

                    if number_of_supply_groups == 0:
                        # Add supply convoy
                        group_role = "supply"
                        group_name = f"{cp_name_trimmed}-{country_name_trimmed}-{group_role}-{group.id}"
                        group.name = group_name

                        self.generate_amphibious_unit_of_class(
                            UnitClass.LOGISTICS,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE,
                        )
                    else:
                        # Add armor group
                        group_role = "assault"
                        group_name = f"{cp_name_trimmed}-{country_name_trimmed}-{group_role}-{group.id}"
                        group.name = group_name

                        self.generate_amphibious_unit_of_class(
                            UnitClass.TANK,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE - 4,
                        )
                        self.generate_amphibious_unit_of_class(
                            UnitClass.TANK,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE - 3,
                        )
                        self.generate_amphibious_unit_of_class(
                            UnitClass.ATGM,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE - 2,
                        )
                        self.generate_amphibious_unit_of_class(
                            UnitClass.APC,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE - 1,
                        )
                        self.generate_amphibious_unit_of_class(
                            UnitClass.IFV,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE,
                        )
                        self.generate_amphibious_unit_of_class(
                            UnitClass.RECON,
                            group,
                            vehicle_units,
                            cp_name_trimmed,
                            group_role,
                            PRETENSE_GROUND_UNIT_GROUP_SIZE,
                        )
            if vehicle_units:
                self.create_vehicle_group(group.group_name, vehicle_units)

    def create_vehicle_group(
        self, group_name: str, units: list[TheaterUnit]
    ) -> VehicleGroup:
        vehicle_group: Optional[VehicleGroup] = None

        control_point = self.ground_object.control_point
        for unit in self.ground_object.units:
            if unit.is_ship:
                # Unit is naval/amphibious. Attach this group to the closest naval group, if available.
                for other_cp in self.game.theater.closest_friendly_control_points_to(
                    self.ground_object.control_point
                ):
                    if other_cp.is_fleet:
                        control_point = other_cp
                        break

        cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(
            control_point.name
        )
        is_player = Player.BLUE
        side = (
            2
            if self.country == self.game.coalition_for(is_player).faction.country
            else 1
        )

        for unit in units:
            assert issubclass(unit.type, VehicleType)
            faction = self.coalition.faction
            if vehicle_group is None:
                vehicle_group = self.m.vehicle_group(
                    self.country,
                    group_name,
                    unit.type,
                    position=unit.position,
                    heading=unit.position.heading.degrees,
                )
                vehicle_group.units[0].player_can_drive = True
                self.enable_eplrs(vehicle_group, unit.type)
                vehicle_group.units[0].name = unit.unit_name
                self.set_alarm_state(vehicle_group)
                GroundForcePainter(faction, vehicle_group.units[0]).apply_livery()

                group_role = group_name.split("-")[2]
                if group_role == "supply":
                    self.game.pretense_ground_supply[side][cp_name_trimmed].append(
                        f"{vehicle_group.name}"
                    )
                elif group_role == "assault":
                    self.game.pretense_ground_assault[side][cp_name_trimmed].append(
                        f"{vehicle_group.name}"
                    )
            else:
                vehicle_unit = self.m.vehicle(unit.unit_name, unit.type)
                vehicle_unit.player_can_drive = True
                vehicle_unit.position = unit.position
                vehicle_unit.heading = unit.position.heading.degrees
                GroundForcePainter(faction, vehicle_unit).apply_livery()
                vehicle_group.add_unit(vehicle_unit)
            self._register_theater_unit(unit, vehicle_group.units[-1])
        if vehicle_group is None:
            raise RuntimeError(f"Error creating VehicleGroup for {group_name}")
        return vehicle_group


class PretenseGenericCarrierGenerator(GenericCarrierGenerator):
    """Base type for carrier group generation.

    Used by both CV(N) groups and LHA groups.
    """

    def __init__(
        self,
        ground_object: GenericCarrierGroundObject,
        control_point: NavalControlPoint,
        country: Country,
        game: Game,
        mission: Mission,
        radio_registry: RadioRegistry,
        tacan_registry: TacanRegistry,
        icls_alloc: Iterator[int],
        runways: Dict[str, RunwayData],
        unit_map: UnitMap,
        mission_data: MissionData,
    ) -> None:
        super().__init__(
            ground_object,
            control_point,
            country,
            game,
            mission,
            radio_registry,
            tacan_registry,
            icls_alloc,
            runways,
            unit_map,
            mission_data,
        )
        self.ground_object = ground_object
        self.control_point = control_point
        self.radio_registry = radio_registry
        self.tacan_registry = tacan_registry
        self.icls_alloc = icls_alloc
        self.runways = runways
        self.mission_data = mission_data

    def generate(self) -> None:
        if self.control_point.frequency is not None:
            atc = self.control_point.frequency
            if atc not in self.radio_registry.allocated_channels:
                self.radio_registry.reserve(atc)
        else:
            atc = self.radio_registry.alloc_uhf()

        for g_id, group in enumerate(self.ground_object.groups):
            if not group.units:
                logging.warning(f"Found empty carrier group in {self.control_point}")
                continue

            ship_units = []
            for unit in group.units:
                if unit.alive:
                    # All alive Ships
                    print(
                        f"Added {unit.unit_name} to ship_units of group {group.group_name}"
                    )
                    ship_units.append(unit)

            if not ship_units:
                # Empty array (no alive units), skip this group
                continue

            ship_group = self.create_ship_group(group.group_name, ship_units, atc)

            if self.game.settings.pretense_carrier_steams_into_wind:
                # Always steam into the wind, even if the carrier is being moved.
                # There are multiple unsimulated hours between turns, so we can
                # count those as the time the carrier uses to move and the mission
                # time as the recovery window.
                brc = self.steam_into_wind(ship_group)
            else:
                brc = Heading(0)

            # Set Carrier Specific Options
            if g_id == 0 and self.control_point.runway_is_operational():
                # Get Correct unit type for the carrier.
                # This will upgrade to super carrier if option is enabled
                carrier_type = self.carrier_type
                if carrier_type is None:
                    raise RuntimeError(
                        f"Error generating carrier group for {self.control_point.name}"
                    )
                ship_group.units[0].type = carrier_type.id
                if self.control_point.tacan is None:
                    tacan = self.tacan_registry.alloc_for_band(
                        TacanBand.X, TacanUsage.TransmitReceive
                    )
                else:
                    tacan = self.control_point.tacan
                if self.control_point.tcn_name is None:
                    tacan_callsign = self.tacan_callsign()
                else:
                    tacan_callsign = self.control_point.tcn_name
                link4 = None
                link4carriers = [Stennis, CVN_71, CVN_72, CVN_73, CVN_75, Forrestal]
                if carrier_type in link4carriers:
                    if self.control_point.link4 is None:
                        link4 = self.radio_registry.alloc_uhf()
                    else:
                        link4 = self.control_point.link4
                icls = None
                icls_name = self.control_point.icls_name
                if carrier_type in link4carriers or carrier_type == LHA_Tarawa:
                    if self.control_point.icls_channel is None:
                        icls = next(self.icls_alloc)
                    else:
                        icls = self.control_point.icls_channel
                self.activate_beacons(
                    ship_group, tacan, tacan_callsign, icls, icls_name, link4
                )
                self.add_runway_data(
                    brc or Heading.from_degrees(0), atc, tacan, tacan_callsign, icls
                )
                self.mission_data.carriers.append(
                    CarrierInfo(
                        group_name=ship_group.name,
                        unit_name=ship_group.units[0].name,
                        callsign=tacan_callsign,
                        freq=atc,
                        tacan=tacan,
                        icls_channel=icls,
                        link4_freq=link4,
                        blue=self.control_point.captured,
                        ship_group=ship_group,
                    )
                )


class PretenseCarrierGenerator(PretenseGenericCarrierGenerator):
    def tacan_callsign(self) -> str:
        # TODO: Assign these properly.
        return random.choice(
            [
                "STE",
                "CVN",
                "CVH",
                "CCV",
                "ACC",
                "ARC",
                "GER",
                "ABR",
                "LIN",
                "TRU",
            ]
        )


class PretenseLhaGenerator(PretenseGenericCarrierGenerator):
    def tacan_callsign(self) -> str:
        # TODO: Assign these properly.
        return random.choice(
            [
                "LHD",
                "LHA",
                "LHB",
                "LHC",
                "LHD",
                "LDS",
            ]
        )


class PretenseTgoGenerator(TgoGenerator):
    """Creates DCS groups and statics for the theater during mission generation.

    Most of the work of group/static generation is delegated to the other
    generator classes. This class is responsible for finding each of the
    locations for spawning ground objects, determining their types, and creating
    the appropriate generators.
    """

    def __init__(
        self,
        mission: Mission,
        game: Game,
        radio_registry: RadioRegistry,
        tacan_registry: TacanRegistry,
        unit_map: UnitMap,
        mission_data: MissionData,
    ) -> None:
        super().__init__(
            mission,
            game,
            radio_registry,
            tacan_registry,
            unit_map,
            mission_data,
        )

        self.m = mission
        self.game = game
        self.radio_registry = radio_registry
        self.tacan_registry = tacan_registry
        self.unit_map = unit_map
        self.icls_alloc = iter(range(1, 21))
        self.runways: Dict[str, RunwayData] = {}
        self.helipads: dict[ControlPoint, list[StaticGroup]] = defaultdict(list)
        self.ground_spawns_roadbase: dict[
            ControlPoint, list[Tuple[StaticGroup, Point]]
        ] = defaultdict(list)
        self.ground_spawns: dict[ControlPoint, list[Tuple[StaticGroup, Point]]] = (
            defaultdict(list)
        )
        self.mission_data = mission_data

    def generate(self) -> None:
        for cp in self.game.theater.controlpoints:
            cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(cp.name)
            for side in range(1, 3):
                if cp_name_trimmed not in self.game.pretense_ground_supply[side]:
                    self.game.pretense_ground_supply[side][cp_name_trimmed] = list()
                if cp_name_trimmed not in self.game.pretense_ground_assault[side]:
                    self.game.pretense_ground_assault[side][cp_name_trimmed] = list()

            # First generate units for the coalition, which initially holds this CP
            country = self.m.country(cp.coalition.faction.country.name)

            # Generate helipads
            helipad_gen = HelipadGenerator(
                self.m, cp, self.game, self.radio_registry, self.tacan_registry
            )
            helipad_gen.generate()
            self.helipads[cp] = helipad_gen.helipads

            # Generate Highway Strip slots
            ground_spawn_roadbase_gen = GroundSpawnRoadbaseGenerator(
                self.m, cp, self.game, self.radio_registry, self.tacan_registry
            )
            ground_spawn_roadbase_gen.generate()
            self.ground_spawns_roadbase[cp] = (
                ground_spawn_roadbase_gen.ground_spawns_roadbase
            )
            random.shuffle(self.ground_spawns_roadbase[cp])

            # Generate STOL pads
            ground_spawn_gen = GroundSpawnGenerator(
                self.m, cp, self.game, self.radio_registry, self.tacan_registry
            )
            ground_spawn_gen.generate()
            self.ground_spawns[cp] = ground_spawn_gen.ground_spawns
            random.shuffle(self.ground_spawns[cp])

            for ground_object in cp.ground_objects:
                generator: GroundObjectGenerator
                if isinstance(ground_object, CarrierGroundObject) and isinstance(
                    cp, NavalControlPoint
                ):
                    generator = PretenseCarrierGenerator(
                        ground_object,
                        cp,
                        country,
                        self.game,
                        self.m,
                        self.radio_registry,
                        self.tacan_registry,
                        self.icls_alloc,
                        self.runways,
                        self.unit_map,
                        self.mission_data,
                    )
                elif isinstance(ground_object, LhaGroundObject) and isinstance(
                    cp, NavalControlPoint
                ):
                    generator = PretenseLhaGenerator(
                        ground_object,
                        cp,
                        country,
                        self.game,
                        self.m,
                        self.radio_registry,
                        self.tacan_registry,
                        self.icls_alloc,
                        self.runways,
                        self.unit_map,
                        self.mission_data,
                    )
                elif isinstance(ground_object, MissileSiteGroundObject):
                    generator = MissileSiteGenerator(
                        ground_object, country, self.game, self.m, self.unit_map
                    )
                else:
                    generator = PretenseGroundObjectGenerator(
                        ground_object, country, self.game, self.m, self.unit_map
                    )
                generator.generate()
            # Then generate ground supply and assault groups for the other coalition
            other_coalition = cp.coalition
            for coalition in cp.coalition.game.coalitions:
                if coalition == cp.coalition:
                    continue
                else:
                    other_coalition = coalition
            country = self.m.country(other_coalition.faction.country.name)
            new_ground_object: TheaterGroundObject
            for ground_object in cp.ground_objects:
                if isinstance(ground_object, BuildingGroundObject):
                    new_ground_object = BuildingGroundObject(
                        name=ground_object.name,
                        category=ground_object.category,
                        location=PresetLocation(
                            f"{ground_object.name} {ground_object.id}",
                            ground_object.position,
                            ground_object.heading,
                        ),
                        control_point=ground_object.control_point,
                        is_fob_structure=ground_object.is_fob_structure,
                        task=ground_object.task,
                    )
                    new_ground_object.groups = ground_object.groups
                    generator = PretenseGroundObjectGenerator(
                        new_ground_object, country, self.game, self.m, self.unit_map
                    )
                elif isinstance(ground_object, VehicleGroupGroundObject):
                    new_ground_object = VehicleGroupGroundObject(
                        name=ground_object.name,
                        location=PresetLocation(
                            f"{ground_object.name} {ground_object.id}",
                            ground_object.position,
                            ground_object.heading,
                        ),
                        control_point=ground_object.control_point,
                        task=ground_object.task,
                    )
                    new_ground_object.groups = ground_object.groups
                    generator = PretenseGroundObjectGenerator(
                        new_ground_object, country, self.game, self.m, self.unit_map
                    )
                else:
                    continue

                generator.coalition = other_coalition
                generator.generate()

        self.mission_data.runways = list(self.runways.values())
