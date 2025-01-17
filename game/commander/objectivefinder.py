from __future__ import annotations

import math
import operator
from collections.abc import Iterable, Iterator
from random import randint
from typing import TYPE_CHECKING, TypeVar

from game.ato.closestairfields import ClosestAirfields, ObjectiveDistanceCache
from game.theater import (
    Airfield,
    ControlPoint,
    Fob,
    FrontLine,
    MissionTarget,
    OffMapSpawn,
    ParkingType,
    NavalControlPoint,
)
from game.theater.theatergroundobject import (
    BuildingGroundObject,
    IadsGroundObject,
    NavalGroundObject,
    IadsBuildingGroundObject,
)
from game.utils import meters, nautical_miles

if TYPE_CHECKING:
    from game import Game
    from game.transfers import CargoShip, Convoy

MissionTargetType = TypeVar("MissionTargetType", bound=MissionTarget)


class ObjectiveFinder:
    """Identifies potential objectives for the mission planner."""

    def __init__(self, game: Game, is_player: bool) -> None:
        self.game = game
        self.is_player = is_player

    def enemy_air_defenses(self) -> Iterator[IadsGroundObject]:
        """Iterates over all enemy SAM sites."""
        for cp in self.enemy_control_points():
            for ground_object in cp.ground_objects:
                if ground_object.is_dead:
                    continue

                if isinstance(ground_object, IadsGroundObject):
                    yield ground_object

    def enemy_ships(self) -> Iterator[NavalGroundObject]:
        for cp in self.enemy_control_points():
            for ground_object in cp.ground_objects:
                if not isinstance(ground_object, NavalGroundObject):
                    continue

                if ground_object.is_dead:
                    continue

                yield ground_object

    def threatening_ships(self) -> Iterator[NavalGroundObject]:
        """Iterates over enemy ships near friendly control points.

        Groups are sorted by their closest proximity to any friendly control
        point (airfield or fleet).
        """
        return self._targets_by_range(self.enemy_ships())

    def _targets_by_range(
        self, targets: Iterable[MissionTargetType]
    ) -> Iterator[MissionTargetType]:
        target_ranges: list[tuple[MissionTargetType, float]] = []
        for target in targets:
            ranges: list[float] = []
            for cp in self.friendly_control_points():
                ranges.append(target.distance_to(cp))
            target_ranges.append((target, min(ranges)))

        target_ranges = sorted(target_ranges, key=operator.itemgetter(1))
        for target, _range in target_ranges:
            yield target

    def strike_targets(self) -> Iterator[BuildingGroundObject]:
        """Iterates over enemy strike targets.

        Targets are sorted by their closest proximity to any friendly control
        point (airfield or fleet).
        """
        targets: list[tuple[BuildingGroundObject, float]] = []
        # Building objectives are made of several individual TGOs (one per
        # building).
        found_targets: set[str] = set()
        for enemy_cp in self.enemy_control_points():
            for ground_object in enemy_cp.ground_objects:
                # TODO: Reuse ground_object.mission_types.
                # The mission types for ground objects are currently not
                # accurate because we include things like strike and BAI for all
                # targets since they have different planning behavior (waypoint
                # generation is better for players with strike when the targets
                # are stationary, AI behavior against weaker air defenses is
                # better with BAI), so that's not a useful filter. Once we have
                # better control over planning profiles and target dependent
                # loadouts we can clean this up.
                if not isinstance(ground_object, BuildingGroundObject):
                    # Other group types (like ships, SAMs, battle positions, etc) have better
                    # suited mission types like anti-ship, DEAD, and BAI.
                    continue

                if isinstance(enemy_cp, Fob) and ground_object.is_control_point:
                    # This is the FOB structure itself. Can't be repaired or
                    # targeted by the player, so shouldn't be targetable by the
                    # AI.
                    continue

                if isinstance(
                    ground_object, IadsBuildingGroundObject
                ) and not self.game.settings.plugin_option("skynetiads"):
                    # Prevent strike targets on IADS Buildings when skynet features
                    # are disabled as they do not serve any purpose
                    continue

                if ground_object.is_dead:
                    continue
                if ground_object.name in found_targets:
                    continue
                ranges: list[float] = []
                for friendly_cp in self.friendly_control_points():
                    ranges.append(ground_object.distance_to(friendly_cp))
                targets.append((ground_object, min(ranges)))
                found_targets.add(ground_object.name)
        targets = sorted(targets, key=operator.itemgetter(1))
        for target, _range in targets:
            yield target

    def front_lines(self) -> Iterator[FrontLine]:
        """Iterates over all active front lines in the theater."""
        yield from self.game.theater.conflicts()

    def vulnerable_control_points(self) -> Iterator[ControlPoint]:
        """Iterates over friendly CPs that are vulnerable to enemy CPs.

        Vulnerability is defined as any enemy CP within threat range of the
        CP.
        """
        for cp in self.friendly_control_points():
            if isinstance(cp, OffMapSpawn):
                # Off-map spawn locations don't need protection.
                continue
            if isinstance(cp, NavalControlPoint):
                yield cp  # always consider CVN/LHA as vulnerable
                continue
            airfields_in_proximity = self.closest_airfields_to(cp)
            airbase_threat_range = self.game.settings.airbase_threat_range
            if (
                not self.is_player
                and randint(1, 100)
                > self.game.settings.opfor_autoplanner_aggressiveness
            ):
                # Chance that the airfield threat range will be evaluated as zero,
                # causing the OPFOR autoplanner to plan offensively
                airbase_threat_range = 0
            airfields_in_threat_range = (
                airfields_in_proximity.operational_airfields_within(
                    nautical_miles(airbase_threat_range)
                )
            )
            for airfield in airfields_in_threat_range:
                if not airfield.is_friendly(self.is_player):
                    yield cp
                    break

    def oca_targets(self, min_aircraft: int) -> Iterator[ControlPoint]:
        parking_type = ParkingType()
        parking_type.include_rotary_wing = True
        parking_type.include_fixed_wing = True
        parking_type.include_fixed_wing_stol = True

        airfields = []
        for control_point in self.enemy_control_points():
            if not isinstance(control_point, Airfield) and not isinstance(
                control_point, Fob
            ):
                continue
            if (
                control_point.allocated_aircraft(parking_type).total_present
                >= min_aircraft
            ):
                airfields.append(control_point)
        return self._targets_by_range(airfields)

    def convoys(self) -> Iterator[Convoy]:
        if self.game.settings.perf_disable_convoys:
            return
        for front_line in self.front_lines():
            yield from self.game.coalition_for(
                self.is_player
            ).transfers.convoys.travelling_to(
                front_line.control_point_hostile_to(self.is_player)
            )

    def cargo_ships(self) -> Iterator[CargoShip]:
        for front_line in self.front_lines():
            yield from self.game.coalition_for(
                self.is_player
            ).transfers.cargo_ships.travelling_to(
                front_line.control_point_hostile_to(self.is_player)
            )

    def friendly_control_points(self) -> Iterator[ControlPoint]:
        """Iterates over all friendly control points."""
        return (
            c for c in self.game.theater.controlpoints if c.is_friendly(self.is_player)
        )

    def farthest_friendly_control_point(self) -> ControlPoint:
        """Finds the friendly control point that is farthest from any threats."""
        threat_zones = self.game.threat_zone_for(not self.is_player)

        farthest = None
        max_distance = meters(0)
        for cp in self.friendly_control_points():
            if isinstance(cp, OffMapSpawn):
                continue
            distance = threat_zones.distance_to_threat(cp.position)
            if distance > max_distance:
                farthest = cp
                max_distance = distance

        if farthest is None:
            raise RuntimeError("Found no friendly control points. You probably lost.")
        return farthest

    def closest_friendly_control_point(self) -> ControlPoint:
        """Finds the friendly control point that is closest to any threats."""
        threat_zones = self.game.threat_zone_for(not self.is_player)

        closest = None
        min_distance = meters(math.inf)
        for cp in self.friendly_control_points():
            if isinstance(cp, OffMapSpawn):
                continue
            distance = threat_zones.distance_to_threat(cp.position)
            if distance < min_distance:
                closest = cp
                min_distance = distance

        if closest is None:
            raise RuntimeError("Found no friendly control points. You probably lost.")
        return closest

    def friendly_naval_control_points(self) -> Iterator[ControlPoint]:
        return (cp for cp in self.friendly_control_points() if cp.is_fleet)

    def enemy_control_points(self) -> Iterator[ControlPoint]:
        """Iterates over all enemy control points."""
        return (
            c
            for c in self.game.theater.controlpoints
            if not c.is_friendly(self.is_player) and c.captured is not None
        )

    def prioritized_points(self) -> list[ControlPoint]:
        prioritized = []
        capturable_later = []
        isolated = []
        for cp in self.game.theater.control_points_for(not self.is_player):
            if cp.is_isolated:
                isolated.append(cp)
                continue
            if cp.has_active_frontline:
                prioritized.append(cp)
            else:
                capturable_later.append(cp)
        prioritized.extend(self._targets_by_range(capturable_later))
        prioritized.extend(self._targets_by_range(isolated))
        return prioritized

    @staticmethod
    def closest_airfields_to(location: MissionTarget) -> ClosestAirfields:
        """Returns the closest airfields to the given location."""
        return ObjectiveDistanceCache.get_closest_airfields(location)
