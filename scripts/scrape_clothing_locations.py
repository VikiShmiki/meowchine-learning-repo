"""Refresh bounded public source facts; never automatically publish new map destinations.

Coordinates in sites.json are separately reviewed OSM matches. A changed source list
fails closed and needs review instead of geocoding a street centre as a collection bin.
No full copyrighted page, cookies, donor data or personal information is retained.
"""

import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx

DIRECTORY = Path(__file__).resolve().parents[1] / "data/infrastructure/clothes-2026-09-22"
SOURCE = "https://ckgs.org.mk/novosti/crven-krst-na-grad-skopje-doniraj-obleka-podari-nadezh/"
# Identifiers are reviewed matches, not fuzzy geocoding guesses.
VENUES = {
    "Карпош": ("clothes-karpos-red-cross", "Red Cross Karpos", 2, None),
    "Даре": ("clothes-dare-dzambaz", "Dare Dzambaz", 2, None),
    "Гази Баба": (
        "clothes-gazi-baba",
        "Red Cross Gazi Baba",
        1,
        "Published Anton Popov 26 conflicts with branch contact address "
        "Blagoja Stefkovski bb; collection position unresolved.",
    ),
    "Чаир": (
        "clothes-chair",
        "Red Cross Chair",
        1,
        "Pavle Ilik 1 is published, but no reliable exact venue coordinate was found.",
    ),
    "Кисела Вода": ("clothes-kisela-voda", "Kisela Voda municipality", 1, None),
    "Градско собрание": ("clothes-city-hall", "Skopje City Hall", 1, None),
    "Момин Поток": (
        "clothes-momin-potok",
        "Momin Potok warehouse",
        None,
        "Donation warehouse entrance unresolved; a neighbourhood or shelter pin "
        "is not sufficient evidence.",
    ),
    "Копче": ("clothes-kopche", "Kopche", None, None),
}


class ListItems(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.stack.append([])

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].append(data)

    def handle_endtag(self, tag):
        if tag == "li" and self.stack:
            self.items.append(" ".join(" ".join(self.stack.pop()).split()))


def extract(html: str) -> list[dict]:
    parser = ListItems()
    parser.feed(html)
    rows = []
    for token, (identifier, name, expected_count, hold) in VENUES.items():
        matches = [
            line
            for line in parser.items
            if token in line and ("контејнер" in line or "секој работен ден" in line)
        ]
        if len(matches) != 1:
            raise ValueError(f"Source structure/list changed for {name}; review required")
        count_match = re.match(r"(\d+)\s+контејнер", matches[0])
        count = int(count_match[1]) if count_match else None
        if count != expected_count:
            raise ValueError(f"Container count changed for {name}; review required")
        rows.append(
            {
                "id": identifier,
                "name": name,
                "reported_containers": count,
                "routing_status": "held" if hold else "mapped_venue",
                "hold_reason": hold,
            }
        )
    return rows


def main():
    response = httpx.get(
        SOURCE,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "SmartRecyclingResearch/0.1"},
    )
    response.raise_for_status()
    rows = extract(response.text)
    catalog = json.loads((DIRECTORY / "sites.json").read_text(encoding="utf-8"))
    mapped = {row["id"]: row for row in rows if row["routing_status"] == "mapped_venue"}
    if {row["id"] for row in catalog["sites"]} != mapped.keys():
        raise ValueError("Reviewed map catalog and published venue list disagree")
    for site in catalog["sites"]:
        if site["reported_containers"] != mapped[site["id"]]["reported_containers"]:
            raise ValueError("Reviewed container counts disagree")
    report = {
        "source": SOURCE,
        "published_on": "2026-04-20",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_sha256": hashlib.sha256(response.content).hexdigest(),
        "documented_venues": len(rows),
        "reported_containers": sum(row["reported_containers"] or 0 for row in rows),
        "mapped_venues": len(mapped),
        "venues": rows,
        "older_unconfirmed_leads": [
            "Novo Lisice / Lisa Centre",
            "Avtokomanda Square",
            "Skopje City Mall",
        ],
        "older_source": "https://api.ckrm.org.mk/doniraj-obleka/",
        "excluded": "Older leads are absent from the 2026 list. H&M Skopje collection "
        "participation was not verified. One-day campaigns are not permanent sites.",
    }
    raw = (DIRECTORY / "sites.json").read_text(encoding="utf-8")
    manifest = {
        "version": catalog["version"],
        "source": SOURCE,
        "sites_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "mapped_venues": len(mapped),
        "documented_venues": len(rows),
        "coordinate_license": "https://www.openstreetmap.org/copyright",
        "counting": "One app collection-point record per venue, not one per physical container.",
    }
    for filename, value in (("research.json", report), ("manifest.json", manifest)):
        (DIRECTORY / filename).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(
        f"Scraped {len(rows)} documented venues; {len(mapped)} reviewed map locations; "
        f"{report['reported_containers']} containers at 6 venues, plus 2 staffed drop-offs."
    )


if __name__ == "__main__":
    main()
