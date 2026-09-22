from tools.flight_tool import parse_route, resolve_location_to_iata


def test_resolve_city_name():
    assert resolve_location_to_iata("Tokyo") == "NRT"
    assert resolve_location_to_iata("new delhi") == "DEL"


def test_resolve_country_name():
    assert resolve_location_to_iata("Bangladesh") == "DAC"
    assert resolve_location_to_iata("Japan") == "NRT"


def test_resolve_direct_iata_code():
    assert resolve_location_to_iata("NRT") == "NRT"
    assert resolve_location_to_iata("nrt") == "NRT"


def test_resolve_unknown_location_returns_none():
    assert resolve_location_to_iata("Nowhereland") is None
    assert resolve_location_to_iata("") is None
    assert resolve_location_to_iata(None) is None


def test_parse_route_from_to():
    assert parse_route("Plan a 7 day trip from Delhi to Tokyo") == ("DEL", "NRT")


def test_parse_route_to_from():
    assert parse_route("flights to Tokyo from Delhi") == ("DEL", "NRT")


def test_parse_route_direct_iata_codes():
    assert parse_route("DAC to NRT flights") == ("DAC", "NRT")


def test_parse_route_global_keyword():
    assert parse_route("show me all flights worldwide") == (None, None)


def test_parse_route_destination_only_matches_to_pattern():
    # Documented contract: "to X" with no explicit origin resolves to
    # (None, arr_iata) — "all flights to X" — not a default-origin guess.
    assert parse_route("Plan a trip to Tokyo") == (None, "NRT")


def test_parse_route_bare_mention_uses_default_origin():
    # Only the no-keyword-match fallback (a single bare location mention)
    # fills in DEFAULT_ORIGIN_IATA.
    dep, arr = parse_route("Tokyo")
    assert arr == "NRT"
    assert dep  # falls back to DEFAULT_ORIGIN_IATA
