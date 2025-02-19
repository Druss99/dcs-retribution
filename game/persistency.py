from __future__ import annotations

import logging
import pickle
import shutil
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any

import dcs.terrain.falklands.airports

import pydcs_extensions
from game.profiling import logged_duration
from pydcs_extensions import (
    ELM2084_MMR_AD_RT,
    Iron_Dome_David_Sling_CP,
    RBS_70,
    RBS_90,
    CH_BVS10,
    Artillerisystem08_M982,
)

if TYPE_CHECKING:
    from game import Game

_dcs_saved_game_folder: Optional[str] = None
_prefer_liberation_payloads: bool = False
_server_port: int = 16880


# fmt: off
class DummyObject:
    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)


class MigrationUnpickler(pickle.Unpickler):
    """Custom unpickler to migrate campaign save-files for when components have been moved"""
    def find_class(self, module: Any, name: str) -> Any:
        if name == "NightMissions":
            from game.settings import NightMissions
            return NightMissions
        if name == "Conditions":
            from game.weather.conditions import Conditions
            return Conditions
        if name == "AtmosphericConditions":
            from game.weather.atmosphericconditions import AtmosphericConditions
            return AtmosphericConditions
        if name == "WindConditions":
            from game.weather.wind import WindConditions
            return WindConditions
        if name == "Clouds":
            from game.weather.clouds import Clouds
            return Clouds
        if name == "Fog":
            from game.weather.fog import Fog
            return Fog
        if name == "ClearSkies":
            from game.weather.weather import ClearSkies
            return ClearSkies
        if name == "Cloudy":
            from game.weather.weather import Cloudy
            return Cloudy
        if name == "Raining":
            from game.weather.weather import Raining
            return Raining
        if name == "Thunderstorm":
            from game.weather.weather import Thunderstorm
            return Thunderstorm
        if name == "Hipico":
            return dcs.terrain.falklands.airports.Hipico_Flying_Club
        if name in ["SaveManager", "SaveGameBundle"]:
            return DummyObject
        if name in ["CaletaTortel", "Caleta_Tortel_Airport"]:
            return dcs.terrain.Airport  # use base-class if airport was removed
        if module == "pydcs_extensions.f4b.f4b":
            return pydcs_extensions.f4
        if module == "pydcs_extensions.irondome.irondome":
            if name in ["I9K57_URAGAN", "I9K51_GRAD", "I9K58_SMERCH"]:
                return None
            elif name == "ELM2048_MMR":
                return ELM2084_MMR_AD_RT
            elif name == "IRON_DOME_CP":
                return Iron_Dome_David_Sling_CP
        if module == "pydcs_extensions.swedishmilitaryassetspack.swedishmilitaryassetspack":
            if name == "BV410_RBS90":
                return RBS_90
            elif name == "BV410":
                return CH_BVS10
            elif name == "Artillerisystem08":
                return Artillerisystem08_M982
            elif name == "BV410_RBS70":
                return RBS_70
        if module == "dcs.terrain.kola.airports":
            if name == "Lakselv":
                from dcs.terrain.kola.airports import Banak
                return Banak
            elif name == "Severomorsk1":
                from dcs.terrain.kola.airports import Severomorsk_1
                return Severomorsk_1
            elif name == "Severomorsk3":
                from dcs.terrain.kola.airports import Severomorsk_3
                return Severomorsk_3
            elif name == "Olenegorsk":
                from dcs.terrain.kola.airports import Olenya
                return Olenya
            elif name == "Bas_100":
                from dcs.terrain.kola.airports import Vuojarvi
                return Vuojarvi
        if module == "dcs.terrain.syria.airports":
            if name == "Amman":
                from dcs.terrain.syria.airports import Marka
                return Marka
            elif name in [
                "Helipad_88",
                "Helipad_183",
                "Helipad_217",
                "Helipad_218"
            ]:
                return dcs.terrain.Airport  # use base-class if airport was removed
        if module == "dcs.terrain.falklands.airports":
            if name == "Aerodromo_De_Tolhuin":
                from dcs.terrain.falklands.airports import Tolhuin
                return Tolhuin
            elif name == "Porvenir_Airfield":
                from dcs.terrain.falklands.airports import Porvenir
                return Porvenir
            elif name == "Aeropuerto_de_Gobernador_Gregores":
                from dcs.terrain.falklands.airports import Gobernador_Gregores
                return Gobernador_Gregores
            elif name == "Aerodromo_O_Higgins":
                from dcs.terrain.falklands.airports import O_Higgins
                return O_Higgins
        if module in ["dcs.vehicles", "dcs.ships"]:
            try:
                return super().find_class(module, name)
            except AttributeError:
                alternate = name.split('.')[:-1] + [name.split('.')[-1][0].lower() + name.split('.')[-1][1:]]
                name = '.'.join(alternate)
        try:
            return super().find_class(module, name)
        except AttributeError:
            if "dcs.terrain" in module and "airports" not in module:
                module = f"{module}.airports"
            else:
                raise
        return super().find_class(module, name)
# fmt: on


def _create_dir_if_needed(path: Path) -> Path:
    if not path.exists():
        path.mkdir(755, parents=True)
    return path


def setup(user_folder: str, prefer_liberation_payloads: bool, port: int) -> None:
    global _dcs_saved_game_folder
    global _prefer_liberation_payloads
    global _server_port
    _dcs_saved_game_folder = user_folder
    _prefer_liberation_payloads = prefer_liberation_payloads
    _server_port = port
    _create_dir_if_needed(save_dir())


def base_path() -> Path:
    global _dcs_saved_game_folder
    assert _dcs_saved_game_folder
    return _create_dir_if_needed(Path(_dcs_saved_game_folder))


def debug_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Debug")


def factions_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Factions")


def groups_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Groups")


def layouts_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Layouts")


def waypoint_debug_directory() -> Path:
    return _create_dir_if_needed(debug_dir() / "Waypoints")


def settings_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Settings")


def airwing_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "AirWing")


def kneeboards_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Kneeboards")


def payloads_dir(backup: bool = False) -> Path:
    payloads = base_path() / "MissionEditor" / "UnitPayloads"
    if backup:
        return _create_dir_if_needed(payloads / "_retribution_backups")
    return _create_dir_if_needed(payloads)


def prefer_liberation_payloads() -> bool:
    global _prefer_liberation_payloads
    return _prefer_liberation_payloads


def user_custom_weapon_injections_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "WeaponInjections")


def save_dir() -> Path:
    return _create_dir_if_needed(base_path() / "Retribution" / "Saves")


def pre_pretense_backups_dir() -> Path:
    return _create_dir_if_needed(save_dir() / "PrePretenseBackups")


def server_port() -> int:
    global _server_port
    return _server_port


def _temporary_save_file() -> str:
    return str(save_dir() / "tmpsave.retribution")


def _autosave_path() -> str:
    return str(save_dir() / "autosave.retribution")


def mission_path_for(name: str) -> Path:
    return base_path() / "Missions" / name


def load_game(path: str) -> Optional[Game]:
    with open(path, "rb") as f:
        try:
            save = MigrationUnpickler(f).load()
            save.savepath = path
            return save
        except Exception:
            logging.exception("Invalid Save game")
            return None


def save_game(game: Game) -> bool:
    with logged_duration("Saving game"):
        try:
            with open(_temporary_save_file(), "wb") as f:
                data = _unload_static_data(game)
                pickle.dump(game, f)
                _restore_static_data(game, data)
            shutil.copy(_temporary_save_file(), game.savepath)
            return True
        except Exception:
            logging.exception("Could not save game")
            return False


def _restore_static_data(game: Game, data: dict[str, Any]) -> None:
    game.theater.landmap = data["landmap"]


def _unload_static_data(game: Game) -> dict[str, Any]:
    landmap = game.theater.landmap
    game.theater.landmap = None
    return {
        "landmap": landmap,
    }


def autosave(game: Game) -> bool:
    """
    Autosave to the autosave location
    :param game: Game to save
    :return: True if saved successfully
    """
    try:
        with open(_autosave_path(), "wb") as f:
            data = _unload_static_data(game)
            pickle.dump(game, f)
            _restore_static_data(game, data)
        return True
    except Exception:
        logging.exception("Could not save game")
        return False
