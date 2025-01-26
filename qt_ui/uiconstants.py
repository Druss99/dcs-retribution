import os
from typing import Dict

from PySide6.QtGui import QPixmap

from .liberation_theme import get_theme_icons

URLS: Dict[str, str] = {
    "Manual": "https://github.com/dcs-retribution/dcs-retribution/wiki",
    "Repository": "https://github.com/dcs-retribution/dcs-retribution",
    "ForumThread": "https://forums.eagle.ru/showthread.php?t=214834",
    "Issues": "https://github.com/dcs-retribution/dcs-retribution/issues",
    "Releases": "https://github.com/dcs-retribution/dcs-retribution/releases",
}

LABELS_OPTIONS = ["Full", "Abbreviated", "Dot Only", "Neutral Dot", "Off"]
SKILL_OPTIONS = ["Average", "Good", "High", "Excellent"]

AIRCRAFT_ICONS: Dict[str, QPixmap] = {}
VEHICLES_ICONS: Dict[str, QPixmap] = {}
ICONS: Dict[str, QPixmap] = {}


def load_icons():
    ICONS["New"] = QPixmap("./resources/ui/misc/" + get_theme_icons() + "/new.png")
    ICONS["Open"] = QPixmap("./resources/ui/misc/" + get_theme_icons() + "/open.png")
    ICONS["Save"] = QPixmap("./resources/ui/misc/" + get_theme_icons() + "/save.png")
    ICONS["Discord"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/discord.png"
    )
    ICONS["Github"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/github.png"
    )
    ICONS["Ukraine"] = QPixmap("./resources/ui/misc/ukraine.png")
    ICONS["Pretense"] = QPixmap("./resources/ui/misc/pretense.png")
    ICONS["Pretense_discord"] = QPixmap("./resources/ui/misc/pretense_discord.png")
    ICONS["Pretense_generate"] = QPixmap("./resources/ui/misc/pretense_generate.png")

    ICONS["Control Points"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/circle.png"
    )
    ICONS["Ground Objects"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/industry.png"
    )
    ICONS["Lines"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/arrows-h.png"
    )
    ICONS["Waypoint Information"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/info.png"
    )
    ICONS["Map Polygon Debug Mode"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/map.png"
    )
    ICONS["Ally SAM Threat Range"] = QPixmap("./resources/ui/misc/blue-sam.png")
    ICONS["Enemy SAM Threat Range"] = QPixmap("./resources/ui/misc/red-sam.png")
    ICONS["SAM Detection Range"] = QPixmap("./resources/ui/misc/detection-sam.png")
    ICONS["Display Culling Zones"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/eraser.png"
    )
    ICONS["Hide Flight Paths"] = QPixmap("./resources/ui/misc/hide-flight-path.png")
    ICONS["Show Selected Flight Path"] = QPixmap("./resources/ui/misc/flight-path.png")
    ICONS["Show All Flight Paths"] = QPixmap("./resources/ui/misc/all-flight-paths.png")

    ICONS["Hangar"] = QPixmap("./resources/ui/misc/hangar.png")

    ICONS["Dawn"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/timeofday/dawn.png"
    )
    ICONS["Day"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/timeofday/day.png"
    )
    ICONS["Dusk"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/timeofday/dusk.png"
    )
    ICONS["Night"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/timeofday/night.png"
    )

    ICONS["Money"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/money_icon.png"
    )
    ICONS["Campaign Management"] = ICONS["Money"]
    ICONS["Campaign Doctrine"] = QPixmap("./resources/ui/misc/blue-sam.png")
    ICONS["PassTurn"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/hourglass.png"
    )
    ICONS["Proceed"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/proceed.png"
    )
    ICONS["Settings"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/settings.png"
    )
    ICONS["Statistics"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/statistics.png"
    )
    ICONS["Ordnance"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/ordnance_icon.png"
    )

    ICONS["Generator"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/generator.png"
    )
    ICONS["Mission Generation"] = ICONS["Generator"]
    ICONS["Missile"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/missile.png"
    )
    ICONS["Difficulty"] = ICONS["Missile"]
    ICONS["Cheat"] = QPixmap("./resources/ui/misc/" + get_theme_icons() + "/cheat.png")
    ICONS["Plugins"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/plugins.png"
    )
    ICONS["PluginsOptions"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/pluginsoptions.png"
    )
    ICONS["Notes"] = QPixmap("./resources/ui/misc/" + get_theme_icons() + "/notes.png")
    ICONS["Reload"] = QPixmap(
        "./resources/ui/misc/" + get_theme_icons() + "/reload.png"
    )

    ICONS["TaskCAS"] = QPixmap("./resources/ui/tasks/cas.png")
    ICONS["TaskCAP"] = QPixmap("./resources/ui/tasks/cap.png")
    ICONS["TaskSEAD"] = QPixmap("./resources/ui/tasks/sead.png")
    ICONS["TaskEmpty"] = QPixmap("./resources/ui/tasks/empty.png")

    """
    Weather Icons
    """
    ICONS["Weather_winds"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/winds.png"
    )
    ICONS["Weather_day-clear"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/day-clear.png"
    )
    ICONS["Weather_day-cloudy-fog"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/day-cloudy-fog.png"
    )
    ICONS["Weather_day-fog"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/day-fog.png"
    )
    ICONS["Weather_day-partly-cloudy"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/day-partly-cloudy.png"
    )
    ICONS["Weather_day-rain"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/day-rain.png"
    )
    ICONS["Weather_day-thunderstorm"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/day-thunderstorm.png"
    )
    ICONS["Weather_day-totally-cloud"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/day-totally-cloud.png"
    )
    ICONS["Weather_night-clear"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/night-clear.png"
    )
    ICONS["Weather_night-cloudy-fog"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/night-cloudy-fog.png"
    )
    ICONS["Weather_night-fog"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/night-fog.png"
    )
    ICONS["Weather_night-partly-cloudy"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/night-partly-cloudy.png"
    )
    ICONS["Weather_night-rain"] = QPixmap(
        "./resources/ui/conditions/" + get_theme_icons() + "/weather/night-rain.png"
    )
    ICONS["Weather_night-thunderstorm"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/night-thunderstorm.png"
    )
    ICONS["Weather_night-totally-cloud"] = QPixmap(
        "./resources/ui/conditions/"
        + get_theme_icons()
        + "/weather/night-totally-cloud.png"
    )

    ICONS["heading"] = QPixmap("./resources/ui/misc/heading.png")
    ICONS["blue-sam"] = QPixmap("./resources/ui/misc/blue-sam.png")


EVENT_ICONS: Dict[str, QPixmap] = {}


def load_event_icons():
    for image in os.listdir("./resources/ui/events/"):
        if image.endswith(".PNG"):
            EVENT_ICONS[image[:-4]] = QPixmap(
                os.path.join("./resources/ui/events/", image)
            )


def load_aircraft_icons():
    for aircraft in os.listdir("./resources/ui/units/aircrafts/icons/"):
        if aircraft.endswith(".jpg"):
            AIRCRAFT_ICONS[aircraft[:-7]] = QPixmap(
                os.path.join("./resources/ui/units/aircrafts/icons/", aircraft)
            )
    AIRCRAFT_ICONS["F-16C_50"] = AIRCRAFT_ICONS["F-16C"]
    AIRCRAFT_ICONS["F-16A MLU"] = AIRCRAFT_ICONS["F-16A"]
    AIRCRAFT_ICONS["FA-18C_hornet"] = AIRCRAFT_ICONS["FA-18C"]
    AIRCRAFT_ICONS["A-10C_2"] = AIRCRAFT_ICONS["A-10C"]
    f1_refuel = ["Mirage-F1CT", "Mirage-F1EE", "Mirage-F1M-EE", "Mirage-F1EQ"]
    for f1 in f1_refuel:
        AIRCRAFT_ICONS[f1] = AIRCRAFT_ICONS["Mirage-F1C-200"]
    AIRCRAFT_ICONS["Mirage-F1M-CE"] = AIRCRAFT_ICONS["Mirage-F1CE"]
    AIRCRAFT_ICONS["F-15ESE"] = AIRCRAFT_ICONS["F-15E"]
    AIRCRAFT_ICONS["Su-30MKA-AG"] = AIRCRAFT_ICONS["Su-30MKA"]
    AIRCRAFT_ICONS["Su-30MKI-AG"] = AIRCRAFT_ICONS["Su-30MKI"]
    AIRCRAFT_ICONS["Su-30MKM-AG"] = AIRCRAFT_ICONS["Su-30MKM"]
    AIRCRAFT_ICONS["Su-30SM-AG"] = AIRCRAFT_ICONS["Su-30SM"]
    AIRCRAFT_ICONS["F-5E-3_FC"] = AIRCRAFT_ICONS["F-5E-3"]
    AIRCRAFT_ICONS["F-86F_FC"] = AIRCRAFT_ICONS["F-86F Sabre"]
    AIRCRAFT_ICONS["MiG-15bis_FC"] = AIRCRAFT_ICONS["MiG-15bis"]
    AIRCRAFT_ICONS["CH_Ka52"] = AIRCRAFT_ICONS["CH_K"]
    AIRCRAFT_ICONS["CH_Ka52K"] = AIRCRAFT_ICONS["CH_Ka"]
    AIRCRAFT_ICONS["CH_Mi28N"] = AIRCRAFT_ICONS["CH_Mi"]
    AIRCRAFT_ICONS["CH_Tu-95MSM"] = AIRCRAFT_ICONS["CH_Tu-95"]
    AIRCRAFT_ICONS["CH_Tu-160M2"] = AIRCRAFT_ICONS["CH_Tu-16"]
    AIRCRAFT_ICONS["B-21"] = AIRCRAFT_ICONS["B"]


def load_vehicle_icons():
    for vehicle in os.listdir("./resources/ui/units/vehicles/icons/"):
        if vehicle.endswith(".jpg"):
            VEHICLES_ICONS[vehicle[:-7]] = QPixmap(
                os.path.join("./resources/ui/units/vehicles/icons/", vehicle)
            )
