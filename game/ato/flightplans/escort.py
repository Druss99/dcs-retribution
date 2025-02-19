from __future__ import annotations

from datetime import datetime
from typing import Type

from .airassault import AirAssaultLayout
from .airlift import AirliftLayout
from .formationattack import (
    FormationAttackBuilder,
    FormationAttackFlightPlan,
    FormationAttackLayout,
)
from .waypointbuilder import WaypointBuilder
from .. import FlightType
from ..packagewaypoints import PackageWaypoints
from ...utils import feet


class EscortFlightPlan(FormationAttackFlightPlan):
    @staticmethod
    def builder_type() -> Type[Builder]:
        return Builder

    @property
    def split_time(self) -> datetime:
        if self.package.primary_flight and self.package.primary_flight.flight_plan:
            return self.package.primary_flight.flight_plan.mission_departure_time
        else:
            return super().split_time


class Builder(FormationAttackBuilder[EscortFlightPlan, FormationAttackLayout]):
    def layout(self) -> FormationAttackLayout:
        non_formation_escort = False
        if self.package.waypoints is None:
            self.package.waypoints = PackageWaypoints.create(
                self.package, self.coalition, dump_debug_info=False
            )
            if self.package.primary_flight:
                departure = self.package.primary_flight.flight_plan.layout.departure
                self.package.waypoints.join = departure.position.lerp(
                    self.package.target.position, 0.2
                )
                non_formation_escort = True

        builder = WaypointBuilder(self.flight)
        ingress, target = builder.escort(
            self.package.waypoints.ingress, self.package.target
        )
        if non_formation_escort:
            target.position = self.package.waypoints.join
        ingress.only_for_player = True
        target.only_for_player = True
        hold = None
        if not (self.flight.is_helo or non_formation_escort):
            hold = builder.hold(self._hold_point())

        join_pos = (
            WaypointBuilder.perturb(self.package.waypoints.ingress, feet(500))
            if self.flight.is_helo
            else self.package.waypoints.join
        )
        join = builder.join(join_pos)

        split = builder.split(self._get_split())

        is_helo = builder.flight.is_helo
        initial = builder.escort_hold(
            target.position if is_helo else self.package.waypoints.initial,
        )

        pf = self.package.primary_flight
        if pf and pf.flight_type in [FlightType.AIR_ASSAULT, FlightType.TRANSPORT]:
            layout = pf.flight_plan.layout
            assert isinstance(layout, AirAssaultLayout) or isinstance(
                layout, AirliftLayout
            )
            if isinstance(layout, AirliftLayout):
                ascent = layout.pickup_ascent or layout.drop_off_ascent
                assert ascent is not None
                join = builder.join(ascent.position)
                if layout.pickup and layout.drop_off_ascent:
                    join = builder.join(layout.drop_off_ascent.position)
            split = builder.split(layout.arrival.position)
            if layout.drop_off:
                initial = builder.escort_hold(
                    layout.drop_off.position,
                )

        refuel = self._build_refuel(builder)

        departure = builder.takeoff(self.flight.departure)
        nav_to = builder.nav_path(
            hold.position if hold else departure.position,
            join.position,
            builder.get_cruise_altitude,
        )

        nav_from = builder.nav_path(
            refuel.position if refuel else split.position,
            self.flight.arrival.position,
            builder.get_cruise_altitude,
        )

        return FormationAttackLayout(
            departure=departure,
            hold=hold,
            nav_to=nav_to,
            join=join,
            ingress=ingress,
            initial=initial,
            targets=[target],
            split=split,
            refuel=refuel,
            nav_from=nav_from,
            arrival=builder.land(self.flight.arrival),
            divert=builder.divert(self.flight.divert),
            bullseye=builder.bullseye(),
            custom_waypoints=list(),
        )

    def build(self, dump_debug_info: bool = False) -> EscortFlightPlan:
        return EscortFlightPlan(self.flight, self.layout())
