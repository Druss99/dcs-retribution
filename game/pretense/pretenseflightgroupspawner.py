import logging
import random
from typing import Any, Tuple

from dcs import Mission
from dcs.country import Country
from dcs.mapping import Vector2, Point
from dcs.terrain import NoParkingSlotError, TheChannel, Falklands
from dcs.terrain.falklands.airports import San_Carlos_FOB, Goose_Green, Gull_Point
from dcs.terrain.thechannel.airports import Manston
from dcs.unitgroup import (
    FlyingGroup,
    ShipGroup,
    StaticGroup,
)

from game.ato import Flight
from game.ato.flightstate import InFlight
from game.ato.starttype import StartType
from game.missiongenerator.aircraft.flightgroupspawner import (
    FlightGroupSpawner,
    MINIMUM_MID_MISSION_SPAWN_ALTITUDE_AGL,
    MINIMUM_MID_MISSION_SPAWN_ALTITUDE_MSL,
    STACK_SEPARATION,
)
from game.missiongenerator.missiondata import MissionData
from game.naming import NameGenerator
from game.theater import Airfield, ControlPoint, Fob, NavalControlPoint, Player


class PretenseNameGenerator(NameGenerator):
    @classmethod
    def next_pretense_aircraft_name(cls, cp: ControlPoint, flight: Flight) -> str:
        cls.aircraft_number += 1
        cp_name_trimmed = cls.pretense_trimmed_cp_name(cp.name)
        return "{}-{}-{}".format(
            cp_name_trimmed, str(flight.flight_type).lower(), cls.aircraft_number
        )

    @classmethod
    def pretense_trimmed_cp_name(cls, cp_name: str) -> str:
        cp_name_alnum = "".join([i for i in cp_name.lower() if i.isalnum()])
        cp_name_trimmed = cp_name_alnum.lstrip("1 2 3 4 5 6 7 8 9 0")
        cp_name_trimmed = cp_name_trimmed.replace("ä", "a")
        cp_name_trimmed = cp_name_trimmed.replace("ö", "o")
        cp_name_trimmed = cp_name_trimmed.replace("ø", "o")
        return cp_name_trimmed


namegen = PretenseNameGenerator
# Air-start AI aircraft which are faster than this on WWII terrains
# 1000 km/h is just above the max speed of the Harrier and Su-25,
# so they will still start normally from grass and dirt strips
WW2_TERRAIN_SUPERSONIC_AI_AIRSTART_SPEED = 1000


class PretenseFlightGroupSpawner(FlightGroupSpawner):
    def __init__(
        self,
        flight: Flight,
        country: Country,
        mission: Mission,
        helipads: dict[ControlPoint, list[StaticGroup]],
        ground_spawns_roadbase: dict[ControlPoint, list[Tuple[StaticGroup, Point]]],
        ground_spawns_large: dict[ControlPoint, list[Tuple[StaticGroup, Point]]],
        ground_spawns: dict[ControlPoint, list[Tuple[StaticGroup, Point]]],
        mission_data: MissionData,
    ) -> None:
        super().__init__(
            flight,
            country,
            mission,
            helipads,
            ground_spawns_roadbase,
            ground_spawns_large,
            ground_spawns,
            mission_data,
        )

        self.flight = flight
        self.country = country
        self.mission = mission
        self.helipads = helipads
        self.ground_spawns_roadbase = ground_spawns_roadbase
        self.ground_spawns = ground_spawns
        self.mission_data = mission_data

    def insert_into_pretense(self, name: str) -> None:
        cp = self.flight.departure
        is_player = Player.BLUE
        cp_side = (
            2
            if self.flight.coalition
            == self.flight.coalition.game.coalition_for(is_player)
            else 1
        )
        cp_name_trimmed = PretenseNameGenerator.pretense_trimmed_cp_name(cp.name)

        if self.flight.client_count == 0:
            self.flight.coalition.game.pretense_air[cp_side][cp_name_trimmed][
                self.flight.flight_type
            ].append(name)
            try:
                self.flight.coalition.game.pretense_air_groups[name] = self.flight
            except AttributeError:
                self.flight.coalition.game.pretense_air_groups = {}
                self.flight.coalition.game.pretense_air_groups[name] = self.flight

    def generate_flight_at_departure(self) -> FlyingGroup[Any]:
        cp = self.flight.departure
        name = namegen.next_pretense_aircraft_name(cp, self.flight)

        try:
            if self.start_type is StartType.IN_FLIGHT:
                self.insert_into_pretense(name)
                group = self._generate_over_departure(name, cp)
                return group
            elif isinstance(cp, NavalControlPoint):
                group_name = cp.get_carrier_group_name()
                carrier_group = self.mission.find_group(group_name)
                if not isinstance(carrier_group, ShipGroup):
                    raise RuntimeError(
                        f"Carrier group {carrier_group} is a "
                        f"{carrier_group.__class__.__name__}, expected a ShipGroup"
                    )
                self.insert_into_pretense(name)
                return self._generate_at_group(name, carrier_group)
            elif isinstance(cp, Fob):
                is_heli = self.flight.squadron.aircraft.helicopter
                is_vtol = not is_heli and self.flight.squadron.aircraft.lha_capable
                if not is_heli and not is_vtol and not cp.has_ground_spawns:
                    raise RuntimeError(
                        f"Cannot spawn fixed-wing aircraft at {cp} because of insufficient ground spawn slots."
                    )
                pilot_count = len(self.flight.roster.members)
                if (
                    not is_heli
                    and self.flight.roster.player_count != pilot_count
                    and not self.flight.coalition.game.settings.ground_start_ai_planes
                ):
                    raise RuntimeError(
                        f"Fixed-wing aircraft at {cp} must be piloted by humans exclusively because"
                        f' the "AI fixed-wing aircraft can use roadbases / bases with only ground'
                        f' spawns" setting is currently disabled.'
                    )
                if cp.has_helipads and (is_heli or is_vtol):
                    self.insert_into_pretense(name)
                    pad_group = self._generate_at_cp_helipad(name, cp)
                    if pad_group is not None:
                        return pad_group
                if cp.has_ground_spawns and (self.flight.client_count > 0 or is_heli):
                    self.insert_into_pretense(name)
                    pad_group = self._generate_at_cp_ground_spawn(name, cp)
                    if pad_group is not None:
                        return pad_group
                raise NoParkingSlotError
            elif isinstance(cp, Airfield):
                is_heli = self.flight.squadron.aircraft.helicopter
                is_vtol = not is_heli and self.flight.squadron.aircraft.lha_capable
                if cp.has_helipads and is_heli:
                    self.insert_into_pretense(name)
                    pad_group = self._generate_at_cp_helipad(name, cp)
                    if pad_group is not None:
                        return pad_group
                # Air-start supersonic AI aircraft if the campaign is being flown in a WWII terrain
                # This will improve these terrains' use in cold war campaigns
                if isinstance(cp.theater.terrain, TheChannel) and not isinstance(
                    cp.dcs_airport, Manston
                ):
                    if (
                        self.flight.client_count == 0
                        and self.flight.squadron.aircraft.max_speed.speed_in_kph
                        > WW2_TERRAIN_SUPERSONIC_AI_AIRSTART_SPEED
                    ):
                        self.insert_into_pretense(name)
                        return self._generate_over_departure(name, cp)
                # Air-start AI fixed wing (non-VTOL) aircraft if the campaign is being flown in the South Atlantic terrain and
                # the airfield is one of the Harrier-only ones in East Falklands.
                # This will help avoid AI aircraft from smashing into the end of the runway and exploding.
                if isinstance(cp.theater.terrain, Falklands) and (
                    isinstance(cp.dcs_airport, San_Carlos_FOB)
                    or isinstance(cp.dcs_airport, Goose_Green)
                    or isinstance(cp.dcs_airport, Gull_Point)
                ):
                    if self.flight.client_count == 0 and is_vtol:
                        self.insert_into_pretense(name)
                        return self._generate_over_departure(name, cp)
                if (
                    cp.has_ground_spawns
                    and len(self.ground_spawns[cp])
                    + len(self.ground_spawns_roadbase[cp])
                    >= self.flight.count
                    and (self.flight.client_count > 0 or is_heli)
                ):
                    self.insert_into_pretense(name)
                    pad_group = self._generate_at_cp_ground_spawn(name, cp)
                    if pad_group is not None:
                        return pad_group
                self.insert_into_pretense(name)
                return self._generate_at_airfield(name, cp)
            else:
                raise NotImplementedError(
                    f"Aircraft spawn behavior not implemented for {cp} ({cp.__class__})"
                )
        except NoParkingSlotError:
            # Generated when there is no place on Runway or on Parking Slots
            if self.flight.client_count > 0:
                # Don't generate player airstarts
                logging.warning(
                    "No room on runway or parking slots. Not generating a player air-start."
                )
                raise NoParkingSlotError
            else:
                logging.warning(
                    "No room on runway or parking slots. Starting from the air."
                )
                self.flight.start_type = StartType.IN_FLIGHT
                self.insert_into_pretense(name)
                group = self._generate_over_departure(name, cp)
                return group

    def generate_mid_mission(self) -> FlyingGroup[Any]:
        assert isinstance(self.flight.state, InFlight)
        name = namegen.next_pretense_aircraft_name(self.flight.departure, self.flight)

        speed = self.flight.state.estimate_speed()
        pos = self.flight.state.estimate_position()
        pos += Vector2(random.randint(100, 1000), random.randint(100, 1000))
        alt, alt_type = self.flight.state.estimate_altitude()
        cp = self.flight.squadron.location.id

        if cp not in self.mission_data.cp_stack:
            self.mission_data.cp_stack[cp] = MINIMUM_MID_MISSION_SPAWN_ALTITUDE_AGL

        # We don't know where the ground is, so just make sure that any aircraft
        # spawning at an MSL altitude is spawned at some minimum altitude.
        # https://github.com/dcs-liberation/dcs_liberation/issues/1941
        if alt_type == "BARO" and alt < MINIMUM_MID_MISSION_SPAWN_ALTITUDE_MSL:
            alt = MINIMUM_MID_MISSION_SPAWN_ALTITUDE_MSL

        # Set a minimum AGL value for 'alt' if needed,
        # otherwise planes might crash in trees and stuff.
        if alt_type == "RADIO" and alt < self.mission_data.cp_stack[cp]:
            alt = self.mission_data.cp_stack[cp]
            self.mission_data.cp_stack[cp] += STACK_SEPARATION

        self.insert_into_pretense(name)
        group = self.mission.flight_group(
            country=self.country,
            name=name,
            aircraft_type=self.flight.unit_type.dcs_unit_type,
            airport=None,
            position=pos,
            altitude=alt.meters,
            speed=speed.kph,
            maintask=None,
            group_size=self.flight.count,
        )

        group.points[0].alt_type = alt_type
        return group
