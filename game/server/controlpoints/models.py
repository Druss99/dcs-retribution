from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from game.server.leaflet import LeafletPoint
from game.theater import Player

if TYPE_CHECKING:
    from game import Game
    from game.theater import ControlPoint
    from enum import Enum


class ControlPointJs(BaseModel):
    id: UUID
    name: str
    blue: int
    position: LeafletPoint
    mobile: bool
    destination: LeafletPoint | None
    sidc: str

    class Config:
        title = "ControlPoint"

    @staticmethod
    def for_control_point(control_point: ControlPoint) -> ControlPointJs:
        destination = None
        if control_point.target_position is not None:
            destination = control_point.target_position.latlng()
        if control_point.captured is Player.NEUTRAL:
            blue = 0
        elif control_point.captured is Player.BLUE:
            blue = 1
        else:
            blue = 2
        return ControlPointJs(
            id=control_point.id,
            name=control_point.name,
            blue=blue,
            position=control_point.position.latlng(),
            mobile=control_point.moveable and control_point.captured is Player.BLUE,
            destination=destination,
            sidc=str(control_point.sidc()),
        )

    @staticmethod
    def all_in_game(game: Game) -> list[ControlPointJs]:
        return [
            ControlPointJs.for_control_point(cp) for cp in game.theater.controlpoints
        ]
