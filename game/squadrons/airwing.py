from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Iterator, Optional, Sequence, TYPE_CHECKING

from game.ato.closestairfields import ObjectiveDistanceCache
from game.dcs.aircrafttype import AircraftType
from .squadrondefloader import SquadronDefLoader
from ..campaignloader.squadrondefgenerator import SquadronDefGenerator
from ..factions.faction import Faction
from ..theater import ControlPoint, MissionTarget
from ..utils import Distance

if TYPE_CHECKING:
    from game.game import Game
    from ..ato.flighttype import FlightType
    from .squadron import Squadron


class AirWing:
    def __init__(self, player: bool, game: Game, faction: Faction) -> None:
        self.player = player
        self.squadrons: dict[AircraftType, list[Squadron]] = defaultdict(list)
        self.squadron_defs = SquadronDefLoader(game, faction).load()
        self.squadron_def_generator = SquadronDefGenerator(faction)
        self.settings = game.settings

    def unclaim_squadron_def(self, squadron: Squadron) -> None:
        if squadron.aircraft in self.squadron_defs:
            for squadron_def in self.squadron_defs[squadron.aircraft]:
                if squadron_def.claimed and squadron_def.name == squadron.name:
                    squadron_def.claimed = False

    def add_squadron(self, squadron: Squadron) -> None:
        self.squadrons[squadron.aircraft].append(squadron)

    def squadrons_for(self, aircraft: AircraftType) -> Sequence[Squadron]:
        return self.squadrons[aircraft]

    def can_auto_plan(self, task: FlightType) -> bool:
        try:
            next(self.auto_assignable_for_task(task))
            return True
        except StopIteration:
            return False

    def best_squadrons_for(
        self,
        location: MissionTarget,
        task: FlightType,
        size: int,
        heli: bool,
        this_turn: bool,
        preferred_type: Optional[AircraftType] = None,
        ignore_range: bool = False,
    ) -> list[Squadron]:
        airfield_cache = ObjectiveDistanceCache.get_closest_airfields(location)
        best_aircraft = AircraftType.priority_list_for_task(task)
        ordered: list[Squadron] = []
        for control_point in airfield_cache.operational_airfields:
            if control_point.captured != self.player:
                continue
            capable_at_base = []
            squadrons = [
                s
                for s in control_point.squadrons
                if not preferred_type
                or s.aircraft.variant_id == preferred_type.variant_id
            ]
            for squadron in squadrons:
                if squadron.can_auto_assign_mission(
                    location, task, size, heli, this_turn, ignore_range
                ):
                    capable_at_base.append(squadron)
                    if squadron.aircraft not in best_aircraft:
                        # If it is not already in the list it should be the last one
                        best_aircraft.append(squadron.aircraft)

            ordered.extend(
                sorted(
                    capable_at_base,
                    key=lambda s: best_aircraft.index(s.aircraft),
                )
            )

        return sorted(
            ordered,
            key=lambda s: (
                # This looks like the opposite of what we want because False sorts
                # before True. Distance is also added,
                # i.e. 75NM with primary task match is similar to non-primary with 0NM to target
                int(s.primary_task != task)
                + Distance.from_meters(s.location.distance_to(location)).nautical_miles
                / self.settings.primary_task_distance_factor
                + best_aircraft.index(s.aircraft) / len(best_aircraft),
            ),
        )

    def best_squadron_for(
        self,
        location: MissionTarget,
        task: FlightType,
        size: int,
        heli: bool,
        this_turn: bool,
        preferred_type: Optional[AircraftType] = None,
        ignore_range: bool = False,
    ) -> Optional[Squadron]:
        for squadron in self.best_squadrons_for(
            location, task, size, heli, this_turn, preferred_type, ignore_range
        ):
            return squadron
        return None

    def best_available_aircrafts_for(self, task: FlightType) -> list[AircraftType]:
        """Returns an ordered list of available aircrafts for the given task"""
        aircrafts = []
        best_aircraft_for_task = AircraftType.priority_list_for_task(task)
        for aircraft, squadrons in self.squadrons.items():
            for squadron in squadrons:
                if squadron.untasked_aircraft and squadron.capable_of(task):
                    aircrafts.append(aircraft)
                    if aircraft not in best_aircraft_for_task:
                        best_aircraft_for_task.append(aircraft)
                    break
        # Sort the list ordered by the best capability
        return sorted(
            aircrafts,
            key=lambda ac: best_aircraft_for_task.index(ac),
        )

    def auto_assignable_for_task(self, task: FlightType) -> Iterator[Squadron]:
        for squadron in self.iter_squadrons():
            if squadron.can_auto_assign(task):
                yield squadron

    def auto_assignable_for_task_at(
        self, task: FlightType, base: ControlPoint
    ) -> Iterator[Squadron]:
        for squadron in self.iter_squadrons():
            if squadron.can_auto_assign(task) and squadron.location == base:
                yield squadron

    def squadron_for(self, aircraft: AircraftType) -> Squadron:
        return self.squadrons_for(aircraft)[0]

    def iter_squadrons(self) -> Iterator[Squadron]:
        return itertools.chain.from_iterable(self.squadrons.values())

    def squadron_at_index(self, index: int) -> Squadron:
        return list(self.iter_squadrons())[index]

    def populate_for_turn_0(self, squadrons_start_full: bool) -> None:
        for squadron in self.iter_squadrons():
            squadron.populate_for_turn_0(squadrons_start_full)

    def end_turn(self) -> None:
        for squadron in self.iter_squadrons():
            squadron.end_turn()

    def reset(self) -> None:
        for squadron in self.iter_squadrons():
            squadron.return_all_pilots_and_aircraft()

    @property
    def size(self) -> int:
        return sum(len(s) for s in self.squadrons.values())
