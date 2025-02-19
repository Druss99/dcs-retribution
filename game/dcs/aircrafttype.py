from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterator, Optional, TYPE_CHECKING, Type

import yaml
from dcs.helicopters import helicopter_map
from dcs.planes import plane_map
from dcs.unitpropertydescription import UnitPropertyDescription
from dcs.unittype import FlyingType
from dcs.weapons_data import weapon_ids

from game.ato import FlightType
from game.data.units import UnitClass
from game.dcs.lasercodeconfig import LaserCodeConfig
from game.dcs.unittype import UnitType
from game.persistency import user_custom_weapon_injections_dir
from game.radio.channels import (
    ApacheChannelNamer,
    ChannelNamer,
    CommonRadioChannelAllocator,
    FarmerRadioChannelAllocator,
    HueyChannelNamer,
    LegacyWarthogChannelNamer,
    MirageChannelNamer,
    MirageF1CEChannelNamer,
    NoOpChannelAllocator,
    RadioChannelAllocator,
    SCR522ChannelNamer,
    SCR522RadioChannelAllocator,
    SingleRadioChannelNamer,
    TomcatChannelNamer,
    ViggenChannelNamer,
    ViggenRadioChannelAllocator,
    ViperChannelNamer,
    WarthogChannelNamer,
    PhantomChannelNamer,
    KiowaChannelNamer,
)
from game.utils import (
    Distance,
    ImperialUnits,
    MetricUnits,
    NauticalUnits,
    SPEED_OF_SOUND_AT_SEA_LEVEL,
    Speed,
    UnitSystem,
    feet,
    knots,
    kph,
    nautical_miles,
)

if TYPE_CHECKING:
    from game.missiongenerator.aircraft.flightdata import FlightData
    from game.missiongenerator.missiondata import MissionData
    from game.radio.radios import Radio, RadioFrequency, RadioRegistry


@dataclass(frozen=True)
class RadioConfig:
    inter_flight: Optional[Radio]
    intra_flight: Optional[Radio]
    channel_allocator: Optional[RadioChannelAllocator]
    channel_namer: Type[ChannelNamer]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> RadioConfig:
        return RadioConfig(
            cls.make_radio(data.get("inter_flight", None)),
            cls.make_radio(data.get("intra_flight", None)),
            cls.make_allocator(data.get("channels", {})),
            cls.make_namer(data.get("channels", {})),
        )

    @classmethod
    def make_radio(cls, name: Optional[str]) -> Optional[Radio]:
        from game.radio.radios import get_radio

        if name is None:
            return None
        return get_radio(name)

    @classmethod
    def make_allocator(cls, data: dict[str, Any]) -> Optional[RadioChannelAllocator]:
        try:
            alloc_type = data["type"]
        except KeyError:
            return None
        allocator_type: Type[RadioChannelAllocator] = {
            "SCR-522": SCR522RadioChannelAllocator,
            "common": CommonRadioChannelAllocator,
            "farmer": FarmerRadioChannelAllocator,
            "noop": NoOpChannelAllocator,
            "viggen": ViggenRadioChannelAllocator,
        }[alloc_type]
        return allocator_type.from_cfg(data)

    @classmethod
    def make_namer(cls, config: dict[str, Any]) -> Type[ChannelNamer]:
        return {
            "SCR-522": SCR522ChannelNamer,
            "default": ChannelNamer,
            "huey": HueyChannelNamer,
            "mirage": MirageChannelNamer,
            "mirage-f1ce": MirageF1CEChannelNamer,
            "single": SingleRadioChannelNamer,
            "tomcat": TomcatChannelNamer,
            "viggen": ViggenChannelNamer,
            "viper": ViperChannelNamer,
            "apache": ApacheChannelNamer,
            "a10c-legacy": LegacyWarthogChannelNamer,
            "a10c-ii": WarthogChannelNamer,
            "phantom": PhantomChannelNamer,
            "kiowa": KiowaChannelNamer,
        }[config.get("namer", "default")]


@dataclass(frozen=True)
class PatrolConfig:
    altitude: Optional[Distance]
    speed: Optional[Speed]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> PatrolConfig:
        altitude = data.get("altitude", None)
        speed = data.get("speed", None)
        return PatrolConfig(
            feet(altitude) if altitude is not None else None,
            knots(speed) if speed is not None else None,
        )


@dataclass(frozen=True)
class AltitudesConfig:
    cruise: Optional[Distance]
    combat: Optional[Distance]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> AltitudesConfig:
        cruise = data.get("cruise", None)
        combat = data.get("combat", None)
        return AltitudesConfig(
            feet(cruise) if cruise is not None else None,
            feet(combat) if combat is not None else None,
        )


@dataclass(frozen=True)
class FuelConsumption:
    #: The estimated taxi fuel requirement, in pounds.
    taxi: int

    #: The estimated fuel consumption for a takeoff climb, in pounds per nautical mile.
    climb: float

    #: The estimated fuel consumption for cruising, in pounds per nautical mile.
    cruise: float

    #: The estimated fuel consumption for combat speeds, in pounds per nautical mile.
    combat: float

    #: The minimum amount of fuel that the aircraft should land with, in pounds. This is
    #: a reserve amount for landing delays or emergencies.
    min_safe: int

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> FuelConsumption:
        return FuelConsumption(
            int(data["taxi"]),
            float(data["climb_ppm"]),
            float(data["cruise_ppm"]),
            float(data["combat_ppm"]),
            int(data["min_safe"]),
        )


# TODO: Split into PlaneType and HelicopterType?
@dataclass(frozen=True)
class AircraftType(UnitType[Type[FlyingType]]):
    carrier_capable: bool
    lha_capable: bool
    always_keeps_gun: bool

    # If true, the aircraft does not use the guns as the last resort weapons, but as a
    # main weapon. It'll RTB when it doesn't have gun ammo left.
    gunfighter: bool

    # UnitSystem to use for the kneeboard, defaults to Nautical (kt/nm/ft)
    kneeboard_units: UnitSystem

    # If true, kneeboards will display zulu times
    utc_kneeboard: bool

    max_group_size: int
    patrol_altitude: Optional[Distance]
    patrol_speed: Optional[Speed]

    cruise_altitude: Optional[Distance]
    combat_altitude: Optional[Distance]

    #: The maximum range between the origin airfield and the target for which the auto-
    #: planner will consider this aircraft usable for a mission.
    max_mission_range: Distance

    fuel_consumption: Optional[FuelConsumption]

    default_livery: Optional[str]

    intra_flight_radio: Optional[Radio]
    channel_allocator: Optional[RadioChannelAllocator]
    channel_namer: Type[ChannelNamer]

    # Logisitcs info
    # cabin_size defines how many troops can be loaded. 0 means the aircraft can not
    # transport any troops. Default for helos is 10, non helos will have 0.
    cabin_size: int
    # If the aircraft can carry crates can_carry_crates should be set to true which
    # will be set to true for helos by default
    can_carry_crates: bool

    # Set to True when aircraft mounts a targeting pod by default i.e. the pod does
    # not take up a weapons station. If True, do not replace LGBs with dumb bombs
    # when no TGP is mounted on any station.
    has_built_in_target_pod: bool

    task_priorities: dict[FlightType, int]
    laser_code_configs: list[LaserCodeConfig]

    use_f15e_waypoint_names: bool

    _by_name: ClassVar[dict[str, AircraftType]] = {}
    _by_unit_type: ClassVar[dict[type[FlyingType], list[AircraftType]]] = defaultdict(
        list
    )

    def __setstate__(self, state: dict[str, Any]) -> None:
        # Save compat: the `name` field has been renamed `variant_id`.
        if "name" in state:
            state["variant_id"] = state.pop("name")

        # Update any existing models with new data on load.
        updated = AircraftType.named(state["variant_id"])
        self.__dict__.update(updated.__dict__)

    def __post_init__(self) -> None:
        enrich = {}
        if FlightType.SEAD_SWEEP not in self.task_priorities:
            if (value := self.task_priorities.get(FlightType.SEAD)) or (
                value := self.task_priorities.get(FlightType.SEAD_ESCORT)
            ):
                enrich[FlightType.SEAD_SWEEP] = value

        if FlightType.ARMED_RECON not in self.task_priorities:
            if (value := self.task_priorities.get(FlightType.CAS)) or (
                value := self.task_priorities.get(FlightType.BAI)
            ):
                enrich[FlightType.ARMED_RECON] = value

        if FlightType.RECOVERY not in self.task_priorities:
            if (
                value := self.task_priorities.get(FlightType.REFUELING)
            ) and self.carrier_capable is True:
                enrich[FlightType.RECOVERY] = value

        self.task_priorities.update(enrich)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AircraftType) and self.variant_id == other.variant_id

    @classmethod
    def register(cls, unit_type: AircraftType) -> None:
        cls._by_name[unit_type.variant_id] = unit_type
        cls._by_unit_type[unit_type.dcs_unit_type].append(unit_type)

    @property
    def flyable(self) -> bool:
        return self.dcs_unit_type.flyable

    @property
    def helicopter(self) -> bool:
        return self.dcs_unit_type.helicopter

    @property
    def max_fuel(self) -> float:
        return self.dcs_unit_type.fuel_max

    @cached_property
    def max_speed(self) -> Speed:
        return kph(self.dcs_unit_type.max_speed)

    @cached_property
    def preferred_patrol_altitude(self) -> Distance:
        if self.patrol_altitude:
            return self.patrol_altitude
        else:
            # TODO: somehow make the upper and lower limit configurable
            return self.preferred_altitude(10, 33, "patrol")

    def preferred_patrol_speed(self, altitude: Distance) -> Speed:
        """Preferred true airspeed when patrolling"""
        if self.patrol_speed is not None:
            return self.patrol_speed
        else:
            # Estimate based on max speed.
            max_speed = self.max_speed
            if max_speed > SPEED_OF_SOUND_AT_SEA_LEVEL * 1.6:
                # Fast airplanes, should manage pretty high patrol speed
                return (
                    Speed.from_mach(0.85, altitude)
                    if altitude.feet > 20000
                    else Speed.from_mach(0.7, altitude)
                )
            elif max_speed > SPEED_OF_SOUND_AT_SEA_LEVEL * 1.2:
                # Medium-fast like F/A-18C
                return (
                    Speed.from_mach(0.8, altitude)
                    if altitude.feet > 20000
                    else Speed.from_mach(0.65, altitude)
                )
            elif max_speed > SPEED_OF_SOUND_AT_SEA_LEVEL * 0.7:
                # Semi-fast like airliners or similar
                return (
                    Speed.from_mach(0.6, altitude)
                    if altitude.feet > 20000
                    else Speed.from_mach(0.5, altitude)
                )
            elif self.helicopter:
                return max_speed * 0.4
            else:
                # Slow like warbirds or attack planes
                # return 50% of max speed + 5% per 2k above 10k to maintain momentum
                return max_speed * min(
                    1.0,
                    0.5
                    + (
                        (((altitude.feet - 10000) / 2000) * 0.05)
                        if altitude.feet > 10000
                        else 0
                    ),
                )

    @cached_property
    def preferred_cruise_altitude(self) -> Distance:
        if self.cruise_altitude:
            return self.cruise_altitude
        else:
            # TODO: somehow make the upper and lower limit configurable
            return self.preferred_altitude(20, 20, "cruise")

    @cached_property
    def preferred_combat_altitude(self) -> Distance:
        if self.combat_altitude:
            return self.combat_altitude
        else:
            # TODO: somehow make the upper and lower limit configurable
            return self.preferred_altitude(20, 20, "combat")

    def preferred_altitude(self, low: int, high: int, type: str) -> Distance:
        # Estimate based on max speed.
        # Aircraft with max speed 600 kph will prefer low
        # Aircraft with max speed 2800 kph will prefer high
        altitude_for_lowest_speed = feet(low * 1000)
        altitude_for_highest_speed = feet(high * 1000)
        lowest_speed = kph(600)
        highest_speed = kph(2800)
        factor = (self.max_speed - lowest_speed).kph / (
            highest_speed - lowest_speed
        ).kph
        altitude = (
            altitude_for_lowest_speed
            + (altitude_for_highest_speed - altitude_for_lowest_speed) * factor
        )
        logging.debug(
            f"Preferred {type} altitude for {self.dcs_unit_type.id}: {altitude.feet}"
        )
        rounded_altitude = feet(round(1000 * round(altitude.feet / 1000)))
        return max(
            altitude_for_lowest_speed,
            min(altitude_for_highest_speed, rounded_altitude),
        )

    def alloc_flight_radio(self, radio_registry: RadioRegistry) -> RadioFrequency:
        from game.radio.radios import ChannelInUseError, kHz

        if self.intra_flight_radio is not None:
            return radio_registry.alloc_for_radio(self.intra_flight_radio)

        # The default radio frequency is set in megahertz. For some aircraft, it is a
        # floating point value. For all current aircraft, adjusting to kilohertz will be
        # sufficient to convert to an integer.
        in_khz = float(self.dcs_unit_type.radio_frequency) * 1000
        if not in_khz.is_integer():
            logging.warning(
                f"Found unexpected sub-kHz default radio for {self}: {in_khz} kHz. "
                "Truncating to integer. The truncated frequency may not be valid for "
                "the aircraft."
            )

        freq = kHz(int(in_khz))
        try:
            radio_registry.reserve(freq)
        except ChannelInUseError:
            pass
        return freq

    def assign_channels_for_flight(
        self, flight: FlightData, mission_data: MissionData
    ) -> None:
        if self.channel_allocator is not None:
            self.channel_allocator.assign_channels_for_flight(flight, mission_data)

    def channel_name(self, radio_id: int, channel_id: int) -> str:
        return self.channel_namer.channel_name(radio_id, channel_id)

    @cached_property
    def laser_code_prop_ids(self) -> set[str]:
        laser_code_props: set[str] = set()
        for laser_code_config in self.laser_code_configs:
            laser_code_props.update(laser_code_config.iter_prop_ids())
        return laser_code_props

    def iter_props(self) -> Iterator[UnitPropertyDescription]:
        yield from self.dcs_unit_type.properties.values()

    def should_show_prop(self, prop_id: str) -> bool:
        return prop_id not in self.laser_code_prop_ids

    def capable_of(self, task: FlightType) -> bool:
        return task in self.task_priorities

    def task_priority(self, task: FlightType) -> int:
        return self.task_priorities[task]

    @staticmethod
    def _migrator() -> Dict[str, str]:
        return {"F-15E Strike Eagle (AI)": "F-15E Strike Eagle"}

    @classmethod
    def named(cls, name: str) -> AircraftType:
        if not cls._loaded:
            cls._load_all()
        return cls._by_name[cls._migrator().get(name, name)]

    @classmethod
    def for_dcs_type(cls, dcs_unit_type: Type[FlyingType]) -> Iterator[AircraftType]:
        if not cls._loaded:
            cls._load_all()
        yield from cls._by_unit_type[dcs_unit_type]

    @classmethod
    def iter_all(cls) -> Iterator[AircraftType]:
        if not cls._loaded:
            cls._load_all()
        yield from cls._by_name.values()

    @classmethod
    @cache
    def priority_list_for_task(cls, task: FlightType) -> list[AircraftType]:
        capable = []
        for aircraft in cls.iter_all():
            if aircraft.capable_of(task):
                capable.append(aircraft)
        return list(reversed(sorted(capable, key=lambda a: a.task_priority(task))))

    def iter_task_capabilities(self) -> Iterator[FlightType]:
        yield from self.task_priorities

    @staticmethod
    def each_dcs_type() -> Iterator[Type[FlyingType]]:
        yield from helicopter_map.values()
        yield from plane_map.values()

    @staticmethod
    def _set_props_overrides(
        config: Dict[str, Any], aircraft: Type[FlyingType]
    ) -> None:
        if aircraft.property_defaults is None:
            logging.warning(
                f"'{aircraft.id}' attempted to set default prop that does not exist."
            )
        else:
            for k in config:
                if k in aircraft.property_defaults:
                    aircraft.property_defaults[k] = config[k]
                else:
                    logging.warning(
                        f"'{aircraft.id}' attempted to set default prop '{k}' that does not exist"
                    )

    @classmethod
    def _data_directory(cls) -> Path:
        return Path("resources/units/aircraft")

    @classmethod
    def _variant_from_dict(
        cls, aircraft: Type[FlyingType], variant_id: str, data: dict[str, Any]
    ) -> AircraftType:
        try:
            price = data["price"]
        except KeyError as ex:
            raise KeyError(f"Missing required price field") from ex

        radio_config = RadioConfig.from_data(data.get("radios", {}))
        patrol_config = PatrolConfig.from_data(data.get("patrol", {}))
        altitudes_config = AltitudesConfig.from_data(data.get("altitudes", {}))

        try:
            mission_range = nautical_miles(int(data["max_range"]))
        except (KeyError, ValueError):
            mission_range = (
                nautical_miles(50) if aircraft.helicopter else nautical_miles(150)
            )
            logging.warning(
                f"{variant_id} does not specify a max_range. Defaulting to "
                f"{mission_range.nautical_miles}NM"
            )

        fuel_data = data.get("fuel")
        if fuel_data is not None:
            fuel_consumption: Optional[FuelConsumption] = FuelConsumption.from_data(
                fuel_data
            )
        else:
            fuel_consumption = None

        try:
            introduction = data["introduced"]
            if introduction is None:
                introduction = "N/A"
        except KeyError:
            introduction = "No data."

        units_data = data.get("kneeboard_units", "nautical").lower()
        units: UnitSystem = NauticalUnits()
        if units_data == "imperial":
            units = ImperialUnits()
        if units_data == "metric":
            units = MetricUnits()

        class_name = data.get("class")
        unit_class = UnitClass.PLANE if class_name is None else UnitClass(class_name)

        prop_overrides = data.get("default_overrides")
        if prop_overrides is not None:
            cls._set_props_overrides(prop_overrides, aircraft)

        task_priorities = cls.get_task_priorities(data)

        cls._custom_weapon_injections(aircraft, data)
        cls._user_weapon_injections(aircraft)

        display_name = data.get("display_name", variant_id)
        return AircraftType(
            dcs_unit_type=aircraft,
            variant_id=variant_id,
            display_name=display_name,
            description=data.get(
                "description",
                f"No data. <a href=\"https://google.com/search?q=DCS+{display_name.replace(' ', '+')}\"><span style=\"color:#FFFFFF\">Google {display_name}</span></a>",
            ),
            year_introduced=introduction,
            country_of_origin=data.get("origin", "No data."),
            manufacturer=data.get("manufacturer", "No data."),
            role=data.get("role", "No data."),
            price=price,
            carrier_capable=data.get("carrier_capable", False),
            lha_capable=data.get("lha_capable", False),
            always_keeps_gun=data.get("always_keeps_gun", False),
            gunfighter=data.get("gunfighter", False),
            max_group_size=data.get("max_group_size", aircraft.group_size_max),
            patrol_altitude=patrol_config.altitude,
            patrol_speed=patrol_config.speed,
            cruise_altitude=altitudes_config.cruise,
            combat_altitude=altitudes_config.combat,
            max_mission_range=mission_range,
            fuel_consumption=fuel_consumption,
            default_livery=data.get("default_livery"),
            intra_flight_radio=radio_config.intra_flight,
            channel_allocator=radio_config.channel_allocator,
            channel_namer=radio_config.channel_namer,
            kneeboard_units=units,
            utc_kneeboard=data.get("utc_kneeboard", False),
            unit_class=unit_class,
            cabin_size=data.get("cabin_size", 10 if aircraft.helicopter else 0),
            can_carry_crates=data.get("can_carry_crates", aircraft.helicopter),
            task_priorities=task_priorities,
            has_built_in_target_pod=data.get("has_built_in_target_pod", False),
            laser_code_configs=[
                LaserCodeConfig.from_yaml(d) for d in data.get("laser_codes", [])
            ],
            use_f15e_waypoint_names=data.get("use_f15e_waypoint_names", False),
        )

    @classmethod
    def get_task_priorities(cls, data: dict[str, Any]) -> dict[FlightType, int]:
        task_priorities: dict[FlightType, int] = {}
        for task_name, priority in data.get("tasks", {}).items():
            task_priorities[FlightType(task_name)] = priority
        if (
            FlightType.SEAD_SWEEP not in task_priorities
            and FlightType.SEAD in task_priorities
        ):
            task_priorities[FlightType.SEAD_SWEEP] = task_priorities[FlightType.SEAD]
        if FlightType.ARMED_RECON not in task_priorities:
            if FlightType.CAS in task_priorities:
                task_priorities[FlightType.ARMED_RECON] = task_priorities[
                    FlightType.CAS
                ]
            elif FlightType.BAI in task_priorities:
                task_priorities[FlightType.ARMED_RECON] = task_priorities[
                    FlightType.BAI
                ]
        return task_priorities

    @staticmethod
    def _custom_weapon_injections(
        aircraft: Type[FlyingType], data: Dict[str, Any]
    ) -> None:
        if (wpn_injection := data.get("weapon_injections")) is not None:
            pylons = [
                v
                for v in aircraft.__dict__.values()
                if inspect.isclass(v) and v.__name__.startswith(f"Pylon")
            ]
            pylons.sort(key=lambda x: int(x.__name__.replace("Pylon", "")))
            for pylon_number, weapons in wpn_injection.items():
                for w in weapons:
                    weapon = weapon_ids[w]
                    pylon = [
                        pylon
                        for pylon in pylons
                        if int(pylon.__name__.replace("Pylon", "")) == pylon_number
                    ][0]
                    setattr(pylon, w, (pylon_number, weapon))

    @staticmethod
    def _user_weapon_injections(aircraft: Type[FlyingType]) -> None:
        data_path = user_custom_weapon_injections_dir() / f"{aircraft.id}.yaml"
        if not data_path.exists():
            return
        with data_path.open(encoding="utf-8") as data_file:
            data = yaml.safe_load(data_file)
        AircraftType._custom_weapon_injections(aircraft, data)

    def __hash__(self) -> int:
        return hash(self.variant_id)
