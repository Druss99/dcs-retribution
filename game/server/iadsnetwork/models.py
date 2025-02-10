from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from game.server.leaflet import LeafletPoint
from game.theater.player import Player
from game.theater.iadsnetwork.iadsnetwork import IadsNetworkNode, IadsNetwork


class IadsConnectionJs(BaseModel):
    id: UUID
    points: list[LeafletPoint]
    node: UUID
    connected: UUID
    active: bool
    blue: int
    is_power: bool

    class Config:
        title = "IadsConnection"

    @staticmethod
    def connections_for_tgo(
        tgo_id: UUID, network: IadsNetwork
    ) -> list[IadsConnectionJs]:
        for node in network.nodes:
            if node.group.ground_object.id == tgo_id:
                return IadsConnectionJs.connections_for_node(node)
        return []

    @staticmethod
    def connections_for_node(network_node: IadsNetworkNode) -> list[IadsConnectionJs]:
        iads_connections = []
        tgo = network_node.group.ground_object
        for id, connection in network_node.connections.items():
            if connection.ground_object.is_friendly(Player.BLUE) != tgo.is_friendly(
                Player.BLUE
            ):
                continue  # Skip connections which are not from same coalition
            if tgo.is_friendly(Player.BLUE):
                blue = 1
            elif tgo.is_friendly(Player.RED):
                blue = 2
            else:
                continue  # Skip neutral
            iads_connections.append(
                IadsConnectionJs(
                    id=id,
                    points=[
                        tgo.position.latlng(),
                        connection.ground_object.position.latlng(),
                    ],
                    node=tgo.id,
                    connected=connection.ground_object.id,
                    active=(
                        network_node.group.alive_units > 0
                        and connection.alive_units > 0
                    ),
                    blue=blue,
                    is_power="power"
                    in [tgo.category, connection.ground_object.category],
                )
            )
        return iads_connections


class IadsNetworkJs(BaseModel):
    advanced: bool
    connections: list[IadsConnectionJs]

    class Config:
        title = "IadsNetwork"

    @staticmethod
    def from_network(network: IadsNetwork) -> IadsNetworkJs:
        iads_connections = []
        for connection in network.nodes:
            if not connection.group.iads_role.participate:
                continue  # Skip
            iads_connections.extend(IadsConnectionJs.connections_for_node(connection))
        return IadsNetworkJs(
            advanced=network.advanced_iads, connections=iads_connections
        )
