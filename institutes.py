"""Met Institute constants shared between 🌤️_Assessment.py and pages/*.py."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Institute:
    short: str  # condensed label for the sidebar (selector, badges, captions)
    long: str  # full name for the main page (headers, tables, chart legends)


INSTITUTES: dict[str, Institute] = {
    "MetNo": Institute(short="MetNo", long="Norwegian Meteorological Institute"),
    "MetEireann": Institute(short="Met Éireann", long="The Irish Meteorological Service"),
    "KNMI": Institute(short="KNMI", long="Royal Netherlands Meteorological Institute"),
    "UKMO": Institute(short="UK Met Office", long="The United Kingdom's National Meteorological Service"),
}
