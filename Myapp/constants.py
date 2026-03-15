NC_CITY_DISTRICT_MAP = {
    "Lefko\u015fa": [
        "Hamitk\u00f6y",
        "Kumsal",
        "Ortak\u00f6y",
        "G\u00f6nyeli",
        "Metehan",
    ],
    "Girne": [
        "Karakum",
        "\u00d6zank\u00f6y",
        "\u00c7atalk\u00f6y",
        "Alsancak",
        "Lapta",
    ],
    "Gazima\u011fusa": [
        "Suriçi",
        "Tuzla",
        "Karakol",
        "Do\u011fu Akdeniz",
        "Mara\u015f",
    ],
    "G\u00fczelyurt": [
        "Merkez",
        "Bostanc\u0131",
        "Yayla",
        "Ayd\u0131nk\u00f6y",
    ],
    "\u0130skele": [
        "Merkez",
        "Long Beach",
        "Bo\u011faz",
        "Mehmet\u00e7ik",
    ],
    "Lefke": [
        "Merkez",
        "Gemikona\u011f\u0131",
        "Yedidalga",
        "Cengizk\u00f6y",
    ],
}

NC_CITY_CHOICES = [(city, city) for city in NC_CITY_DISTRICT_MAP.keys()]

_all_districts = []
for districts in NC_CITY_DISTRICT_MAP.values():
    for district in districts:
        if district not in _all_districts:
            _all_districts.append(district)

NC_DISTRICT_CHOICES = [(district, district) for district in _all_districts]
