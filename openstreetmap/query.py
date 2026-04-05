from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

DEFAULT_TIMEOUT = 30
DEFAULT_OVERPASS_QUERY_TIMEOUT = 25
DEFAULT_NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = "vs-code-ai-skills-openstreetmap/1.0 (+https://github.com/t4ggno/vs-code-ai-skills)"
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_PREVIEW_RESULTS = 20
DEFAULT_MAX_BODY_CHARS = 12000
MAX_SEARCH_LIMIT = 40
MAX_LOOKUP_IDS = 50
MIN_PUBLIC_NOMINATIM_DELAY_SECONDS = 1.0
PUBLIC_NOMINATIM_HOSTS = {"nominatim.openstreetmap.org"}
LAYER_CHOICES = ("address", "poi", "railway", "natural", "manmade")
NOMINATIM_FORMAT_CHOICES = ("json", "jsonv2", "geojson", "geocodejson", "xml")
STRUCTURED_SEARCH_FIELDS = (
    "amenity",
    "street",
    "city",
    "county",
    "state",
    "country",
    "postalcode",
)


def get_env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    cleaned = raw_value.strip()
    if not cleaned:
        return default
    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


def load_local_env() -> None:
    env_paths = [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]
    seen: set[Path] = set()
    for env_path in env_paths:
        if not env_path.exists() or env_path in seen:
            continue
        seen.add(env_path)
        load_dotenv(env_path, override=False)


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def normalize_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        raise ValueError("Base URLs must not be empty.")
    return cleaned


def truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return f"{value[:max_chars]}\n… [truncated {len(value) - max_chars} chars]", True


def raise_for_status_with_context(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body_preview, _ = truncate_text(response.text.strip(), 2000)
        if body_preview:
            raise RuntimeError(f"HTTP {response.status_code} from {response.url}: {body_preview}") from exc
        raise RuntimeError(f"HTTP {response.status_code} from {response.url}.") from exc


def parse_response_content(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def build_endpoint_payload(
    service: str,
    endpoint: str,
    request: dict[str, Any],
    response_meta: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "service": service,
        "endpoint": endpoint,
        "request": request,
        "resolved_url": response_meta["url"],
        "status": response_meta["status"],
        "content_type": response_meta["content_type"],
        **extra,
    }


class OpenStreetMapClient:
    def __init__(
        self,
        nominatim_base_url: str,
        overpass_url: str,
        user_agent: str,
        email: str | None,
        timeout: int,
    ) -> None:
        self.nominatim_base_url = normalize_base_url(nominatim_base_url)
        self.overpass_url = normalize_base_url(overpass_url)
        self.user_agent = user_agent.strip() or DEFAULT_USER_AGENT
        self.email = email.strip() if email else None
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            }
        )
        self._last_nominatim_request_at: float | None = None

    def is_public_nominatim(self) -> bool:
        host = requests.utils.urlparse(self.nominatim_base_url).hostname or ""
        return host.lower() in PUBLIC_NOMINATIM_HOSTS

    def maybe_wait_for_public_nominatim(self) -> None:
        if not self.is_public_nominatim() or self._last_nominatim_request_at is None:
            return
        elapsed = time.monotonic() - self._last_nominatim_request_at
        if elapsed >= MIN_PUBLIC_NOMINATIM_DELAY_SECONDS:
            return
        time.sleep(MIN_PUBLIC_NOMINATIM_DELAY_SECONDS - elapsed)

    def nominatim_request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        self.maybe_wait_for_public_nominatim()
        request_params = {key: value for key, value in params.items() if value is not None}
        if self.email and "email" not in request_params:
            request_params["email"] = self.email

        response = self.session.get(
            f"{self.nominatim_base_url}{path}",
            params=request_params,
            timeout=self.timeout,
        )
        self._last_nominatim_request_at = time.monotonic()
        raise_for_status_with_context(response)
        return {
            "url": response.url,
            "status": response.status_code,
            "content_type": response.headers.get("Content-Type", ""),
            "data": parse_response_content(response),
        }

    def overpass_request(self, query: str) -> dict[str, Any]:
        response = self.session.post(
            self.overpass_url,
            data={"data": query},
            timeout=self.timeout,
        )
        raise_for_status_with_context(response)
        return {
            "url": response.url,
            "status": response.status_code,
            "content_type": response.headers.get("Content-Type", ""),
            "data": parse_response_content(response),
        }


def add_bool_flag(
    parser: argparse.ArgumentParser,
    name: str,
    default: bool,
    enable_help: str,
    disable_help: str,
) -> None:
    parser.set_defaults(**{name: default})
    option = name.replace("_", "-")
    parser.add_argument(f"--{option}", dest=name, action="store_true", help=enable_help)
    parser.add_argument(f"--no-{option}", dest=name, action="store_false", help=disable_help)


def add_common_arguments(parser: argparse.ArgumentParser, *, use_defaults: bool) -> None:
    nominatim_default = os.getenv("OSM_NOMINATIM_URL", DEFAULT_NOMINATIM_BASE_URL) if use_defaults else argparse.SUPPRESS
    overpass_default = os.getenv("OSM_OVERPASS_URL", DEFAULT_OVERPASS_URL) if use_defaults else argparse.SUPPRESS
    user_agent_default = os.getenv("OSM_USER_AGENT", DEFAULT_USER_AGENT) if use_defaults else argparse.SUPPRESS
    email_default = os.getenv("OSM_CONTACT_EMAIL") if use_defaults else argparse.SUPPRESS
    timeout_default = get_env_int("OSM_TIMEOUT", DEFAULT_TIMEOUT) if use_defaults else argparse.SUPPRESS
    parser.add_argument(
        "--nominatim-base-url",
        default=nominatim_default,
        help=f"Base URL for Nominatim-compatible geocoding. Default: {DEFAULT_NOMINATIM_BASE_URL}.",
    )
    parser.add_argument(
        "--overpass-url",
        default=overpass_default,
        help=f"Overpass interpreter endpoint. Default: {DEFAULT_OVERPASS_URL}.",
    )
    parser.add_argument(
        "--user-agent",
        default=user_agent_default,
        help="HTTP User-Agent used for OpenStreetMap services.",
    )
    parser.add_argument(
        "--email",
        default=email_default,
        help="Optional contact email for larger Nominatim request volumes.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=timeout_default,
        help=f"HTTP timeout in seconds. Default: {DEFAULT_TIMEOUT}.",
    )


def build_common_parser(*, use_defaults: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    add_common_arguments(parser, use_defaults=use_defaults)
    return parser


def add_polygon_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--polygon-format",
        choices=("geojson", "kml", "svg", "text"),
        help="Include full geometry in the requested polygon format.",
    )
    parser.add_argument(
        "--polygon-threshold",
        type=float,
        help="Simplification tolerance in degrees when polygon output is enabled.",
    )


def add_nominatim_output_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_format: str,
    default_addressdetails: bool,
) -> None:
    parser.add_argument(
        "--format",
        choices=NOMINATIM_FORMAT_CHOICES,
        default=default_format,
        help=f"Nominatim output format. Default: {default_format}.",
    )
    add_bool_flag(
        parser,
        "addressdetails",
        default_addressdetails,
        "Include structured address components.",
        "Do not include structured address components.",
    )
    add_bool_flag(
        parser,
        "extratags",
        False,
        "Include extra tags like website, opening_hours, or wikidata when available.",
        "Do not include extra tags.",
    )
    add_bool_flag(
        parser,
        "namedetails",
        False,
        "Include multilingual and alternative names when available.",
        "Do not include multilingual and alternative names.",
    )
    add_bool_flag(
        parser,
        "entrances",
        False,
        "Include tagged entrances when available.",
        "Do not include tagged entrances.",
    )
    parser.add_argument(
        "--accept-language",
        help="Preferred result language order, for example 'en,de' or a full Accept-Language header value.",
    )
    add_polygon_arguments(parser)


def add_search_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query", nargs="?", help="Free-form search query, for example 'Brandenburger Tor, Berlin'.")
    parser.add_argument("--amenity", help="Structured search field for POI name or type.")
    parser.add_argument("--street", help="Structured search field for house number and street name.")
    parser.add_argument("--city", help="Structured search field for city.")
    parser.add_argument("--county", help="Structured search field for county.")
    parser.add_argument("--state", help="Structured search field for state.")
    parser.add_argument("--country", help="Structured search field for country.")
    parser.add_argument("--postalcode", help="Structured search field for postal code.")


def build_parser() -> argparse.ArgumentParser:
    common_parser = build_common_parser(use_defaults=True)
    subcommand_common_parser = build_common_parser(use_defaults=False)
    parser = argparse.ArgumentParser(
        description="Query OpenStreetMap services for geocoding, address verification, raw OSM lookup, and Overpass data extraction.",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser(
        "search",
        parents=[subcommand_common_parser],
        help="Forward geocode a free-form or structured address with Nominatim.",
    )
    add_search_input_arguments(search_parser)
    add_nominatim_output_arguments(search_parser, default_format="jsonv2", default_addressdetails=True)
    search_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help=f"Maximum number of search results to request. Default: {DEFAULT_SEARCH_LIMIT}. Cannot exceed {MAX_SEARCH_LIMIT}.",
    )
    search_parser.add_argument(
        "--countrycode",
        action="append",
        help="Hard-filter to one or more ISO 3166-1 alpha-2 country codes. Can be repeated.",
    )
    search_parser.add_argument(
        "--layer",
        action="append",
        choices=LAYER_CHOICES,
        help="Limit search results to one or more thematic layers. Can be repeated.",
    )
    search_parser.add_argument(
        "--feature-type",
        choices=("country", "state", "city", "settlement"),
        help="Restrict the search to a specific address-layer feature type.",
    )
    search_parser.add_argument(
        "--exclude-place-id",
        action="append",
        help="Exclude one or more Nominatim place_ids from the results. Can be repeated.",
    )
    search_parser.add_argument(
        "--viewbox",
        help="Optional result focus box in x1,y1,x2,y2 order (longitude,latitude,longitude,latitude).",
    )
    add_bool_flag(
        search_parser,
        "bounded",
        False,
        "Turn the viewbox into a hard filter instead of a ranking boost.",
        "Use the viewbox only as a ranking boost.",
    )
    add_bool_flag(
        search_parser,
        "dedupe",
        True,
        "Deduplicate search results that represent the same real-world place.",
        "Disable result deduplication.",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        parents=[subcommand_common_parser],
        help="Verify a textual location against expected coordinates or country and return normalized address data.",
    )
    add_search_input_arguments(verify_parser)
    add_nominatim_output_arguments(verify_parser, default_format="jsonv2", default_addressdetails=True)
    verify_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help=f"Maximum number of candidates to inspect. Default: {DEFAULT_SEARCH_LIMIT}. Cannot exceed {MAX_SEARCH_LIMIT}.",
    )
    verify_parser.add_argument(
        "--countrycode",
        action="append",
        help="Hard-filter verify candidates to one or more ISO 3166-1 alpha-2 country codes. Can be repeated.",
    )
    verify_parser.add_argument(
        "--layer",
        action="append",
        choices=LAYER_CHOICES,
        help="Limit verify candidates to one or more thematic layers. Can be repeated.",
    )
    verify_parser.add_argument(
        "--feature-type",
        choices=("country", "state", "city", "settlement"),
        help="Restrict verify candidates to a specific address-layer feature type.",
    )
    verify_parser.add_argument(
        "--viewbox",
        help="Optional result focus box in x1,y1,x2,y2 order (longitude,latitude,longitude,latitude).",
    )
    add_bool_flag(
        verify_parser,
        "bounded",
        False,
        "Turn the viewbox into a hard filter instead of a ranking boost.",
        "Use the viewbox only as a ranking boost.",
    )
    add_bool_flag(
        verify_parser,
        "dedupe",
        True,
        "Deduplicate verify candidates that represent the same real-world place.",
        "Disable candidate deduplication.",
    )
    verify_parser.add_argument("--expected-lat", type=float, help="Expected latitude for the verified location.")
    verify_parser.add_argument("--expected-lon", type=float, help="Expected longitude for the verified location.")
    verify_parser.add_argument(
        "--max-distance-meters",
        type=float,
        help="Optional pass/fail threshold for candidate distance from the expected coordinate.",
    )
    verify_parser.add_argument(
        "--expected-countrycode",
        help="Optional ISO 3166-1 alpha-2 country code to compare against the returned country_code.",
    )

    reverse_parser = subparsers.add_parser(
        "reverse",
        parents=[subcommand_common_parser],
        help="Reverse geocode a coordinate to a likely address or place.",
    )
    reverse_parser.add_argument("lat", type=float, help="Latitude in WGS84.")
    reverse_parser.add_argument("lon", type=float, help="Longitude in WGS84.")
    add_nominatim_output_arguments(reverse_parser, default_format="jsonv2", default_addressdetails=True)
    reverse_parser.add_argument(
        "--zoom",
        type=int,
        default=18,
        help="Reverse geocoding detail level from 0-18. Default: 18.",
    )
    reverse_parser.add_argument(
        "--layer",
        action="append",
        choices=LAYER_CHOICES,
        help="Limit reverse results to one or more thematic layers. Can be repeated.",
    )

    lookup_parser = subparsers.add_parser(
        "lookup",
        parents=[subcommand_common_parser],
        help="Look up one or more OSM objects by OSM ID using Nominatim.",
    )
    lookup_parser.add_argument(
        "osm_ids",
        nargs="+",
        help="OSM IDs like N240109189, W50637691, or R146656. Multiple IDs may be space- or comma-separated.",
    )
    add_nominatim_output_arguments(lookup_parser, default_format="jsonv2", default_addressdetails=True)

    details_parser = subparsers.add_parser(
        "details",
        parents=[subcommand_common_parser],
        help="Inspect detailed Nominatim place internals. Requires a self-hosted or third-party Nominatim instance.",
    )
    details_parser.add_argument("--place-id", type=int, help="Nominatim place_id to inspect.")
    details_parser.add_argument(
        "--osm-type",
        choices=("N", "W", "R", "node", "way", "relation"),
        help="OSM type when using --osm-id.",
    )
    details_parser.add_argument("--osm-id", type=int, help="OSM ID when using --osm-type.")
    details_parser.add_argument("--class-name", help="Optional class disambiguator for objects with multiple main tags.")
    add_bool_flag(
        details_parser,
        "addressdetails",
        False,
        "Include address breakdown information.",
        "Do not include address breakdown information.",
    )
    add_bool_flag(
        details_parser,
        "keywords",
        False,
        "Include name and address keyword lists.",
        "Do not include keyword lists.",
    )
    add_bool_flag(
        details_parser,
        "linkedplaces",
        True,
        "Include linked places for the same physical object.",
        "Do not include linked places.",
    )
    add_bool_flag(
        details_parser,
        "hierarchy",
        False,
        "Include dependent POIs and address hierarchy information.",
        "Do not include dependent POIs and address hierarchy information.",
    )
    add_bool_flag(
        details_parser,
        "group_hierarchy",
        False,
        "Group hierarchy output by type.",
        "Do not group hierarchy output by type.",
    )
    add_bool_flag(
        details_parser,
        "entrances",
        False,
        "Include tagged entrances.",
        "Do not include tagged entrances.",
    )
    add_bool_flag(
        details_parser,
        "polygon_geojson",
        False,
        "Include GeoJSON geometry for the place.",
        "Do not include GeoJSON geometry for the place.",
    )
    details_parser.add_argument(
        "--accept-language",
        help="Preferred language order for names, using the Accept-Language syntax.",
    )

    status_parser = subparsers.add_parser(
        "status",
        parents=[subcommand_common_parser],
        help="Check the status of the configured Nominatim service.",
    )
    status_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Status endpoint output format. Default: json.",
    )

    boundaries_parser = subparsers.add_parser(
        "boundaries",
        parents=[subcommand_common_parser],
        help="Find administrative boundaries containing a coordinate using Overpass is_in().",
    )
    boundaries_parser.add_argument("lat", type=float, help="Latitude in WGS84.")
    boundaries_parser.add_argument("lon", type=float, help="Longitude in WGS84.")
    boundaries_parser.add_argument(
        "--admin-level",
        action="append",
        help="Optional admin_level filter. Can be repeated, for example --admin-level 2 --admin-level 8.",
    )
    boundaries_parser.add_argument(
        "--overpass-timeout",
        type=int,
        default=DEFAULT_OVERPASS_QUERY_TIMEOUT,
        help=f"Overpass query timeout in seconds. Default: {DEFAULT_OVERPASS_QUERY_TIMEOUT}.",
    )
    boundaries_parser.add_argument(
        "--max-preview-results",
        type=int,
        default=DEFAULT_PREVIEW_RESULTS,
        help=f"Maximum number of boundary results to print. Default: {DEFAULT_PREVIEW_RESULTS}.",
    )

    nearby_parser = subparsers.add_parser(
        "nearby",
        parents=[subcommand_common_parser],
        help="Find nearby OSM features by exact tags using an Overpass around() query.",
    )
    nearby_parser.add_argument("lat", type=float, help="Latitude in WGS84.")
    nearby_parser.add_argument("lon", type=float, help="Longitude in WGS84.")
    nearby_parser.add_argument("radius", type=float, help="Search radius in meters.")
    nearby_parser.add_argument(
        "--tag",
        action="append",
        required=True,
        help="Exact key=value tag filter. Can be repeated, for example --tag amenity=cafe --tag wheelchair=yes.",
    )
    nearby_parser.add_argument(
        "--overpass-timeout",
        type=int,
        default=DEFAULT_OVERPASS_QUERY_TIMEOUT,
        help=f"Overpass query timeout in seconds. Default: {DEFAULT_OVERPASS_QUERY_TIMEOUT}.",
    )
    nearby_parser.add_argument(
        "--max-preview-results",
        type=int,
        default=DEFAULT_PREVIEW_RESULTS,
        help=f"Maximum number of nearby results to print. Default: {DEFAULT_PREVIEW_RESULTS}.",
    )

    overpass_parser = subparsers.add_parser(
        "overpass",
        parents=[subcommand_common_parser],
        help="Run a raw Overpass QL query and summarize the response.",
    )
    overpass_parser.add_argument("query", nargs="?", help="Raw Overpass QL query string.")
    overpass_parser.add_argument("--file", help="Path to a file containing the Overpass QL query.")
    overpass_parser.add_argument(
        "--max-preview-elements",
        type=int,
        default=DEFAULT_PREVIEW_RESULTS,
        help=f"Maximum number of Overpass elements to include in the preview. Default: {DEFAULT_PREVIEW_RESULTS}.",
    )
    overpass_parser.add_argument(
        "--max-body-chars",
        type=int,
        default=DEFAULT_MAX_BODY_CHARS,
        help=f"Maximum number of non-JSON response characters to print. Default: {DEFAULT_MAX_BODY_CHARS}.",
    )

    return parser


def validate_comma_numbers(raw_value: str, expected_parts: int, label: str) -> str:
    parts = [part.strip() for part in raw_value.split(",")]
    if len(parts) != expected_parts:
        raise ValueError(f"Invalid {label} '{raw_value}'. Expected {expected_parts} comma-separated numbers.")
    for part in parts:
        float(part)
    return ",".join(parts)


def normalize_search_input(args: argparse.Namespace) -> tuple[str | None, dict[str, str]]:
    structured = {
        field: getattr(args, field)
        for field in STRUCTURED_SEARCH_FIELDS
        if getattr(args, field) is not None
    }
    query = args.query.strip() if args.query else None
    if query and structured:
        raise ValueError("Use either a free-form search query or structured address fields, not both.")
    if not query and not structured:
        raise ValueError("Provide a free-form query or at least one structured address field.")
    return query, structured


def build_polygon_params(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "polygon_format", None):
        return {}
    params: dict[str, Any] = {f"polygon_{args.polygon_format}": 1}
    if args.polygon_threshold is not None:
        params["polygon_threshold"] = args.polygon_threshold
    return params


def build_nominatim_output_params(args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if hasattr(args, "format"):
        params["format"] = args.format
    if hasattr(args, "addressdetails"):
        params["addressdetails"] = 1 if args.addressdetails else 0
    if hasattr(args, "extratags"):
        params["extratags"] = 1 if args.extratags else 0
    if hasattr(args, "namedetails"):
        params["namedetails"] = 1 if args.namedetails else 0
    if hasattr(args, "entrances"):
        params["entrances"] = 1 if args.entrances else 0
    if getattr(args, "accept_language", None):
        params["accept-language"] = args.accept_language
    params.update(build_polygon_params(args))
    return params


def build_search_params(args: argparse.Namespace) -> tuple[dict[str, Any], str | None, dict[str, str]]:
    query, structured = normalize_search_input(args)
    if args.limit < 1 or args.limit > MAX_SEARCH_LIMIT:
        raise ValueError(f"--limit must be between 1 and {MAX_SEARCH_LIMIT}.")

    params = build_nominatim_output_params(args)
    params["limit"] = args.limit
    params["dedupe"] = 1 if args.dedupe else 0
    if query is not None:
        params["q"] = query
    else:
        params.update(structured)

    if args.countrycode:
        params["countrycodes"] = ",".join(code.strip().lower() for code in args.countrycode if code.strip())
    if args.layer:
        params["layer"] = ",".join(args.layer)
    if getattr(args, "feature_type", None):
        params["featureType"] = args.feature_type
    if getattr(args, "exclude_place_id", None):
        params["exclude_place_ids"] = ",".join(args.exclude_place_id)
    if getattr(args, "viewbox", None):
        params["viewbox"] = validate_comma_numbers(args.viewbox, 4, "viewbox")
    if getattr(args, "bounded", False):
        params["bounded"] = 1

    return params, query, structured


def build_reverse_params(args: argparse.Namespace) -> dict[str, Any]:
    if args.zoom < 0 or args.zoom > 18:
        raise ValueError("--zoom must be between 0 and 18.")

    params = build_nominatim_output_params(args)
    params["lat"] = args.lat
    params["lon"] = args.lon
    params["zoom"] = args.zoom
    if args.layer:
        params["layer"] = ",".join(args.layer)
    return params


def normalize_osm_id_token(token: str) -> str:
    cleaned = token.strip().upper()
    if not cleaned:
        raise ValueError("OSM IDs must not be empty.")
    if cleaned[0] not in {"N", "W", "R"}:
        raise ValueError(f"Invalid OSM ID '{token}'. Prefix each ID with N, W, or R.")
    if not cleaned[1:].isdigit():
        raise ValueError(f"Invalid OSM ID '{token}'. The numeric part must contain digits only.")
    return cleaned


def normalize_osm_ids(raw_items: list[str]) -> list[str]:
    tokens: list[str] = []
    for item in raw_items:
        for part in item.split(","):
            if part.strip():
                tokens.append(normalize_osm_id_token(part))
    if not tokens:
        raise ValueError("Provide at least one OSM ID for lookup.")
    if len(tokens) > MAX_LOOKUP_IDS:
        raise ValueError(f"Lookup supports up to {MAX_LOOKUP_IDS} OSM IDs at a time.")
    return tokens


def build_lookup_params(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    osm_ids = normalize_osm_ids(args.osm_ids)
    params = build_nominatim_output_params(args)
    params["osm_ids"] = ",".join(osm_ids)
    return params, osm_ids


def normalize_details_osm_type(value: str | None) -> str | None:
    if value is None:
        return None
    upper = value.strip().upper()
    mapping = {"NODE": "N", "WAY": "W", "RELATION": "R"}
    return mapping.get(upper, upper)


def build_details_params(args: argparse.Namespace) -> dict[str, Any]:
    has_place_id = args.place_id is not None
    has_osm_ref = args.osm_type is not None or args.osm_id is not None
    if not has_place_id and not has_osm_ref:
        raise ValueError("Provide either --place-id or the combination of --osm-type and --osm-id.")
    if has_place_id and has_osm_ref:
        raise ValueError("Use either --place-id or --osm-type/--osm-id, not both.")
    if args.osm_type is None and args.osm_id is not None:
        raise ValueError("--osm-type is required when --osm-id is used.")
    if args.osm_type is not None and args.osm_id is None:
        raise ValueError("--osm-id is required when --osm-type is used.")

    params: dict[str, Any] = {
        "addressdetails": 1 if args.addressdetails else 0,
        "keywords": 1 if args.keywords else 0,
        "linkedplaces": 1 if args.linkedplaces else 0,
        "hierarchy": 1 if args.hierarchy else 0,
        "group_hierarchy": 1 if args.group_hierarchy else 0,
        "entrances": 1 if args.entrances else 0,
    }
    if args.polygon_geojson:
        params["polygon_geojson"] = 1
    if args.accept_language:
        params["accept-language"] = args.accept_language
    if args.place_id is not None:
        params["place_id"] = args.place_id
        return params

    normalized_osm_type = normalize_details_osm_type(args.osm_type)
    if normalized_osm_type not in {"N", "W", "R"}:
        raise ValueError("--osm-type must be one of N, W, R, node, way, or relation.")
    params["osmtype"] = normalized_osm_type
    params["osmid"] = args.osm_id
    if args.class_name:
        params["class"] = args.class_name
    return params


def escape_overpass_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_tag_filters(tag_items: list[str]) -> str:
    filters: list[str] = []
    for item in tag_items:
        if "=" not in item:
            raise ValueError(f"Invalid tag filter '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Invalid tag filter '{item}'. Use key=value with both parts present.")
        filters.append(f'["{escape_overpass_string(key)}"="{escape_overpass_string(value)}"]')
    return "".join(filters)


def build_boundaries_query(args: argparse.Namespace) -> str:
    level_filter = "[boundary=\"administrative\"][name][admin_level]"
    if args.admin_level:
        cleaned = [value.strip() for value in args.admin_level if value.strip()]
        if cleaned:
            regex = "|".join(escape_overpass_string(value) for value in cleaned)
            level_filter = f'{level_filter}["admin_level"~"^({regex})$"]'
    return (
        f"[out:json][timeout:{args.overpass_timeout}];\n"
        f"is_in({args.lat},{args.lon})->.areas;\n"
        f"area.areas{level_filter};\n"
        "out tags;"
    )


def build_nearby_query(args: argparse.Namespace) -> str:
    if args.radius <= 0:
        raise ValueError("radius must be greater than 0.")
    filters = build_tag_filters(args.tag)
    return (
        f"[out:json][timeout:{args.overpass_timeout}];\n"
        f"node(around:{args.radius},{args.lat},{args.lon}){filters}->.nodes;\n"
        "(\n"
        f"  way(around:{args.radius},{args.lat},{args.lon}){filters};\n"
        f"  relation(around:{args.radius},{args.lat},{args.lon}){filters};\n"
        ")->.shapes;\n"
        ".nodes out body qt;\n"
        ".shapes out tags center qt;"
    )


def read_overpass_query(query: str | None, file_path: str | None) -> str:
    if query and file_path:
        raise ValueError("Use either a direct Overpass query string or --file, not both.")
    if file_path:
        try:
            file_query = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"Could not read Overpass query file '{file_path}': {exc}") from exc
        if not file_query:
            raise ValueError(f"Overpass query file '{file_path}' is empty.")
        return file_query
    if query:
        cleaned_query = query.strip()
        if cleaned_query:
            return cleaned_query
        raise ValueError("Overpass query must not be empty.")
    raise ValueError("Provide an Overpass query string or use --file.")


def count_results(data: Any) -> int | None:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        features = data.get("features")
        if isinstance(features, list):
            return len(features)
        if isinstance(features, dict):
            return 1
        if "status" in data:
            return 1
    return None


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_meters = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    sin_phi = math.sin(delta_phi / 2.0)
    sin_lambda = math.sin(delta_lambda / 2.0)
    a_value = sin_phi * sin_phi + math.cos(phi1) * math.cos(phi2) * sin_lambda * sin_lambda
    return 2.0 * earth_radius_meters * math.atan2(math.sqrt(a_value), math.sqrt(1.0 - a_value))


def admin_level_sort_key(value: str | None) -> tuple[int, str]:
    if value is None:
        return (999, "")
    try:
        return (int(value), value)
    except ValueError:
        return (999, value)


def extract_country_code(item: dict[str, Any]) -> str | None:
    address = item.get("address")
    if isinstance(address, dict):
        country_code = address.get("country_code")
        if isinstance(country_code, str):
            return country_code.lower()
    country_code = item.get("country_code")
    if isinstance(country_code, str):
        return country_code.lower()
    return None


def enrich_verify_candidates(
    items: list[dict[str, Any]],
    expected_lat: float | None,
    expected_lon: float | None,
    max_distance_meters: float | None,
    expected_countrycode: str | None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    normalized_expected_country = expected_countrycode.lower() if expected_countrycode else None
    for item in items:
        candidate = dict(item)
        lat = coerce_float(item.get("lat"))
        lon = coerce_float(item.get("lon"))
        if expected_lat is not None and expected_lon is not None and lat is not None and lon is not None:
            distance = haversine_distance_meters(expected_lat, expected_lon, lat, lon)
            candidate["distance_to_expected_meters"] = round(distance, 1)
            if max_distance_meters is not None:
                candidate["within_max_distance"] = distance <= max_distance_meters
        if normalized_expected_country is not None:
            candidate["matches_expected_countrycode"] = extract_country_code(item) == normalized_expected_country
        enriched.append(candidate)
    return enriched


def summarize_boundaries(data: dict[str, Any], max_preview_results: int) -> dict[str, Any]:
    elements = data.get("elements", []) if isinstance(data, dict) else []
    boundaries: list[dict[str, Any]] = []
    for element in elements:
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue
        boundaries.append(
            {
                "type": element.get("type"),
                "id": element.get("id"),
                "name": tags.get("name"),
                "admin_level": tags.get("admin_level"),
                "tags": tags,
            }
        )
    boundaries.sort(key=lambda item: admin_level_sort_key(item.get("admin_level")))
    preview = boundaries[:max_preview_results]
    return {
        "result_count": len(boundaries),
        "results": preview,
        "results_truncated": len(boundaries) > len(preview),
        "osm_base": data.get("osm3s", {}).get("timestamp_osm_base") if isinstance(data, dict) else None,
        "areas_base": data.get("osm3s", {}).get("timestamp_areas_base") if isinstance(data, dict) else None,
    }


def element_coordinates(element: dict[str, Any]) -> tuple[float | None, float | None]:
    if element.get("type") == "node":
        return coerce_float(element.get("lat")), coerce_float(element.get("lon"))
    center = element.get("center")
    if isinstance(center, dict):
        return coerce_float(center.get("lat")), coerce_float(center.get("lon"))
    return None, None


def summarize_nearby(data: dict[str, Any], lat: float, lon: float, max_preview_results: int) -> dict[str, Any]:
    elements = data.get("elements", []) if isinstance(data, dict) else []
    matches: list[dict[str, Any]] = []
    for element in elements:
        element_lat, element_lon = element_coordinates(element)
        distance = None
        if element_lat is not None and element_lon is not None:
            distance = round(haversine_distance_meters(lat, lon, element_lat, element_lon), 1)
        matches.append(
            {
                "type": element.get("type"),
                "id": element.get("id"),
                "lat": element_lat,
                "lon": element_lon,
                "distance_meters": distance,
                "tags": element.get("tags", {}),
            }
        )
    matches.sort(key=lambda item: item["distance_meters"] if item["distance_meters"] is not None else math.inf)
    preview = matches[:max_preview_results]
    return {
        "match_count": len(matches),
        "matches": preview,
        "matches_truncated": len(matches) > len(preview),
        "osm_base": data.get("osm3s", {}).get("timestamp_osm_base") if isinstance(data, dict) else None,
    }


def summarize_overpass_response(data: Any, max_preview_elements: int, max_body_chars: int) -> dict[str, Any]:
    if not isinstance(data, dict):
        preview, truncated = truncate_text(str(data), max_body_chars)
        return {
            "body_format": "text",
            "body": preview,
            "body_truncated": truncated,
        }

    elements = data.get("elements")
    if not isinstance(elements, list):
        return {"body_format": "json", "body": data, "body_truncated": False}

    counts = Counter(str(element.get("type", "unknown")) for element in elements)
    payload: dict[str, Any] = {
        "body_format": "json",
        "osm_base": data.get("osm3s", {}).get("timestamp_osm_base"),
        "areas_base": data.get("osm3s", {}).get("timestamp_areas_base"),
        "element_count": len(elements),
        "counts_by_type": dict(counts),
    }
    if len(elements) <= max_preview_elements:
        payload["elements"] = elements
        payload["body_truncated"] = False
        return payload

    payload["elements_preview"] = elements[:max_preview_elements]
    payload["body_truncated"] = True
    return payload


def handle_search(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    params, query, structured = build_search_params(args)
    response = client.nominatim_request("/search", params)
    return build_endpoint_payload(
        "nominatim",
        "search",
        {
            "base_url": client.nominatim_base_url,
            "free_form_query": query,
            "structured_query": structured,
            "params": params,
        },
        response,
        result_count=count_results(response["data"]),
        response=response["data"],
    )


def handle_verify(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    if (args.expected_lat is None) != (args.expected_lon is None):
        raise ValueError("Provide both --expected-lat and --expected-lon together.")

    params, query, structured = build_search_params(args)
    params["format"] = "jsonv2"
    response = client.nominatim_request("/search", params)
    raw_data = response["data"]
    if not isinstance(raw_data, list):
        raise RuntimeError("Verify expects JSON search results. Keep the output format as json or jsonv2.")

    enriched = enrich_verify_candidates(
        raw_data,
        args.expected_lat,
        args.expected_lon,
        args.max_distance_meters,
        args.expected_countrycode,
    )
    best_match = enriched[0] if enriched else None
    closest_match = None
    if args.expected_lat is not None and args.expected_lon is not None and enriched:
        closest_match = min(
            enriched,
            key=lambda item: item.get("distance_to_expected_meters", math.inf),
        )

    expected_point_reverse = None
    reverse_call = None
    if args.expected_lat is not None and args.expected_lon is not None:
        reverse_params = {
            "format": "jsonv2",
            "lat": args.expected_lat,
            "lon": args.expected_lon,
            "addressdetails": 1,
        }
        if args.accept_language:
            reverse_params["accept-language"] = args.accept_language
        reverse_response = client.nominatim_request("/reverse", reverse_params)
        expected_point_reverse = reverse_response["data"]
        reverse_call = {
            "params": reverse_params,
            "resolved_url": reverse_response["url"],
            "status": reverse_response["status"],
            "content_type": reverse_response["content_type"],
        }

    return build_endpoint_payload(
        "nominatim",
        "verify",
        {
            "base_url": client.nominatim_base_url,
            "free_form_query": query,
            "structured_query": structured,
            "params": params,
            "expected_coordinate": (
                {"lat": args.expected_lat, "lon": args.expected_lon}
                if args.expected_lat is not None and args.expected_lon is not None
                else None
            ),
            "max_distance_meters": args.max_distance_meters,
            "expected_countrycode": args.expected_countrycode.lower() if args.expected_countrycode else None,
        },
        response,
        matched=bool(enriched),
        candidate_count=len(enriched),
        best_match=best_match,
        closest_match_to_expected_coordinate=closest_match,
        expected_coordinate_reverse=expected_point_reverse,
        expected_coordinate_reverse_request=reverse_call,
        alternatives=enriched,
    )


def handle_reverse(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    params = build_reverse_params(args)
    response = client.nominatim_request("/reverse", params)
    return build_endpoint_payload(
        "nominatim",
        "reverse",
        {
            "base_url": client.nominatim_base_url,
            "coordinate": {"lat": args.lat, "lon": args.lon},
            "params": params,
        },
        response,
        result_count=count_results(response["data"]),
        response=response["data"],
    )


def handle_lookup(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    params, osm_ids = build_lookup_params(args)
    response = client.nominatim_request("/lookup", params)
    return build_endpoint_payload(
        "nominatim",
        "lookup",
        {
            "base_url": client.nominatim_base_url,
            "osm_ids": osm_ids,
            "params": params,
        },
        response,
        result_count=count_results(response["data"]),
        response=response["data"],
    )


def handle_details(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    if client.is_public_nominatim():
        raise RuntimeError(
            "The public Nominatim details endpoint must not be used by scripts. Use --nominatim-base-url with a self-hosted or third-party Nominatim instance instead."
        )
    params = build_details_params(args)
    response = client.nominatim_request("/details", params)
    return build_endpoint_payload(
        "nominatim",
        "details",
        {
            "base_url": client.nominatim_base_url,
            "params": params,
        },
        response,
        response=response["data"],
    )


def handle_status(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    params = {"format": args.format}
    response = client.nominatim_request("/status", params)
    return build_endpoint_payload(
        "nominatim",
        "status",
        {
            "base_url": client.nominatim_base_url,
            "params": params,
        },
        response,
        response=response["data"],
    )


def handle_boundaries(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    if args.overpass_timeout < 1:
        raise ValueError("--overpass-timeout must be at least 1.")
    if args.max_preview_results < 1:
        raise ValueError("--max-preview-results must be at least 1.")
    query = build_boundaries_query(args)
    response = client.overpass_request(query)
    if not isinstance(response["data"], dict):
        raise RuntimeError("Expected JSON from Overpass for the boundaries query.")
    return build_endpoint_payload(
        "overpass",
        "boundaries",
        {
            "overpass_url": client.overpass_url,
            "coordinate": {"lat": args.lat, "lon": args.lon},
            "admin_levels": args.admin_level or [],
            "query": query,
        },
        response,
        **summarize_boundaries(response["data"], args.max_preview_results),
    )


def handle_nearby(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    if args.overpass_timeout < 1:
        raise ValueError("--overpass-timeout must be at least 1.")
    if args.max_preview_results < 1:
        raise ValueError("--max-preview-results must be at least 1.")
    query = build_nearby_query(args)
    response = client.overpass_request(query)
    if not isinstance(response["data"], dict):
        raise RuntimeError("Expected JSON from Overpass for the nearby query.")
    return build_endpoint_payload(
        "overpass",
        "nearby",
        {
            "overpass_url": client.overpass_url,
            "coordinate": {"lat": args.lat, "lon": args.lon},
            "radius_meters": args.radius,
            "tags": args.tag,
            "query": query,
        },
        response,
        **summarize_nearby(response["data"], args.lat, args.lon, args.max_preview_results),
    )


def handle_overpass(args: argparse.Namespace, client: OpenStreetMapClient) -> dict[str, Any]:
    if args.max_preview_elements < 1:
        raise ValueError("--max-preview-elements must be at least 1.")
    if args.max_body_chars < 1:
        raise ValueError("--max-body-chars must be at least 1.")
    query = read_overpass_query(args.query, args.file)
    response = client.overpass_request(query)
    return build_endpoint_payload(
        "overpass",
        "raw-query",
        {
            "overpass_url": client.overpass_url,
            "query": query,
            "file": args.file,
        },
        response,
        response=summarize_overpass_response(
            response["data"],
            args.max_preview_elements,
            args.max_body_chars,
        ),
    )


def build_client(args: argparse.Namespace) -> OpenStreetMapClient:
    if args.timeout < 1:
        raise ValueError("--timeout must be at least 1.")
    return OpenStreetMapClient(
        nominatim_base_url=args.nominatim_base_url,
        overpass_url=args.overpass_url,
        user_agent=args.user_agent,
        email=args.email,
        timeout=args.timeout,
    )


def main() -> int:
    configure_stdio()
    load_local_env()

    try:
        parser = build_parser()
        args = parser.parse_args()
        client = build_client(args)
        handlers = {
            "search": handle_search,
            "verify": handle_verify,
            "reverse": handle_reverse,
            "lookup": handle_lookup,
            "details": handle_details,
            "status": handle_status,
            "boundaries": handle_boundaries,
            "nearby": handle_nearby,
            "overpass": handle_overpass,
        }
        payload = handlers[args.command](args, client)
    except SystemExit:
        raise
    except (RuntimeError, ValueError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.command == "status":
        response_payload = payload.get("response")
        if isinstance(response_payload, dict):
            status_value = response_payload.get("status")
            if status_value not in {None, 0, "0"}:
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
