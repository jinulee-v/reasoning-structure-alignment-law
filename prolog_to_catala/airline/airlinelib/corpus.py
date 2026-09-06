"""The pristine corpus, read into world models.

An airline case is one sentence in one grammar, and all 300 parse: a
passenger, a cabin, an origin, a destination, a numbered list of items with
dimensions and weight, and a ticket price.  That sentence, typed, is the world
model --- there is nothing to ground in the sense SARA's `grounding.py` means,
because the case text is already structured.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from . import paths

CABINS = ["Basic Economy", "Main Cabin", "Main Plus", "Premium Economy",
          "Business", "First"]

#: city as the cases spell it -> the identifier used in Prolog and in Catala
CITY_ATOM = {"Washington D.C.": "washington_dc", "Hong Kong": "hong_kong",
             "Bogotá": "bogota"}
CITY_CATALA = {"Washington D.C.": "WashingtonDC", "Hong Kong": "HongKongCity",
               "Bogotá": "Bogota", "Port-au-Prince": "PortAuPrince",
               "Rio de Janeiro": "RioDeJaneiro"}

CABIN_ATOM = {"Basic Economy": "basic_economy", "Main Cabin": "main_cabin",
              "Main Plus": "main_plus", "Premium Economy": "premium_economy",
              "Business": "business", "First": "first"}
CABIN_CATALA = {"Basic Economy": "BasicEconomy", "Main Cabin": "MainCabin",
                "Main Plus": "MainPlus", "Premium Economy": "PremiumEconomy",
                "Business": "Business", "First": "First"}


def city_atom(c: str) -> str:
    return CITY_ATOM.get(c, c.lower().replace(" ", "_").replace("-", "_"))


def city_catala(c: str) -> str:
    return CITY_CATALA.get(c, c.replace(" ", "").replace("-", ""))


def check_gazetteer() -> None:
    """Every city the corpus names must be a case of `AirlineWorld.City`.

    The default spelling rule --- drop spaces and hyphens --- is right for
    twenty of the twenty-one multi-word cities and wrong for "Rio de Janeiro",
    whose enumeration case capitalises the particle.  A city that does not map
    produces a Catala file that fails to compile, which the differential runner
    reports as 562 disagreeing cases with no value on the Catala side, rather
    than as the one-line emitter bug it is.  So the mapping is checked against
    the port's own declaration before anything is emitted.
    """
    src = (paths.CATALA_PROJECT / "AirlineWorld.catala_en").read_text()
    block = src.split("declaration enumeration City:", 1)[1].split("```", 1)[0]
    declared = set(re.findall(r"^\s*--\s*(\w+)", block, re.M))
    wrong = {c: city_catala(c) for c in CITY_ATOM_ALL if city_catala(c) not in declared}
    if wrong:
        raise RuntimeError(
            "these cities do not name a case of AirlineWorld.City: "
            + ", ".join(f"{k!r} -> {v}" for k, v in sorted(wrong.items())))


#: item kind, as the Prolog atom and the Catala enumeration case.  The fee
#: tables price `ordinary_bag`; the rest exist for the rules that exempt them
#: or give them their own limit.
ITEM_KINDS = {
    "ordinary_bag": "OrdinaryBag",
    "soft_sided_garment_bag": "SoftSidedGarmentBag",
    "diaper_bag": "DiaperBag",
    "breast_pump": "BreastPump",
    "breast_milk_cooler": "BreastMilkCooler",
    "child_safety_seat": "ChildSafetySeat",
    "stroller": "Stroller",
    "medical_or_mobility_device": "MedicalOrMobilityDevice",
}

#: AAdvantage / oneworld tier, likewise
STATUSES = {
    "no_status": "NoStatus", "gold": "Gold", "platinum": "Platinum",
    "platinum_pro": "PlatinumPro", "executive_platinum": "ExecutivePlatinum",
}
MILITARY = {
    "not_military": "NotMilitary", "on_orders": "OnOrders",
    "personal_travel": "PersonalTravel",
}


@dataclass
class Item:
    length: int
    width: int
    height: int
    weight: int
    #: everything the corpus can express is an ordinary bag; the other kinds
    #: exist only for the rules no case can state.  DEVIATIONS C1.
    kind: str = "ordinary_bag"

    @property
    def size_sum(self) -> int:
        return self.length + self.width + self.height


@dataclass
class Trip:
    """An airline world model."""
    id: str
    origin: str
    destination: str
    cabin: str
    ticket: int
    items: list
    #: Complimentary Bags attributes, each defaulting to "no" so a world that
    #: does not mention them behaves as it did before the section was written.
    status_at_ticketing: str = "no_status"
    status_at_checkin: str = "no_status"
    cardmember: bool = False
    military: str = "not_military"
    flagship: bool = False
    children: int = 0
    #: the reference program's answer, where the world came from a seed case
    label: int | None = None
    #: `seed` or the name of the generator that produced it
    method: str = "seed"
    hard: bool = False

    def to_json(self) -> dict:
        d = asdict(self)
        d["items"] = [asdict(i) for i in self.items]
        return d

    @staticmethod
    def from_json(d: dict) -> "Trip":
        d = dict(d)
        d["items"] = [Item(**i) for i in d["items"]]
        return Trip(**d)


_TRIP_RE = re.compile(
    r"^(?P<name>\w+) is an? (?P<cabin>[\w ]+?) Class passenger flying from "
    r"(?P<origin>[\w .'-]+?) to (?P<dest>[\w .'-]+?) with the following items: "
    r"(?P<items>.*?)\s*(?P=name)'s flight ticket is \$(?P<ticket>\d+)\.$", re.S)
_ITEM_RE = re.compile(
    r"\d+\.\s*An? ([\w -]+?):\s*(\d+) x (\d+) x (\d+) inches,\s*(\d+) lbs")


#: filled in by `load_airline`; the cities the corpus actually names.
CITY_ATOM_ALL: set = set()


def load_airline() -> list:
    """All 300 airline cases, as world models."""
    trips = []
    for f in sorted((paths.AIRLINE_RAW / "meta").glob("*.json")):
        m = json.loads(f.read_text())
        h = _TRIP_RE.match(m["text"].strip())
        if h is None:
            raise ValueError(f"{m['id']}: case text does not parse")
        items = [Item(int(a), int(b), int(c), int(w))
                 for _, a, b, c, w in _ITEM_RE.findall(h.group("items"))]
        trips.append(Trip(id=m["id"], origin=h.group("origin"), destination=h.group("dest"),
                          cabin=h.group("cabin"), ticket=int(h.group("ticket")),
                          items=items, label=int(m["label"]), hard=bool(m["hard"])))
        CITY_ATOM_ALL.update({h.group("origin"), h.group("dest")})
    check_gazetteer()
    return trips


def reference_program(domain: str, case_id: str) -> str:
    return (paths.RAW / domain / "cases" / f"{case_id}.pl").read_text()
