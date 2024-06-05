from dataclasses import dataclass, fields
import enum
import functools
from typing import Optional

from selenium import webdriver
import requests


# TODO: Check for better datatype: https://stackoverflow.com/q/31537316/7410886
class Position(enum.Enum):
    GOALKEEPER = 0
    # TW = 0
    # DEFENSE = 1
    DEFENDER = 1
    # AW = 1
    # MIDFIELD = 2
    MIDFIELDER = 2
    # MF = 2
    # OFFENSE = 3
    FORWARD = 3
    # ST = 3

    def __lt__(self, other):
        return self.value < other.value


@dataclass(unsafe_hash=True)
class Player:
    """Represents a player with real as well as game stats."""

    name: str
    nationality: Optional[str] = None
    id_transfermarkt_de: Optional[int] = None
    market_value: Optional[int] = None
    ingame_position: Optional[Position] = None
    ingame_value: Optional[int] = None

    def first_name(self, special_chars=True):
        name_parts = self.name.split(" ", 1)
        if len(name_parts) == 2:
            first_name = name_parts[0].lower()
        else:
            first_name = None
        if not special_chars:
            first_name = idfy(first_name)
        return first_name

    def family_name(self, special_chars=True):
        name_parts = self.name.split(" ", 1)
        if len(name_parts) == 2:
            family_name = name_parts[1].lower()
        else:
            family_name = self.name.lower()
        if not special_chars:
            family_name = idfy(family_name)
        return family_name

    def __add__(self, other):
        for field in fields(Player)[
            1:
        ]:  # Name has to be assigned at both. Take the name of the first player.
            value_self = getattr(self, field.name)
            value_other = getattr(other, field.name)
            if value_self is not None and value_other is not None:
                raise ValueError(
                    f"Can't add players. Too many values for {field.name}: {self} + {other}."
                )

        return Player(
            self.name,
            self.nationality if self.nationality is not None else other.nationality,
            (
                self.id_transfermarkt_de
                if self.id_transfermarkt_de is not None
                else other.id_transfermarkt_de
            ),
            self.market_value if self.market_value is not None else other.market_value,
            (
                self.ingame_position
                if self.ingame_position is not None
                else other.ingame_position
            ),
            self.ingame_value if self.ingame_value is not None else other.ingame_value,
        )


def with_session(func):
    """Convenience decorator to save one intendation level."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Custom user agent"})
            return func(session, *args, **kwargs)

    return wrapper


def with_driver(func):
    """Convenience decorator to save one intendation level."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        with webdriver.Chrome(options=options) as driver:
            return func(driver, *args, **kwargs)

    return wrapper


def idfy(name: str) -> str:
    """Replace special characters to match player names from different sources."""
    replacements = {
        "ä": "ae",
        "æ": "ae",
        "á": "a",
        "ą": "a",
        "ć": "c",
        "č": "c",
        "ç": "c",
        "ć": "c",
        "ď": "d",
        "é": "e",
        "ę": "e",
        "ë": "e",
        "ğ": "g",
        "ı": "i",
        "í": "i",
        "ï": "i",
        "ł": "l",
        "ń": "n",
        "ň": "n",
        "ñ": "n",
        "ö": "oe",
        "ø": "oe",
        "ó": "o",
        "ô": "o",
        "ß": "ss",
        "š": "s",
        "ş": "s",
        "ś": "s",
        "ü": "ue",
        "ú": "u",
        "ý": "y",
        "ź": "z",
        "ž": "z",
    }
    name_id = name.lower()
    for replacement in replacements.items():
        name_id = name_id.replace(*replacement)
    return name_id
