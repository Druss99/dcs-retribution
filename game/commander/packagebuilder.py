from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from game.theater import ControlPoint, MissionTarget, OffMapSpawn
from game.utils import nautical_miles
from ..ato import FlightType
from ..ato.flight import Flight
from ..ato.package import Package
from ..ato.starttype import StartType
from ..db.database import Database

if TYPE_CHECKING:
    from game.ato.closestairfields import ClosestAirfields
    from game.dcs.aircrafttype import AircraftType
    from game.lasercodes import LaserCodeRegistry
    from game.squadrons.airwing import AirWing
    from .missionproposals import ProposedFlight


class PackageBuilder:
    """Builds a Package for the flights it receives."""

    def __init__(
        self,
        location: MissionTarget,
        closest_airfields: ClosestAirfields,
        air_wing: AirWing,
        laser_code_registry: LaserCodeRegistry,
        flight_db: Database[Flight],
        is_player: bool,
        start_type: StartType,
        asap: bool,
    ) -> None:
        self.closest_airfields = closest_airfields
        self.is_player = is_player
        self.package = Package(location, flight_db, auto_asap=asap)
        self.air_wing = air_wing
        self.laser_code_registry = laser_code_registry
        self.start_type = start_type

    def plan_flight(self, plan: ProposedFlight, ignore_range: bool) -> bool:
        """Allocates aircraft for the given flight and adds them to the package.

        If no suitable aircraft are available, False is returned. If the failed
        flight was critical and the rest of the mission will be scrubbed, the
        caller should return any previously planned flights to the inventory
        using release_planned_aircraft.
        """
        target = self.package.target
        heli = False
        pf = self.package.primary_flight
        if pf:
            target = (
                pf.departure
                if pf.flight_type
                in [FlightType.AEWC, FlightType.REFUELING, FlightType.RECOVERY]
                else target
            )
            heli = pf.is_helo
        squadron = self.air_wing.best_squadron_for(
            target,
            plan.task,
            plan.num_aircraft,
            heli,
            this_turn=True,
            preferred_type=plan.preferred_type,
            ignore_range=ignore_range,
        )
        if squadron is None:
            return False
        start_type = squadron.location.required_aircraft_start_type
        if start_type is None:
            start_type = self.start_type

        flight = Flight(
            self.package,
            squadron,
            plan.num_aircraft,
            plan.task,
            start_type,
            divert=self.find_divert_field(squadron.aircraft, squadron.location),
        )
        for member in flight.iter_members():
            if member.is_player:
                member.assign_tgp_laser_code(
                    self.laser_code_registry.alloc_laser_code()
                )
        # If this is a client flight, set the start_type again to match the configured default
        # https://github.com/dcs-liberation/dcs_liberation/issues/1567
        if (
            squadron.location.required_aircraft_start_type is None
            and flight.roster is not None
            and flight.roster.player_count > 0
        ):
            flight.start_type = (
                squadron.coalition.game.settings.default_start_type_client
            )
        self.package.add_flight(flight)
        return True

    def find_divert_field(
        self, aircraft: AircraftType, arrival: ControlPoint
    ) -> Optional[ControlPoint]:
        divert_limit = nautical_miles(150)
        for airfield in self.closest_airfields.operational_airfields_within(
            divert_limit
        ):
            if airfield.captured != self.is_player:
                continue
            if airfield == arrival:
                continue
            if not airfield.can_operate(aircraft):
                continue
            if isinstance(airfield, OffMapSpawn):
                continue
            return airfield
        return None

    def build(self) -> Package:
        """Returns the built package."""
        return self.package

    def release_planned_aircraft(self) -> None:
        """Returns any planned flights to the inventory."""
        flights = list(self.package.flights)
        for flight in flights:
            self.package.remove_flight(flight)
