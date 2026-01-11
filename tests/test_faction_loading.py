"""Tests to ensure all faction files are valid and reference existing units."""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

from game import persistency
from game.dcs.aircrafttype import AircraftType
from game.dcs.groundunittype import GroundUnitType
from game.dcs.shipunittype import ShipUnitType
from game.factions.faction import Faction
from game.factions.factionloader import FactionLoader, FACTION_DIRECTORY


class TestFactionLoading(unittest.TestCase):
    """Test that all faction definitions are valid and reference existing units."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up persistency system and load all units for validation."""
        # Create a temporary directory for the tests
        cls.temp_dir = tempfile.mkdtemp()
        persistency.setup(cls.temp_dir, False, 16880)

        # Pre-load all unit types to ensure they're available for validation
        list(AircraftType.iter_all())
        # Load ground units and ships by iterating through DCS types
        for dcs_unit in GroundUnitType.each_dcs_type():
            list(GroundUnitType.for_dcs_type(dcs_unit))
        for dcs_ship in ShipUnitType.each_dcs_type():
            list(ShipUnitType.for_dcs_type(dcs_ship))

    def test_all_faction_files_are_parseable(self) -> None:
        """Test that all faction JSON/YAML files can be parsed."""
        errors = []
        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        self.assertGreater(len(faction_files), 0, "No faction files found")

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                # Basic structure validation
                if not isinstance(data, dict):
                    errors.append(
                        f"{faction_file.name}: Root element is not a dictionary"
                    )
                    continue

                if "name" not in data:
                    errors.append(f"{faction_file.name}: Missing required 'name' field")

                if "country" not in data:
                    errors.append(
                        f"{faction_file.name}: Missing required 'country' field"
                    )

            except json.JSONDecodeError as e:
                errors.append(f"{faction_file.name}: JSON parsing error - {e}")
            except yaml.YAMLError as e:
                errors.append(f"{faction_file.name}: YAML parsing error - {e}")
            except Exception as e:
                errors.append(f"{faction_file.name}: Unexpected error - {e}")

        if errors:
            self.fail("\n".join(errors))

        logging.info(f"Successfully parsed {len(faction_files)} faction files")

    def test_all_factions_load_successfully(self) -> None:
        """Test that all factions can be loaded through the FactionLoader."""
        loader = FactionLoader()
        errors = []
        loaded_count = 0

        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                # Try to create a Faction from the data
                faction = Faction.from_dict(data)
                loaded_count += 1

                # Basic validation
                self.assertIsNotNone(
                    faction.name, f"{faction_file.name}: Faction has no name"
                )
                self.assertIsNotNone(
                    faction.country, f"{faction_file.name}: Faction has no country"
                )

            except KeyError as e:
                errors.append(f"{faction_file.name}: Missing or invalid field - {e}")
            except Exception as e:
                errors.append(f"{faction_file.name}: Failed to load - {e}")

        if errors:
            self.fail("\n".join(errors))

        self.assertGreater(loaded_count, 0, "No factions were loaded")
        logging.info(f"Successfully loaded {loaded_count} factions")

    def test_all_faction_aircraft_exist(self) -> None:
        """Test that all aircraft referenced in factions actually exist."""
        errors = []
        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                faction_name = data.get("name", faction_file.name)

                # Check aircraft
                for aircraft_name in data.get("aircrafts", []):
                    try:
                        AircraftType.named(aircraft_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Aircraft '{aircraft_name}' does not exist"
                        )

                # Check AWACS
                for awacs_name in data.get("awacs", []):
                    try:
                        AircraftType.named(awacs_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: AWACS '{awacs_name}' does not exist"
                        )

                # Check tankers
                for tanker_name in data.get("tankers", []):
                    try:
                        AircraftType.named(tanker_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Tanker '{tanker_name}' does not exist"
                        )

            except Exception as e:
                logging.warning(f"Could not validate {faction_file.name}: {e}")

        if errors:
            self.fail("\n".join(errors))

    def test_all_faction_ground_units_exist(self) -> None:
        """Test that all ground units referenced in factions actually exist."""
        errors = []
        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                faction_name = data.get("name", faction_file.name)

                # Check frontline units
                for unit_name in data.get("frontline_units", []):
                    try:
                        GroundUnitType.named(unit_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Frontline unit '{unit_name}' does not exist"
                        )

                # Check artillery units
                for unit_name in data.get("artillery_units", []):
                    try:
                        GroundUnitType.named(unit_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Artillery unit '{unit_name}' does not exist"
                        )

                # Check infantry units
                for unit_name in data.get("infantry_units", []):
                    try:
                        GroundUnitType.named(unit_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Infantry unit '{unit_name}' does not exist"
                        )

                # Check logistics units
                for unit_name in data.get("logistics_units", []):
                    try:
                        GroundUnitType.named(unit_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Logistics unit '{unit_name}' does not exist"
                        )

                # Check air defense units
                for unit_name in data.get("air_defense_units", []):
                    try:
                        GroundUnitType.named(unit_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Air defense unit '{unit_name}' does not exist"
                        )

                # Check missiles
                for unit_name in data.get("missiles", []):
                    try:
                        GroundUnitType.named(unit_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Missile unit '{unit_name}' does not exist"
                        )

            except Exception as e:
                logging.warning(f"Could not validate {faction_file.name}: {e}")

        if errors:
            self.fail("\n".join(errors))

    def test_all_faction_naval_units_exist(self) -> None:
        """Test that all naval units referenced in factions actually exist."""
        errors = []
        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                faction_name = data.get("name", faction_file.name)

                # Check naval units
                for ship_name in data.get("naval_units", []):
                    try:
                        ShipUnitType.named(ship_name)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Naval unit '{ship_name}' does not exist"
                        )

                # Check cargo ship
                cargo_ship = data.get("cargo_ship")
                if cargo_ship:
                    try:
                        ShipUnitType.named(cargo_ship)
                    except KeyError:
                        errors.append(
                            f"{faction_name}: Cargo ship '{cargo_ship}' does not exist"
                        )

            except Exception as e:
                logging.warning(f"Could not validate {faction_file.name}: {e}")

        if errors:
            self.fail("\n".join(errors))

    def test_all_faction_preset_groups_are_valid(self) -> None:
        """Test that preset groups referenced in factions actually exist."""
        errors = []
        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        # Load all ForceGroups to build the registry
        from game.armedforces.forcegroup import ForceGroup

        ForceGroup._load_all()
        available_groups = set(ForceGroup._by_name.keys())

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                faction_name = data.get("name", faction_file.name)

                # Preset groups are stored as strings (group names, not filenames)
                for preset_group_name in data.get("preset_groups", []):
                    if not isinstance(preset_group_name, str):
                        errors.append(
                            f"{faction_name}: Preset group entry '{preset_group_name}' is not a string"
                        )
                        continue

                    # Check if the group name exists in loaded ForceGroups
                    if preset_group_name not in available_groups:
                        errors.append(
                            f"{faction_name}: Preset group '{preset_group_name}' does not exist"
                        )

            except Exception as e:
                logging.warning(
                    f"Could not validate preset groups in {faction_file.name}: {e}"
                )

        if errors:
            self.fail("\n".join(errors))

    def test_faction_carriers_are_valid(self) -> None:
        """Test that carrier units specified in factions exist in naval_units."""
        errors = []
        faction_files = FactionLoader.find_faction_files_in(FACTION_DIRECTORY)

        for faction_file in faction_files:
            try:
                with faction_file.open("r", encoding="utf-8") as f:
                    if "yml" in faction_file.name or "yaml" in faction_file.name:
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

                faction_name = data.get("name", faction_file.name)
                naval_units = set(data.get("naval_units", []))

                # Check carriers (new format)
                carriers = data.get("carriers", {})
                if isinstance(carriers, dict):
                    for carrier_type, carrier_names in carriers.items():
                        if carrier_type not in naval_units:
                            errors.append(
                                f"{faction_name}: Carrier '{carrier_type}' is not in naval_units"
                            )

            except Exception as e:
                logging.warning(
                    f"Could not validate carriers in {faction_file.name}: {e}"
                )

        if errors:
            self.fail("\n".join(errors))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
