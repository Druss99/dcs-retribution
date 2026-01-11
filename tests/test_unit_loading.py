"""Tests to ensure all units can be loaded without errors."""

import logging
import tempfile
import unittest
from pathlib import Path
from typing import Iterator

from dcs.helicopters import helicopter_map
from dcs.planes import plane_map
from dcs.ships import ship_map
from dcs.vehicles import vehicle_map

from game import persistency
from game.dcs.aircrafttype import AircraftType
from game.dcs.groundunittype import GroundUnitType
from game.dcs.shipunittype import ShipUnitType
from game.squadrons.squadrondef import SquadronDef


class TestUnitLoading(unittest.TestCase):
    """Test that all unit definitions can be loaded successfully."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up persistency system for all tests."""
        # Create a temporary directory for the tests
        cls.temp_dir = tempfile.mkdtemp()
        persistency.setup(cls.temp_dir, False, 16880)

    # def test_all_aircraft_types_load(self) -> None:
    #     """Test that all aircraft YAML files can be loaded without errors."""
    #     errors = []
    #     loaded_count = 0

    #     # This will trigger loading all aircraft from YAML files
    #     try:
    #         for aircraft in AircraftType.iter_all():
    #             loaded_count += 1
    #             # Verify the aircraft has required attributes
    #             self.assertIsNotNone(aircraft.dcs_unit_type)
    #             self.assertIsNotNone(aircraft.variant_id)
    #             self.assertIsNotNone(aircraft.display_name)
    #             self.assertIsInstance(aircraft.price, int)
    #     except Exception as e:
    #         errors.append(f"Failed to load aircraft types: {e}")

    #     if errors:
    #         self.fail("\n".join(errors))

    #     # Ensure we actually loaded some aircraft
    #     self.assertGreater(loaded_count, 0, "No aircraft types were loaded")
    #     logging.info(f"Successfully loaded {loaded_count} aircraft types")

    def test_all_aircraft_variants_are_registered(self) -> None:
        """Test that all aircraft variants can be retrieved by name."""
        errors = []

        # Load all aircraft first
        list(AircraftType.iter_all())

        # Now verify each variant can be retrieved by its name
        for aircraft in AircraftType.iter_all():
            try:
                retrieved = AircraftType.named(aircraft.variant_id)
                self.assertEqual(
                    aircraft.variant_id,
                    retrieved.variant_id,
                    f"Retrieved aircraft variant ID mismatch",
                )
            except KeyError as e:
                errors.append(
                    f"Aircraft variant '{aircraft.variant_id}' cannot be retrieved by name: {e}"
                )

        if errors:
            self.fail("\n".join(errors))

    # def test_all_ground_unit_types_load(self) -> None:
    #     """Test that all ground unit YAML files can be loaded without errors."""
    #     errors = []
    #     loaded_count = 0
    #     allowed_warnings = ["No data for", "it will not be available", "has no class"]

    #     # Capture any warnings
    #     with self.assertLogs(level=logging.WARNING, logger=None) as log_context:
    #         # Add a dummy warning to ensure we have at least one log
    #         logging.getLogger().warning("Test start")
    #         try:
    #             # Load ground units by iterating through DCS types
    #             for dcs_unit in GroundUnitType.each_dcs_type():
    #                 for unit in GroundUnitType.for_dcs_type(dcs_unit):
    #                     loaded_count += 1
    #                     self.assertIsNotNone(unit.dcs_unit_type)
    #                     self.assertIsNotNone(unit.variant_id)
    #                     self.assertIsInstance(unit.price, int)
    #         except Exception as e:
    #             errors.append(f"Failed to load ground unit types: {e}")

    #     # Check that warnings are only about missing data (ignore test start marker)
    #     for record in log_context.records:
    #         msg = record.getMessage()
    #         if msg != "Test start" and not any(warning in msg for warning in allowed_warnings):
    #             errors.append(f"Unexpected warning: {msg}")

    #     if errors:
    #         self.fail("\n".join(errors))

    #     # Ground units might have 0 if none are defined, so we just log
    #     logging.info(f"Successfully loaded {loaded_count} ground unit types")

    # def test_all_ship_types_load(self) -> None:
    #     """Test that all ship YAML files can be loaded without errors."""
    #     errors = []
    #     loaded_count = 0
    #     allowed_warnings = ["No data for", "it will not be available", "has no class"]

    #     with self.assertLogs(level=logging.WARNING, logger=None) as log_context:
    #         # Add a dummy warning to ensure we have at least one log
    #         logging.getLogger().warning("Test start")
    #         try:
    #             # Load ships by iterating through DCS types
    #             for dcs_ship in ShipUnitType.each_dcs_type():
    #                 for ship in ShipUnitType.for_dcs_type(dcs_ship):
    #                     loaded_count += 1
    #                     self.assertIsNotNone(ship.dcs_unit_type)
    #                     self.assertIsNotNone(ship.variant_id)
    #                     self.assertIsInstance(ship.price, int)
    #         except Exception as e:
    #             errors.append(f"Failed to load ship types: {e}")

    #     # Check that warnings are only about missing data (ignore test start marker)
    #     for record in log_context.records:
    #         msg = record.getMessage()
    #         if msg != "Test start" and not any(warning in msg for warning in allowed_warnings):
    #             errors.append(f"Unexpected warning: {msg}")

    #     if errors:
    #         self.fail("\n".join(errors))

    #     # Ships might have 0 if none are defined, so we just log
    #     logging.info(f"Successfully loaded {loaded_count} ship types")

    def test_squadron_definitions_reference_valid_aircraft(self) -> None:
        """Test that all squadron definitions reference aircraft that exist."""
        errors = []
        squadron_count = 0

        # Load all aircraft first
        list(AircraftType.iter_all())

        # Check all squadron YAML files
        squadrons_dir = Path("resources/squadrons")
        if not squadrons_dir.exists():
            self.skipTest("Squadrons directory not found")

        for squadron_file in squadrons_dir.glob("*/*.yaml"):
            try:
                squadron = SquadronDef.from_yaml(squadron_file)
                squadron_count += 1

                # Verify the aircraft type exists
                self.assertIsNotNone(
                    squadron.aircraft,
                    f"Squadron {squadron.name} references invalid aircraft",
                )

                # Verify we can look up the aircraft by name
                try:
                    AircraftType.named(squadron.aircraft.variant_id)
                except KeyError as e:
                    errors.append(
                        f"Squadron '{squadron.name}' in {squadron_file} references "
                        f"aircraft '{squadron.aircraft.variant_id}' that cannot be found: {e}"
                    )

            except KeyError as e:
                errors.append(
                    f"Squadron {squadron_file} references invalid aircraft: {e}"
                )
            except Exception as e:
                # Allow other exceptions but log them
                logging.warning(
                    f"Could not fully validate squadron {squadron_file}: {e}"
                )

        if errors:
            self.fail("\n".join(errors))

        if squadron_count > 0:
            logging.info(
                f"Successfully validated {squadron_count} squadron definitions"
            )

    def test_no_duplicate_aircraft_variant_names(self) -> None:
        """Test that there are no duplicate aircraft variant names."""
        variant_names = set()
        duplicates = []

        for aircraft in AircraftType.iter_all():
            if aircraft.variant_id in variant_names:
                duplicates.append(aircraft.variant_id)
            variant_names.add(aircraft.variant_id)

        if duplicates:
            self.fail(
                f"Duplicate aircraft variant names found: {', '.join(duplicates)}"
            )

    def test_all_dcs_aircraft_types_have_yaml_files(self) -> None:
        """Test that all DCS aircraft types either have YAML files or are expected to be missing."""
        missing = []
        aircraft_dir = Path("resources/units/aircraft")

        for dcs_aircraft in list(helicopter_map.values()) + list(plane_map.values()):
            yaml_file = aircraft_dir / f"{dcs_aircraft.id}.yaml"
            if not yaml_file.exists():
                try:
                    list(AircraftType.for_dcs_type(dcs_aircraft))
                except StopIteration:
                    missing.append(dcs_aircraft.id)

        assert (
            not missing
        ), f"DCS aircraft types missing YAML files: {', '.join(missing)}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
