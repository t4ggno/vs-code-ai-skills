---
name: openstreetmap
description: Query OpenStreetMap-powered Nominatim and Overpass services for geocoding, reverse geocoding, address verification, nearby POIs, administrative boundaries, and raw OSM data.
---

# OpenStreetMap Skill

Use this skill when you need location intelligence from OpenStreetMap data:

- forward geocoding for addresses, places, and POIs
- reverse geocoding from latitude/longitude to a likely address
- address normalization and verification against expected coordinates
- raw OSM object lookup by `N`, `W`, or `R` IDs
- nearby POI discovery with exact tag filters
- administrative boundary checks for a coordinate
- ad-hoc Overpass QL queries for raw OSM data extraction

The skill combines two public OpenStreetMap services:

- **Nominatim** for search, reverse geocoding, lookup, and service status
- **Overpass API** for raw map data, nearby POIs, and boundary discovery

## What the script returns

`openstreetmap/query.py` prints structured JSON so the calling agent can inspect:

- request metadata
- resolved URLs
- parsed API responses
- candidate counts and previews
- derived metrics like distance-to-expected-coordinate for verification and nearby searches

## Commands

### Forward geocode an address or place

```text
python openstreetmap/query.py search "Brandenburger Tor, Berlin" --limit 3 --namedetails --extratags
```

### Verify a location and normalize the best address match

```text
python openstreetmap/query.py verify "Brandenburger Tor, Berlin" --expected-lat 52.516275 --expected-lon 13.377704 --max-distance-meters 250
```

### Reverse geocode a coordinate

```text
python openstreetmap/query.py reverse 52.516275 13.377704 --zoom 18
```

### Look up raw OSM objects by OSM ID

```text
python openstreetmap/query.py lookup W50637691 R146656
```

### Find administrative boundaries containing a coordinate

```text
python openstreetmap/query.py boundaries 52.516275 13.377704 --admin-level 2 --admin-level 8
```

### Search nearby features with exact tags

```text
python openstreetmap/query.py nearby 52.516275 13.377704 500 --tag amenity=cafe --tag wheelchair=yes
```

### Run a raw Overpass QL query

```text
python openstreetmap/query.py overpass "[out:json][timeout:25];nwr[amenity=drinking_water](52.51,13.37,52.53,13.41);out body center;"
```

### Check Nominatim service health

```text
python openstreetmap/query.py status
```

### Inspect Nominatim details on your own instance

```text
python openstreetmap/query.py details --nominatim-base-url https://your-nominatim.example.com --osm-type W --osm-id 50637691 --linkedplaces --hierarchy --polygon-geojson
```

## Optional environment variables

The script also reads optional values from `.env` or the process environment:

- `OSM_NOMINATIM_URL`
- `OSM_OVERPASS_URL`
- `OSM_USER_AGENT`
- `OSM_CONTACT_EMAIL`
- `OSM_TIMEOUT`

## Public-service guardrails

When the default public services are used, keep these rules in mind:

- Public Nominatim requires a meaningful `User-Agent` or `Referer`.
- Public Nominatim should be kept to **at most 1 request per second**.
- Public Nominatim must **not** be used for client-side autocomplete or heavy bulk jobs.
- Public Nominatim `/details` is **not** allowed for scripted access, so this script blocks that endpoint unless you supply a custom `--nominatim-base-url`.
- Use **Overpass** for raw OSM data extraction and POI searches rather than trying to stretch Nominatim into a bulk data API.

## When to prefer this skill

Prefer this skill over general web search when you need:

- a best-effort canonical address for a place name or messy address string
- a reverse geocode for a coordinate
- a sanity check that a named place is close to an expected location
- exact-tag nearby searches like `amenity=cafe`, `tourism=hotel`, or `highway=bus_stop`
- administrative context such as country, state, city, or district boundaries for a point
- raw Overpass QL output for map-derived datasets
