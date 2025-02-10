from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, List

from dcs import Point
from dcs.action import (
    ClearFlag,
    DoScript,
    MarkToAll,
    SetFlag,
    RemoveSceneObjects,
    RemoveSceneObjectsMask,
    SceneryDestructionZone,
    Smoke,
)
from dcs.condition import (
    AllOfCoalitionOutsideZone,
    FlagIsFalse,
    FlagIsTrue,
    PartOfCoalitionInZone,
    TimeAfter,
    TimeSinceFlag,
)
from dcs.mission import Mission
from dcs.task import Option
from dcs.terrain.caucasus.airports import Krasnodar_Pashkovsky
from dcs.terrain.syria.airports import Damascus, Khalkhalah
from dcs.translation import String
from dcs.triggers import Event, TriggerCondition, TriggerOnce
from dcs.unit import Skill
from numpy import cross, einsum, arctan2
from shapely import MultiPolygon, Point as ShapelyPoint

from game.naming import ALPHA_MILITARY
from game.pretense.pretenseflightgroupspawner import PretenseNameGenerator
from game.theater import Airfield, Player
from game.theater.controlpoint import Fob, TRIGGER_RADIUS_CAPTURE, OffMapSpawn

if TYPE_CHECKING:
    from game.game import Game

PUSH_TRIGGER_SIZE = 3000
PUSH_TRIGGER_ACTIVATION_AGL = 25

REGROUP_ZONE_DISTANCE = 12000
REGROUP_ALT = 5000

TRIGGER_WAYPOINT_OFFSET = 2
TRIGGER_MIN_DISTANCE_FROM_START = 10000
# modified since we now have advanced SAM units
TRIGGER_RADIUS_MINIMUM = 3000000

TRIGGER_RADIUS_SMALL = 50000
TRIGGER_RADIUS_MEDIUM = 100000
TRIGGER_RADIUS_LARGE = 150000
TRIGGER_RADIUS_ALL_MAP = 3000000
TRIGGER_RADIUS_CLEAR_SCENERY = 1000
TRIGGER_RADIUS_PRETENSE_TGO = 500
TRIGGER_RADIUS_PRETENSE_SUPPLY = 500
TRIGGER_RADIUS_PRETENSE_HELI = 1000
TRIGGER_RADIUS_PRETENSE_HELI_BUFFER = 500
TRIGGER_RADIUS_PRETENSE_CARRIER = 20000
TRIGGER_RADIUS_PRETENSE_CARRIER_SMALL = 3000
TRIGGER_RADIUS_PRETENSE_CARRIER_CORNER = 25000
TRIGGER_RUNWAY_LENGTH_PRETENSE = 2500
TRIGGER_RUNWAY_WIDTH_PRETENSE = 400

SIMPLIFY_RUNS_PRETENSE_CARRIER = 10000


class Silence(Option):
    Key = 7


class PretenseTriggerGenerator:
    capture_zone_types = (Fob, Airfield)
    capture_zone_flag = 600

    def __init__(self, mission: Mission, game: Game) -> None:
        self.mission = mission
        self.game = game

    def _set_allegiances(self, player_coalition: str, enemy_coalition: str) -> None:
        """
        Set airbase initial coalition
        """

        # Empty neutrals airports
        airfields = [
            cp for cp in self.game.theater.controlpoints if isinstance(cp, Airfield)
        ]
        airport_ids = {cp.airport.id for cp in airfields}
        for airport in self.mission.terrain.airport_list():
            if airport.id not in airport_ids:
                airport.unlimited_fuel = False
                airport.unlimited_munitions = False
                airport.unlimited_aircrafts = False
                airport.gasoline_init = 0
                airport.methanol_mixture_init = 0
                airport.diesel_init = 0
                airport.jet_init = 0
                airport.operating_level_air = 0
                airport.operating_level_equipment = 0
                airport.operating_level_fuel = 0

        for airport in self.mission.terrain.airport_list():
            if airport.id not in airport_ids:
                airport.unlimited_fuel = True
                airport.unlimited_munitions = True
                airport.unlimited_aircrafts = True

        for airfield in airfields:
            cp_airport = self.mission.terrain.airport_by_id(airfield.airport.id)
            if cp_airport is None:
                raise RuntimeError(
                    f"Could not find {airfield.airport.name} in the mission"
                )
            cp_airport.set_coalition(
                airfield.captured and player_coalition or enemy_coalition
            )

    def _set_skill(self, player_coalition: str, enemy_coalition: str) -> None:
        """
        Set skill level for all aircraft in the mission
        """
        for coalition_name, coalition in self.mission.coalition.items():
            if coalition_name == player_coalition:
                skill_level = Skill(self.game.settings.player_skill)
            elif coalition_name == enemy_coalition:
                skill_level = Skill(self.game.settings.enemy_vehicle_skill)
            else:
                continue

            for country in coalition.countries.values():
                for vehicle_group in country.vehicle_group:
                    vehicle_group.set_skill(skill_level)

    def _gen_markers(self) -> None:
        """
        Generate markers on F10 map for each existing objective
        """
        if self.game.settings.generate_marks:
            mark_trigger = TriggerOnce(Event.NoEvent, "Marks generator")
            mark_trigger.add_condition(TimeAfter(1))
            v = 10
            for cp in self.game.theater.controlpoints:
                seen = set()
                for ground_object in cp.ground_objects:
                    if ground_object.obj_name in seen:
                        continue

                    seen.add(ground_object.obj_name)
                    for location in ground_object.mark_locations:
                        zone = self.mission.triggers.add_triggerzone(
                            location, radius=10, hidden=True, name="MARK"
                        )
                        if cp.captured is Player.BLUE:
                            name = ground_object.obj_name + " [ALLY]"
                        else:
                            name = ground_object.obj_name + " [ENEMY]"
                        mark_trigger.add_action(MarkToAll(v, zone.id, String(name)))
                        v += 1
            self.mission.triggerrules.triggers.append(mark_trigger)

    def _generate_capture_triggers(
        self, player_coalition: str, enemy_coalition: str
    ) -> None:
        """Creates a pair of triggers for each control point of `cls.capture_zone_types`.
        One for the initial capture of a control point, and one if it is recaptured.
        Directly appends to the global `base_capture_events` var declared by `dcs_libaration.lua`
        """
        for cp in self.game.theater.controlpoints:
            if isinstance(cp, self.capture_zone_types) and not cp.is_carrier:
                if cp.captured is Player.BLUE:
                    attacking_coalition = enemy_coalition
                    attack_coalition_int = 1  # 1 is the Event int for Red
                    defending_coalition = player_coalition
                    defend_coalition_int = 2  # 2 is the Event int for Blue
                else:
                    attacking_coalition = player_coalition
                    attack_coalition_int = 2
                    defending_coalition = enemy_coalition
                    defend_coalition_int = 1

                trigger_zone = self.mission.triggers.add_triggerzone(
                    cp.position,
                    radius=TRIGGER_RADIUS_CAPTURE,
                    hidden=False,
                    name="CAPTURE",
                )
                flag = self.get_capture_zone_flag()
                capture_trigger = TriggerCondition(Event.NoEvent, "Capture Trigger")
                capture_trigger.add_condition(
                    AllOfCoalitionOutsideZone(
                        defending_coalition, trigger_zone.id, unit_type="GROUND"
                    )
                )
                capture_trigger.add_condition(
                    PartOfCoalitionInZone(
                        attacking_coalition, trigger_zone.id, unit_type="GROUND"
                    )
                )
                capture_trigger.add_condition(FlagIsFalse(flag=flag))
                script_string = String(
                    f'base_capture_events[#base_capture_events + 1] = "{cp.id}||{attack_coalition_int}||{cp.full_name}"'
                )
                capture_trigger.add_action(DoScript(script_string))
                capture_trigger.add_action(SetFlag(flag=flag))
                self.mission.triggerrules.triggers.append(capture_trigger)

                recapture_trigger = TriggerCondition(Event.NoEvent, "Capture Trigger")
                recapture_trigger.add_condition(
                    AllOfCoalitionOutsideZone(
                        attacking_coalition, trigger_zone.id, unit_type="GROUND"
                    )
                )
                recapture_trigger.add_condition(
                    PartOfCoalitionInZone(
                        defending_coalition, trigger_zone.id, unit_type="GROUND"
                    )
                )
                recapture_trigger.add_condition(FlagIsTrue(flag=flag))
                script_string = String(
                    f'base_capture_events[#base_capture_events + 1] = "{cp.id}||{defend_coalition_int}||{cp.full_name}"'
                )
                recapture_trigger.add_action(DoScript(script_string))
                recapture_trigger.add_action(ClearFlag(flag=flag))
                self.mission.triggerrules.triggers.append(recapture_trigger)

    def _generate_pretense_zone_triggers(self) -> None:
        """Creates triggger zones for the Pretense campaign. These include:
        - Carrier zones for friendly forces, generated from the navmesh / sea zone intersection
        - Carrier zones for opposing forces
        - Airfield and FARP zones
        - Airfield and FARP spawn points / helicopter spawn points / ground object positions
        """

        # First generate carrier zones for friendly forces
        use_blue_navmesh = (
            self.game.settings.pretense_carrier_zones_navmesh == "Blue navmesh"
        )
        sea_zones_landmap = self.game.coalition_for(
            player=Player.RED
        ).nav_mesh.theater.landmap
        if (
            self.game.settings.pretense_controllable_carrier
            and sea_zones_landmap is not None
        ):
            navmesh_number = 0
            for navmesh_poly in self.game.coalition_for(
                player=Player.BLUE if use_blue_navmesh else Player.RED
            ).nav_mesh.polys:
                navmesh_number += 1
                if sea_zones_landmap.sea_zones.intersects(navmesh_poly.poly):
                    # Get the intersection between the navmesh zone and the sea zone
                    navmesh_sea_intersection = sea_zones_landmap.sea_zones.intersection(
                        navmesh_poly.poly
                    )
                    navmesh_zone_verticies = navmesh_sea_intersection

                    # Simplify it to get a quadrangle
                    for simplify_run in range(SIMPLIFY_RUNS_PRETENSE_CARRIER):
                        navmesh_zone_verticies = navmesh_sea_intersection.simplify(
                            float(simplify_run * 10), preserve_topology=False
                        )
                        if isinstance(navmesh_zone_verticies, MultiPolygon):
                            break
                        if len(navmesh_zone_verticies.exterior.coords) <= 4:
                            break
                    if isinstance(navmesh_zone_verticies, MultiPolygon):
                        continue
                    trigger_zone_verticies = []
                    terrain = self.game.theater.terrain
                    alpha = random.choice(ALPHA_MILITARY)

                    # Generate the quadrangle zone and four points inside it for carrier navigation
                    if len(navmesh_zone_verticies.exterior.coords) == 4:
                        zone_color = {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.15}
                        corner_point_num = 0
                        for point_coord in navmesh_zone_verticies.exterior.coords:
                            corner_point = Point(
                                x=point_coord[0], y=point_coord[1], terrain=terrain
                            )
                            nav_point = corner_point.point_from_heading(
                                corner_point.heading_between_point(
                                    navmesh_sea_intersection.centroid
                                ),
                                TRIGGER_RADIUS_PRETENSE_CARRIER_CORNER,
                            )
                            corner_point_num += 1

                            zone_name = f"{alpha}-{navmesh_number}-{corner_point_num}"
                            if sea_zones_landmap.sea_zones.contains(
                                ShapelyPoint(nav_point.x, nav_point.y)
                            ):
                                self.mission.triggers.add_triggerzone(
                                    nav_point,
                                    radius=TRIGGER_RADIUS_PRETENSE_CARRIER_SMALL,
                                    hidden=False,
                                    name=zone_name,
                                    color=zone_color,
                                )

                            trigger_zone_verticies.append(corner_point)

                        zone_name = f"{alpha}-{navmesh_number}"
                        trigger_zone = self.mission.triggers.add_triggerzone_quad(
                            navmesh_sea_intersection.centroid,
                            trigger_zone_verticies,
                            hidden=False,
                            name=zone_name,
                            color=zone_color,
                        )
                        try:
                            if len(self.game.pretense_carrier_zones) == 0:
                                self.game.pretense_carrier_zones = []
                        except AttributeError:
                            self.game.pretense_carrier_zones = []
                        self.game.pretense_carrier_zones.append(zone_name)

        for cp in self.game.theater.controlpoints:
            if (
                cp.is_fleet
                and self.game.settings.pretense_controllable_carrier
                and cp.captured is Player.BLUE
            ):
                # Friendly carrier zones are generated above
                continue
            elif cp.is_fleet:
                trigger_radius = float(TRIGGER_RADIUS_PRETENSE_CARRIER)
            elif isinstance(cp, Fob) and cp.has_helipads:
                trigger_radius = TRIGGER_RADIUS_PRETENSE_HELI
                for helipad in list(
                    cp.helipads + cp.helipads_quad + cp.helipads_invisible
                ):
                    if cp.position.distance_to_point(helipad) > trigger_radius:
                        trigger_radius = cp.position.distance_to_point(helipad)
                for ground_spawn, ground_spawn_wp in list(
                    cp.ground_spawns + cp.ground_spawns_roadbase
                ):
                    if cp.position.distance_to_point(ground_spawn) > trigger_radius:
                        trigger_radius = cp.position.distance_to_point(ground_spawn)
                trigger_radius += TRIGGER_RADIUS_PRETENSE_HELI_BUFFER
            else:
                if cp.dcs_airport is not None and (
                    isinstance(cp.dcs_airport, Damascus)
                    or isinstance(cp.dcs_airport, Khalkhalah)
                    or isinstance(cp.dcs_airport, Krasnodar_Pashkovsky)
                ):
                    # Increase the size of Pretense zones at Damascus, Khalkhalah and Krasnodar-Pashkovsky
                    # (which are quite spread out) so the zone would encompass the entire airfield.
                    trigger_radius = int(TRIGGER_RADIUS_CAPTURE * 1.8)
                else:
                    trigger_radius = TRIGGER_RADIUS_CAPTURE
            cp_name = "".join(
                [i for i in cp.name if i.isalnum() or i.isspace() or i == "-"]
            )
            cp_name = cp_name.replace("Ä", "A")
            cp_name = cp_name.replace("Ö", "O")
            cp_name = cp_name.replace("Ø", "O")
            cp_name = cp_name.replace("ä", "a")
            cp_name = cp_name.replace("ö", "o")
            cp_name = cp_name.replace("ø", "o")
            if not isinstance(cp, OffMapSpawn):
                zone_color = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.15}
                self.mission.triggers.add_triggerzone(
                    cp.position,
                    radius=trigger_radius,
                    hidden=False,
                    name=cp_name,
                    color=zone_color,
                )
            cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(cp.name)
            tgo_num = 0
            for tgo in cp.ground_objects:
                if cp.is_fleet or tgo.sea_object:
                    continue
                tgo_num += 1
                zone_color = {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.15}
                self.mission.triggers.add_triggerzone(
                    tgo.position,
                    radius=TRIGGER_RADIUS_PRETENSE_TGO,
                    hidden=False,
                    name=f"{cp_name_trimmed}-{tgo_num}",
                    color=zone_color,
                )
            for helipad in cp.helipads + cp.helipads_invisible + cp.helipads_quad:
                zone_color = {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.15}
                self.mission.triggers.add_triggerzone(
                    position=helipad,
                    radius=TRIGGER_RADIUS_PRETENSE_HELI,
                    hidden=False,
                    name=f"{cp_name_trimmed}-hsp",
                    color=zone_color,
                )
                break
            for supply_route in cp.convoy_routes.values():
                tgo_num += 1
                zone_color = {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.15}
                origin_position = supply_route[0]
                next_position = supply_route[1]
                convoy_heading = origin_position.heading_between_point(next_position)
                supply_position = origin_position.point_from_heading(
                    convoy_heading, 300
                )
                self.mission.triggers.add_triggerzone(
                    supply_position,
                    radius=TRIGGER_RADIUS_PRETENSE_TGO,
                    hidden=False,
                    name=f"{cp_name_trimmed}-sp",
                    color=zone_color,
                )
                break
        airfields = [
            cp for cp in self.game.theater.controlpoints if isinstance(cp, Airfield)
        ]
        for airfield in airfields:
            cp_airport = self.mission.terrain.airport_by_id(airfield.airport.id)
            if cp_airport is None:
                continue
            cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(
                cp_airport.name
            )
            zone_color = {1: 0.0, 2: 1.0, 3: 0.5, 4: 0.15}
            if cp_airport is None:
                raise RuntimeError(
                    f"Could not find {airfield.airport.name} in the mission"
                )
            for runway in cp_airport.runways:
                runway_end_1 = cp_airport.position.point_from_heading(
                    runway.heading, TRIGGER_RUNWAY_LENGTH_PRETENSE / 2
                )
                runway_end_2 = cp_airport.position.point_from_heading(
                    runway.heading + 180, TRIGGER_RUNWAY_LENGTH_PRETENSE / 2
                )
                runway_verticies = [
                    runway_end_1.point_from_heading(
                        runway.heading - 90, TRIGGER_RUNWAY_WIDTH_PRETENSE / 2
                    ),
                    runway_end_1.point_from_heading(
                        runway.heading + 90, TRIGGER_RUNWAY_WIDTH_PRETENSE / 2
                    ),
                    runway_end_2.point_from_heading(
                        runway.heading + 90, TRIGGER_RUNWAY_WIDTH_PRETENSE / 2
                    ),
                    runway_end_2.point_from_heading(
                        runway.heading - 90, TRIGGER_RUNWAY_WIDTH_PRETENSE / 2
                    ),
                ]
                trigger_zone = self.mission.triggers.add_triggerzone_quad(
                    cp_airport.position,
                    runway_verticies,
                    hidden=False,
                    name=f"{cp_name_trimmed}-runway-{runway.id}",
                    color=zone_color,
                )
                break

    def generate(self) -> None:
        player_coalition = "blue"
        enemy_coalition = "red"

        self._set_skill(player_coalition, enemy_coalition)
        self._set_allegiances(player_coalition, enemy_coalition)
        self._generate_pretense_zone_triggers()
        self._generate_capture_triggers(player_coalition, enemy_coalition)

    @classmethod
    def get_capture_zone_flag(cls) -> int:
        flag = cls.capture_zone_flag
        cls.capture_zone_flag += 1
        return flag
