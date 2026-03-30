from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
import requests

from conftest import load_module

MODULE = load_module("openstreetmap/query.py", "openstreetmap_query")
SCRIPT_PATH = Path(__file__).with_name("query.py")


class FakeStream:
    def __init__(self) -> None:
        self.encodings: list[str] = []

    def reconfigure(self, *, encoding: str) -> None:
        self.encodings.append(encoding)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        ok: bool = True,
        url: str = "https://example.com/api",
        headers: dict[str, str] | None = None,
        json_payload: object | None = None,
        text_payload: str = "",
    ) -> None:
        self.status_code = status_code
        self.ok = ok
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self._json_payload = json_payload
        self.text = text_payload

    def json(self) -> object:
        if self._json_payload is None:
            raise ValueError("not json")
        return self._json_payload

    def raise_for_status(self) -> None:
        if self.ok:
            return
        raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(
        self,
        *,
        get_responses: list[FakeResponse] | None = None,
        post_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_calls: list[tuple[str, dict[str, object]]] = []
        self.post_calls: list[tuple[str, dict[str, object]]] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.get_calls.append((url, kwargs))
        if not self.get_responses:
            raise AssertionError("No fake GET response configured")
        return self.get_responses.pop(0)

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.post_calls.append((url, kwargs))
        if not self.post_responses:
            raise AssertionError("No fake POST response configured")
        return self.post_responses.pop(0)


class FakeClient:
    def __init__(
        self,
        *,
        nominatim_responses: list[dict[str, object]] | None = None,
        overpass_responses: list[dict[str, object]] | None = None,
        public_nominatim: bool = False,
    ) -> None:
        self.nominatim_base_url = "https://nominatim.example.com"
        self.overpass_url = "https://overpass.example.com/api/interpreter"
        self._public_nominatim = public_nominatim
        self.nominatim_responses = list(nominatim_responses or [])
        self.overpass_responses = list(overpass_responses or [])
        self.nominatim_calls: list[tuple[str, dict[str, object]]] = []
        self.overpass_calls: list[str] = []

    def is_public_nominatim(self) -> bool:
        return self._public_nominatim

    def nominatim_request(self, path: str, params: dict[str, object]) -> dict[str, object]:
        self.nominatim_calls.append((path, params))
        if not self.nominatim_responses:
            raise AssertionError("No fake Nominatim response configured")
        return self.nominatim_responses.pop(0)

    def overpass_request(self, query: str) -> dict[str, object]:
        self.overpass_calls.append(query)
        if not self.overpass_responses:
            raise AssertionError("No fake Overpass response configured")
        return self.overpass_responses.pop(0)


def make_service_response(
    data: object,
    *,
    url: str = "https://example.com/api",
    status: int = 200,
    content_type: str = "application/json",
) -> dict[str, object]:
    return {
        "url": url,
        "status": status,
        "content_type": content_type,
        "data": data,
    }


def make_nominatim_options() -> dict[str, object]:
    return {
        "format": "jsonv2",
        "addressdetails": True,
        "extratags": False,
        "namedetails": False,
        "entrances": False,
        "accept_language": None,
        "polygon_format": None,
        "polygon_threshold": None,
    }


def make_search_args(**overrides: object) -> SimpleNamespace:
    defaults = make_nominatim_options()
    defaults.update(
        {
            "query": "Brandenburger Tor, Berlin",
            "amenity": None,
            "street": None,
            "city": None,
            "county": None,
            "state": None,
            "country": None,
            "postalcode": None,
            "limit": 5,
            "countrycode": None,
            "layer": None,
            "feature_type": None,
            "exclude_place_id": None,
            "viewbox": None,
            "bounded": False,
            "dedupe": True,
            "expected_lat": None,
            "expected_lon": None,
            "max_distance_meters": None,
            "expected_countrycode": None,
        }
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_reverse_args(**overrides: object) -> SimpleNamespace:
    defaults = make_nominatim_options()
    defaults.update({"lat": 52.5163, "lon": 13.3777, "zoom": 18, "layer": None})
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_lookup_args(**overrides: object) -> SimpleNamespace:
    defaults = make_nominatim_options()
    defaults.update({"osm_ids": ["W50637691"]})
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_details_args(**overrides: object) -> SimpleNamespace:
    defaults = {
        "place_id": None,
        "osm_type": None,
        "osm_id": None,
        "class_name": None,
        "addressdetails": False,
        "keywords": False,
        "linkedplaces": True,
        "hierarchy": False,
        "group_hierarchy": False,
        "entrances": False,
        "polygon_geojson": False,
        "accept_language": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_boundaries_args(**overrides: object) -> SimpleNamespace:
    defaults = {
        "lat": 52.5163,
        "lon": 13.3777,
        "admin_level": None,
        "overpass_timeout": 25,
        "max_preview_results": 20,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_nearby_args(**overrides: object) -> SimpleNamespace:
    defaults = {
        "lat": 52.5163,
        "lon": 13.3777,
        "radius": 150.0,
        "tag": ["tourism=attraction"],
        "overpass_timeout": 25,
        "max_preview_results": 20,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_overpass_args(**overrides: object) -> SimpleNamespace:
    defaults = {
        "query": "node[amenity=cafe](50,8,50.1,8.1);out;",
        "file": None,
        "max_preview_elements": 20,
        "max_body_chars": 12000,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_client_args(**overrides: object) -> SimpleNamespace:
    defaults = {
        "nominatim_base_url": "https://nominatim.example.com/",
        "overpass_url": "https://overpass.example.com/api/interpreter/",
        "user_agent": " test-agent ",
        "email": "maps@example.com",
        "timeout": 30,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_stdio_and_basic_helpers_cover_url_timeout_and_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_stdout = FakeStream()
    fake_stderr = FakeStream()
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)
    MODULE.configure_stdio()

    assert fake_stdout.encodings == ["utf-8"]
    assert fake_stderr.encodings == ["utf-8"]
    assert MODULE.normalize_base_url(" https://example.com/ ") == "https://example.com"
    assert MODULE.get_env_int("MISSING_TIMEOUT", 30) == 30

    monkeypatch.setenv("OSM_TIMEOUT", "   ")
    assert MODULE.get_env_int("OSM_TIMEOUT", 30) == 30

    monkeypatch.setenv("OSM_TIMEOUT", " 45 ")
    assert MODULE.get_env_int("OSM_TIMEOUT", 30) == 45

    monkeypatch.setenv("OSM_TIMEOUT", "bad")
    with pytest.raises(ValueError):
        MODULE.get_env_int("OSM_TIMEOUT", 30)

    with pytest.raises(ValueError):
        MODULE.normalize_base_url("   ")

    preview, truncated = MODULE.truncate_text("abcdef", 3)
    assert truncated is True
    assert preview.startswith("abc")


def test_raise_for_status_and_response_parsing_handle_json_and_text() -> None:
    assert MODULE.parse_response_content(FakeResponse(json_payload={"ok": True})) == {"ok": True}
    assert MODULE.parse_response_content(FakeResponse(json_payload=None, text_payload="plain")) == "plain"

    with pytest.raises(RuntimeError, match="HTTP 503"):
        MODULE.raise_for_status_with_context(
            FakeResponse(status_code=503, ok=False, text_payload="service unavailable")
        )

    with pytest.raises(RuntimeError, match="HTTP 500"):
        MODULE.raise_for_status_with_context(FakeResponse(status_code=500, ok=False, text_payload=""))


def test_openstreetmap_client_waits_for_public_nominatim_and_injects_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeSession(get_responses=[FakeResponse(json_payload={"ok": True})])
    client = MODULE.OpenStreetMapClient(
        "https://nominatim.openstreetmap.org",
        "https://overpass.example.com/api/interpreter",
        "skill-tests",
        "maps@example.com",
        12,
    )
    client.session = fake_session
    client._last_nominatim_request_at = 100.0
    sleep_calls: list[float] = []
    moments = iter([100.25, 101.0])
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: next(moments))
    monkeypatch.setattr(MODULE.time, "sleep", lambda value: sleep_calls.append(value))

    response = client.nominatim_request("/status", {"format": "json"})

    assert client.is_public_nominatim() is True
    assert sleep_calls[0] == pytest.approx(0.75)
    assert fake_session.get_calls[0][0] == "https://nominatim.openstreetmap.org/status"
    assert fake_session.get_calls[0][1]["params"]["email"] == "maps@example.com"
    assert response["data"] == {"ok": True}


def test_openstreetmap_client_private_wait_paths_and_overpass_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    private_client = MODULE.OpenStreetMapClient(
        "https://nominatim.example.com",
        "https://overpass.example.com/api/interpreter",
        "skill-tests",
        None,
        12,
    )
    private_client.maybe_wait_for_public_nominatim()
    assert sleep_calls == []

    public_client = MODULE.OpenStreetMapClient(
        "https://nominatim.openstreetmap.org",
        "https://overpass.example.com/api/interpreter",
        "skill-tests",
        None,
        12,
    )
    public_client._last_nominatim_request_at = 100.0
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: 102.0)
    public_client.maybe_wait_for_public_nominatim()
    assert sleep_calls == []

    fake_session = FakeSession(
        post_responses=[FakeResponse(json_payload={"elements": [{"id": 1}]}, url="https://overpass.example.com/api/interpreter")]
    )
    private_client.session = fake_session

    response = private_client.overpass_request("node[id=1];out;")

    assert fake_session.post_calls[0][0] == "https://overpass.example.com/api/interpreter"
    assert fake_session.post_calls[0][1]["data"] == {"data": "node[id=1];out;"}
    assert response["data"] == {"elements": [{"id": 1}]}


def test_build_parser_accepts_common_options_before_and_after_subcommand() -> None:
    parser = MODULE.build_parser()

    args_before = parser.parse_args(["--timeout", "11", "status"])
    args_after = parser.parse_args(
        ["status", "--timeout", "7", "--nominatim-base-url", "https://nominatim.example.com"]
    )

    assert args_before.command == "status"
    assert args_before.timeout == 11
    assert args_after.timeout == 7
    assert args_after.nominatim_base_url == "https://nominatim.example.com"


def test_build_search_params_support_free_form_and_structured_queries() -> None:
    free_form_args = make_search_args(
        countrycode=["DE", " AT "],
        layer=["poi", "address"],
        feature_type="city",
        exclude_place_id=["10", "20"],
        viewbox="13.0, 52.0, 14.0, 53.0",
        bounded=True,
        dedupe=False,
    )
    params, query, structured = MODULE.build_search_params(free_form_args)

    assert query == "Brandenburger Tor, Berlin"
    assert structured == {}
    assert params["q"] == "Brandenburger Tor, Berlin"
    assert params["countrycodes"] == "de,at"
    assert params["layer"] == "poi,address"
    assert params["featureType"] == "city"
    assert params["exclude_place_ids"] == "10,20"
    assert params["viewbox"] == "13.0,52.0,14.0,53.0"
    assert params["bounded"] == 1
    assert params["dedupe"] == 0

    structured_args = make_search_args(query=None, city="Berlin", country="Germany")
    structured_params, structured_query, structured_fields = MODULE.build_search_params(structured_args)
    assert structured_query is None
    assert structured_fields == {"city": "Berlin", "country": "Germany"}
    assert "q" not in structured_params


def test_build_search_params_reject_invalid_combinations() -> None:
    with pytest.raises(ValueError):
        MODULE.build_search_params(make_search_args(city="Berlin"))

    with pytest.raises(ValueError):
        MODULE.build_search_params(make_search_args(query=None))

    with pytest.raises(ValueError):
        MODULE.build_search_params(make_search_args(limit=0))

    with pytest.raises(ValueError):
        MODULE.build_search_params(make_search_args(viewbox="13,52,14"))


def test_reverse_lookup_and_details_helpers_validate_ranges_and_ids() -> None:
    reverse_params = MODULE.build_reverse_params(make_reverse_args(layer=["address", "poi"], zoom=10))
    assert reverse_params["zoom"] == 10
    assert reverse_params["layer"] == "address,poi"

    with pytest.raises(ValueError):
        MODULE.build_reverse_params(make_reverse_args(zoom=19))

    assert MODULE.normalize_osm_ids(["w1,n2", "R3"]) == ["W1", "N2", "R3"]

    with pytest.raises(ValueError):
        MODULE.normalize_osm_ids(["invalid"])

    with pytest.raises(ValueError):
        MODULE.normalize_osm_ids([*(f"W{index}" for index in range(1, 52))])

    lookup_params, osm_ids = MODULE.build_lookup_params(make_lookup_args(osm_ids=["W10", "n20,r30"]))
    assert osm_ids == ["W10", "N20", "R30"]
    assert lookup_params["osm_ids"] == "W10,N20,R30"

    assert MODULE.build_details_params(make_details_args(place_id=42))["place_id"] == 42
    relation_details = MODULE.build_details_params(make_details_args(osm_type="relation", osm_id=99))
    assert relation_details["osmtype"] == "R"
    assert relation_details["osmid"] == 99

    assert MODULE.build_polygon_params(make_search_args(polygon_format="geojson", polygon_threshold=0.25)) == {
        "polygon_geojson": 1,
        "polygon_threshold": 0.25,
    }

    with pytest.raises(ValueError):
        MODULE.normalize_osm_id_token(" ")

    with pytest.raises(ValueError):
        MODULE.normalize_osm_id_token("Wabc")

    with pytest.raises(ValueError):
        MODULE.normalize_osm_ids([", ,"])

    assert MODULE.normalize_details_osm_type(None) is None

    with pytest.raises(ValueError):
        MODULE.build_details_params(make_details_args(osm_id=7))

    with pytest.raises(ValueError):
        MODULE.build_details_params(make_details_args(osm_type="way"))

    details = MODULE.build_details_params(
        make_details_args(
            osm_type="way",
            osm_id=7,
            polygon_geojson=True,
            accept_language="en,de",
            class_name="highway",
        )
    )
    assert details["polygon_geojson"] == 1
    assert details["accept-language"] == "en,de"
    assert details["class"] == "highway"

    with pytest.raises(ValueError):
        MODULE.build_details_params(make_details_args(osm_type="planet", osm_id=7))

    with pytest.raises(ValueError):
        MODULE.build_details_params(make_details_args())

    with pytest.raises(ValueError):
        MODULE.build_details_params(make_details_args(place_id=42, osm_type="way", osm_id=9))


def test_overpass_query_helpers_validate_tags_and_sources(tmp_path: Path) -> None:
    tag_filters = MODULE.build_tag_filters([r'name=Brandenburger "Tor"', r'path=C:\maps'])
    assert '\\"Tor\\"' in tag_filters
    assert 'C:\\\\maps' in tag_filters

    with pytest.raises(ValueError):
        MODULE.build_tag_filters(["amenity"])

    with pytest.raises(ValueError):
        MODULE.build_tag_filters(["amenity="])

    boundaries_query = MODULE.build_boundaries_query(make_boundaries_args(admin_level=["2", "8"]))
    assert 'is_in(52.5163,13.3777)' in boundaries_query
    assert '["admin_level"~"^(2|8)$"]' in boundaries_query

    nearby_query = MODULE.build_nearby_query(make_nearby_args(tag=["tourism=attraction", "name=Brandenburger Tor"]))
    assert 'node(around:150.0,52.5163,13.3777)' in nearby_query
    assert 'relation(around:150.0,52.5163,13.3777)' in nearby_query

    with pytest.raises(ValueError):
        MODULE.build_nearby_query(make_nearby_args(radius=0))

    query_file = tmp_path / "query.overpassql"
    query_file.write_text("  node[id=1];out;  ", encoding="utf-8")
    assert MODULE.read_overpass_query(None, str(query_file)) == "node[id=1];out;"
    assert MODULE.read_overpass_query("  node[id=2];out;  ", None) == "node[id=2];out;"

    empty_file = tmp_path / "empty.overpassql"
    empty_file.write_text("   ", encoding="utf-8")
    with pytest.raises(ValueError):
        MODULE.read_overpass_query(None, str(empty_file))

    with pytest.raises(ValueError):
        MODULE.read_overpass_query("node[id=1];out;", str(query_file))

    with pytest.raises(ValueError):
        MODULE.read_overpass_query(None, str(tmp_path / "missing.overpassql"))

    with pytest.raises(ValueError):
        MODULE.read_overpass_query("   ", None)

    with pytest.raises(ValueError):
        MODULE.read_overpass_query(None, None)


def test_result_helpers_cover_counts_distances_and_summaries() -> None:
    assert MODULE.count_results([1, 2, 3]) == 3
    assert MODULE.count_results({"features": [{"id": 1}]}) == 1
    assert MODULE.count_results({"features": {"id": 1}}) == 1
    assert MODULE.count_results({"status": 0}) == 1
    assert MODULE.count_results({"other": 1}) is None
    assert MODULE.coerce_float("bad") is None
    assert MODULE.admin_level_sort_key(None) == (999, "")
    assert MODULE.admin_level_sort_key("abc") == (999, "abc")
    assert MODULE.extract_country_code({}) is None
    assert MODULE.element_coordinates({"type": "way"}) == (None, None)
    assert MODULE.haversine_distance_meters(52.5, 13.4, 52.5, 13.4) == pytest.approx(0.0)

    boundaries = MODULE.summarize_boundaries(
        {
            "elements": [
                {"type": "relation", "id": 8, "tags": {"name": "Berlin", "admin_level": "8"}},
                {"type": "relation", "id": 2, "tags": {"name": "Germany", "admin_level": "2"}},
            ],
            "osm3s": {"timestamp_osm_base": "2026-03-30T00:00:00Z", "timestamp_areas_base": "2026-03-29T00:00:00Z"},
        },
        1,
    )
    assert boundaries["result_count"] == 2
    assert boundaries["results"][0]["name"] == "Germany"
    assert boundaries["results_truncated"] is True

    empty_boundaries = MODULE.summarize_boundaries({"elements": [{"type": "relation", "id": 1, "tags": None}]}, 5)
    assert empty_boundaries["result_count"] == 0

    nearby = MODULE.summarize_nearby(
        {
            "elements": [
                {"type": "way", "id": 2, "center": {"lat": 52.5173, "lon": 13.3787}, "tags": {"name": "Far"}},
                {"type": "node", "id": 1, "lat": 52.5163, "lon": 13.3777, "tags": {"name": "Near"}},
            ],
            "osm3s": {"timestamp_osm_base": "2026-03-30T00:00:00Z"},
        },
        52.5163,
        13.3777,
        1,
    )
    assert nearby["match_count"] == 2
    assert nearby["matches"][0]["tags"]["name"] == "Near"
    assert nearby["matches_truncated"] is True

    text_summary = MODULE.summarize_overpass_response("x" * 10, 2, 5)
    assert text_summary["body_format"] == "text"
    assert text_summary["body_truncated"] is True

    json_summary = MODULE.summarize_overpass_response(
        {
            "elements": [{"type": "node", "id": 1}, {"type": "way", "id": 2}, {"type": "way", "id": 3}],
            "osm3s": {"timestamp_osm_base": "2026-03-30T00:00:00Z"},
        },
        2,
        100,
    )
    assert json_summary["element_count"] == 3
    assert json_summary["counts_by_type"] == {"node": 1, "way": 2}
    assert len(json_summary["elements_preview"]) == 2

    raw_json_summary = MODULE.summarize_overpass_response({"meta": "x"}, 5, 100)
    assert raw_json_summary == {"body_format": "json", "body": {"meta": "x"}, "body_truncated": False}

    full_json_summary = MODULE.summarize_overpass_response(
        {"elements": [{"type": "node", "id": 1}]},
        5,
        100,
    )
    assert full_json_summary["elements"] == [{"type": "node", "id": 1}]
    assert full_json_summary["body_truncated"] is False


def test_enrich_verify_candidates_adds_distance_and_country_flags() -> None:
    enriched = MODULE.enrich_verify_candidates(
        [
            {"lat": "52.5163", "lon": "13.3777", "address": {"country_code": "de"}},
            {"lat": None, "lon": None, "country_code": "at"},
        ],
        52.5163,
        13.3777,
        10.0,
        "DE",
    )

    assert enriched[0]["distance_to_expected_meters"] == pytest.approx(0.0)
    assert enriched[0]["within_max_distance"] is True
    assert enriched[0]["matches_expected_countrycode"] is True
    assert "distance_to_expected_meters" not in enriched[1]
    assert enriched[1]["matches_expected_countrycode"] is False


def test_handle_verify_runs_search_and_reverse_and_selects_closest_match() -> None:
    args = make_search_args(
        format="xml",
        expected_lat=52.5163,
        expected_lon=13.3777,
        max_distance_meters=50.0,
        expected_countrycode="DE",
        accept_language="en,de",
    )
    client = FakeClient(
        nominatim_responses=[
            make_service_response(
                [
                    {"display_name": "Far", "lat": "52.5200", "lon": "13.4000", "address": {"country_code": "de"}},
                    {"display_name": "Near", "lat": "52.5163", "lon": "13.3777", "address": {"country_code": "de"}},
                ],
                url="https://nominatim.example.com/search",
            ),
            make_service_response({"display_name": "Expected point"}, url="https://nominatim.example.com/reverse"),
        ]
    )

    payload = MODULE.handle_verify(args, client)

    assert client.nominatim_calls[0][0] == "/search"
    assert client.nominatim_calls[0][1]["format"] == "jsonv2"
    assert client.nominatim_calls[1][0] == "/reverse"
    assert payload["matched"] is True
    assert payload["best_match"]["display_name"] == "Far"
    assert payload["closest_match_to_expected_coordinate"]["display_name"] == "Near"
    assert payload["expected_coordinate_reverse"]["display_name"] == "Expected point"


def test_handle_search_reverse_lookup_details_status_and_verify_without_expected_coordinate() -> None:
    client = FakeClient(
        nominatim_responses=[
            make_service_response([{"display_name": "Search result"}], url="https://nominatim.example.com/search"),
            make_service_response({"display_name": "Reverse result"}, url="https://nominatim.example.com/reverse"),
            make_service_response([{"display_name": "Lookup result"}], url="https://nominatim.example.com/lookup"),
            make_service_response({"display_name": "Details result"}, url="https://nominatim.example.com/details"),
            make_service_response({"status": 0}, url="https://nominatim.example.com/status"),
            make_service_response([{"display_name": "Verify result", "lat": "52.5163", "lon": "13.3777"}], url="https://nominatim.example.com/search"),
        ]
    )

    search_payload = MODULE.handle_search(make_search_args(), client)
    reverse_payload = MODULE.handle_reverse(make_reverse_args(), client)
    lookup_payload = MODULE.handle_lookup(make_lookup_args(), client)
    details_payload = MODULE.handle_details(make_details_args(place_id=42), client)
    status_payload = MODULE.handle_status(SimpleNamespace(format="json"), client)
    verify_payload = MODULE.handle_verify(make_search_args(expected_lat=None, expected_lon=None), client)

    assert search_payload["endpoint"] == "search"
    assert search_payload["response"] == [{"display_name": "Search result"}]
    assert reverse_payload["endpoint"] == "reverse"
    assert reverse_payload["response"] == {"display_name": "Reverse result"}
    assert lookup_payload["endpoint"] == "lookup"
    assert lookup_payload["request"]["osm_ids"] == ["W50637691"]
    assert details_payload["endpoint"] == "details"
    assert details_payload["response"] == {"display_name": "Details result"}
    assert status_payload["endpoint"] == "status"
    assert status_payload["response"] == {"status": 0}
    assert verify_payload["request"]["expected_coordinate"] is None
    assert verify_payload["expected_coordinate_reverse"] is None
    assert verify_payload["closest_match_to_expected_coordinate"] is None


def test_handle_functions_validate_errors_and_public_guards() -> None:
    with pytest.raises(ValueError):
        MODULE.handle_verify(make_search_args(expected_lat=52.5), FakeClient())

    with pytest.raises(RuntimeError):
        MODULE.handle_verify(
            make_search_args(),
            FakeClient(nominatim_responses=[make_service_response({"not": "a list"})]),
        )

    with pytest.raises(RuntimeError):
        MODULE.handle_details(make_details_args(place_id=42), FakeClient(public_nominatim=True))

    with pytest.raises(ValueError):
        MODULE.handle_boundaries(make_boundaries_args(overpass_timeout=0), FakeClient())

    with pytest.raises(ValueError):
        MODULE.handle_boundaries(make_boundaries_args(max_preview_results=0), FakeClient())

    with pytest.raises(RuntimeError):
        MODULE.handle_boundaries(
            make_boundaries_args(),
            FakeClient(overpass_responses=[make_service_response("not-json")]),
        )

    with pytest.raises(RuntimeError):
        MODULE.handle_nearby(
            make_nearby_args(),
            FakeClient(overpass_responses=[make_service_response("not-json")]),
        )

    with pytest.raises(ValueError):
        MODULE.handle_nearby(make_nearby_args(overpass_timeout=0), FakeClient())

    with pytest.raises(ValueError):
        MODULE.handle_nearby(make_nearby_args(max_preview_results=0), FakeClient())

    with pytest.raises(ValueError):
        MODULE.handle_overpass(make_overpass_args(max_preview_elements=0), FakeClient())

    with pytest.raises(ValueError):
        MODULE.handle_overpass(make_overpass_args(max_body_chars=0), FakeClient())


def test_handle_boundaries_nearby_and_overpass_shape_payloads(tmp_path: Path) -> None:
    query_file = tmp_path / "cafes.overpassql"
    query_file.write_text("node[amenity=cafe];out;", encoding="utf-8")
    client = FakeClient(
        overpass_responses=[
            make_service_response({"elements": [{"type": "relation", "id": 2, "tags": {"name": "Germany", "admin_level": "2"}}]}),
            make_service_response({"elements": [{"type": "node", "id": 1, "lat": 52.5163, "lon": 13.3777, "tags": {"name": "Gate"}}]}),
            make_service_response(
                {"elements": [{"type": "node", "id": 1}, {"type": "way", "id": 2}]},
                content_type="application/json",
            ),
        ]
    )

    boundaries_payload = MODULE.handle_boundaries(make_boundaries_args(admin_level=["2"]), client)
    nearby_payload = MODULE.handle_nearby(make_nearby_args(), client)
    overpass_payload = MODULE.handle_overpass(make_overpass_args(query=None, file=str(query_file), max_preview_elements=1), client)

    assert boundaries_payload["service"] == "overpass"
    assert boundaries_payload["result_count"] == 1
    assert nearby_payload["match_count"] == 1
    assert nearby_payload["matches"][0]["distance_meters"] == pytest.approx(0.0)
    assert overpass_payload["response"]["element_count"] == 2
    assert overpass_payload["response"]["body_truncated"] is True


def test_build_client_and_main_cover_success_status_and_error_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    client = MODULE.build_client(make_client_args())
    assert client.nominatim_base_url == "https://nominatim.example.com"
    assert client.overpass_url == "https://overpass.example.com/api/interpreter"
    assert client.user_agent == "test-agent"

    with pytest.raises(ValueError):
        MODULE.build_client(make_client_args(timeout=0))

    monkeypatch.setattr(MODULE, "build_client", lambda args: object())
    monkeypatch.setattr(
        MODULE,
        "handle_status",
        lambda args, client: {"response": {"status": 0}, "endpoint": "status"},
    )
    monkeypatch.setattr(sys, "argv", ["query.py", "status"])
    assert MODULE.main() == 0
    assert json.loads(capsys.readouterr().out)["endpoint"] == "status"

    monkeypatch.setattr(
        MODULE,
        "handle_status",
        lambda args, client: {"response": {"status": 2}, "endpoint": "status"},
    )
    monkeypatch.setattr(sys, "argv", ["query.py", "status"])
    assert MODULE.main() == 1
    assert json.loads(capsys.readouterr().out)["response"]["status"] == 2

    monkeypatch.setenv("OSM_TIMEOUT", "bad")
    monkeypatch.setattr(sys, "argv", ["query.py", "status"])
    assert MODULE.main() == 1
    assert "Environment variable OSM_TIMEOUT must be an integer" in capsys.readouterr().err

    monkeypatch.delenv("OSM_TIMEOUT", raising=False)
    missing_query_file = tmp_path / "missing.overpassql"
    monkeypatch.setattr(sys, "argv", ["query.py", "overpass", "--file", str(missing_query_file)])
    assert MODULE.main() == 1
    assert "Could not read Overpass query file" in capsys.readouterr().err


def test_main_reraises_system_exit_and_script_entrypoint_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ExplodingParser:
        def parse_args(self) -> SimpleNamespace:
            raise SystemExit(2)

    monkeypatch.setattr(MODULE, "configure_stdio", lambda: None)
    monkeypatch.setattr(MODULE, "load_local_env", lambda: None)
    monkeypatch.setattr(MODULE, "build_parser", lambda: ExplodingParser())

    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()

    assert exc_info.value.code == 2

    fake_session = FakeSession(get_responses=[FakeResponse(json_payload={"status": 0}, url="https://nominatim.example.com/status")])
    monkeypatch.setattr(requests, "Session", lambda: fake_session)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "status", "--nominatim-base-url", "https://nominatim.example.com"],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["endpoint"] == "status"
