---
name: openstreetmap
description: Queries OpenStreetMap services for geocoding, reverse geocoding, address verification, boundaries, nearby POIs, and raw Overpass data. Use when the task needs structured map or location data. Do not use it as a substitute for general web search or turn-by-turn routing.
argument-hint: <operation and place/coords> [tags, expected coordinates, limits]
---

# OpenStreetMap Skill

1. Use this skill when you need structured location data from OpenStreetMap rather than free-form web content.
2. Execute the local script [query.py](./query.py) with the narrowest subcommand that matches the task.
3. Prefer Nominatim for search, reverse geocoding, lookup, and lightweight normalization tasks.
4. Prefer Overpass for nearby feature discovery, raw OSM extraction, and administrative boundary checks.
5. Keep public-service usage respectful: meaningful `User-Agent`, low request rate, and no bulk scraping against the public Nominatim instance.
6. If the user already has expected coordinates or country constraints, include them so the verification step can score candidates instead of guessing.

## Common invocations

- Forward geocode:
	`python ./query.py search "Brandenburger Tor, Berlin" --limit 3 --namedetails --extratags`
- Verify a place against expected coordinates:
	`python ./query.py verify "Brandenburger Tor, Berlin" --expected-lat 52.516275 --expected-lon 13.377704 --max-distance-meters 250`
- Reverse geocode a coordinate:
	`python ./query.py reverse 52.516275 13.377704 --zoom 18`
- Find nearby exact-tag matches:
	`python ./query.py nearby 52.516275 13.377704 500 --tag amenity=cafe --tag wheelchair=yes`
- Run raw Overpass QL:
	`python ./query.py overpass "[out:json][timeout:25];nwr[amenity=drinking_water](52.51,13.37,52.53,13.41);out body center;"`

## Optional environment variables

- `OSM_NOMINATIM_URL`
- `OSM_OVERPASS_URL`
- `OSM_USER_AGENT`
- `OSM_CONTACT_EMAIL`
- `OSM_TIMEOUT`

## Public-service guardrails

- Public Nominatim requires a meaningful `User-Agent` or `Referer`.
- Public Nominatim should be kept to **at most 1 request per second**.
- Public Nominatim must **not** be used for client-side autocomplete or heavy bulk jobs.
- Public Nominatim `/details` is **not** allowed for scripted access, so this script blocks that endpoint unless you supply a custom `--nominatim-base-url`.
- Use **Overpass** for raw OSM data extraction and POI searches rather than trying to stretch Nominatim into a bulk data API.
