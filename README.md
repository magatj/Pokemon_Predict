# Pokémon Vending Forecast

An independent community forecasting tool that answers one question:

> **When is a Pokémon vending machine near you most likely to make a product available for purchase?**

Default search area: **ZIP 98092, 10-mile radius**. Deployment target: **GitLab Pages**,
with an AWS migration scaffold ready in `infrastructure/terraform/`.

This is a working pipeline, not a mockup. Machine discovery, distance filtering,
retailer verification, observation normalization, forecasting and publishing all
execute; a live run against the official locator API is what produced the numbers
quoted below.

---

## Current state, honestly

| Thing | Status |
|---|---|
| Machines discovered within 10 miles of 98092 | **16** (from 23 found across the tiled search box) |
| Machines verified against a retailer store page | **9–10** Safeway stores, kiosk listing confirmed |
| Community observations ingested | **95** real reports, parsed from a live tracker |
| Machines showing a real last-known status | **3** |
| Machines showing a **regional network pattern** | **16** (all of them) |
| Machines reading `INSUFFICIENT DATA` | **0** |

No machine has enough history of its own yet, so rather than showing nothing,
the engine backs off to the empirical pattern across **93 community reports
within 250 miles** — standard shrinkage toward a population prior. Every such
figure is labelled *network-wide, not this machine*, shown at hour resolution
(the prior's real precision) and capped at 35%. See
[What is actually available online](#what-is-actually-available-online).

To see the scored UI, generate a clearly-labelled synthetic dataset:

```bash
python -m pokevend.jobs.seed_demo --output data-demo
```

---

## Repository tree

```
.
├── .gitlab-ci.yml                  Scheduled ingestion + Pages deployment
├── pyproject.toml                  ruff + pytest configuration
├── package.json                    npm workspace root
├── config/
│   ├── forecast_config.yaml        Every forecasting number lives here
│   └── sources.yaml                Source registry: enable/disable, rate limits
├── data/                           Committed pipeline state (machines, observations)
├── apps/
│   ├── ingestion/                  Python: ingestion, normalization, forecasting
│   │   ├── pokevend/
│   │   │   ├── config.py           Typed, eagerly validated config loader
│   │   │   ├── geo.py              Haversine, bounding boxes, bbox tiling
│   │   │   ├── geocode.py          ZIP centroid lookup
│   │   │   ├── http.py             robots.txt, rate limits, ETag caching
│   │   │   ├── localtime.py        Local-time conversion for time-of-day features
│   │   │   ├── store.py            JSON/JSONL persistence + publishing
│   │   │   ├── timeutil.py         Tolerant ISO-8601 handling
│   │   │   ├── models/             Machine, Observation, SourceHealth
│   │   │   ├── sources/            One adapter per source
│   │   │   ├── normalizers/        Radius filter, authority merge, matching, dedup
│   │   │   ├── forecast/           Features, minute pattern, interval, recency,
│   │   │   │                       network prior, engine
│   │   │   └── jobs/               refresh_machines, collect_observations,
│   │   │                           build_forecasts, seed_demo
│   │   └── tests/                  265 tests, fixtures under tests/fixtures/
│   └── web/                        React + TypeScript + Recharts dashboard
│       ├── public/data/            Generated JSON the dashboard reads
│       └── src/
│           ├── lib/                Data loading, sorting, formatting, submissions
│           ├── components/         Cards, badges, timeline, report form, sources
│           └── pages/              Dashboard, MachineDetail
└── infrastructure/terraform/       AWS migration scaffold (provisions nothing)
```

---

## Local setup

Requires **Python 3.8+** and **Node 20+**.

```bash
# Python
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate elsewhere
pip install -r apps/ingestion/requirements-dev.txt

# Node
npm install
```

Run the pipeline end to end:

```bash
export PYTHONPATH="$PWD/apps/ingestion"     # Windows: set PYTHONPATH=%CD%\apps\ingestion

python -m pokevend.jobs.refresh_machines        # discover + verify machines
python -m pokevend.jobs.collect_observations    # community observations
python -m pokevend.jobs.build_forecasts         # forecast + publish JSON

npm run dev                                     # http://localhost:5173
```

Useful flags: `--no-verify` skips retailer verification (much faster),
`--log-level DEBUG` shows every skipped row and cache hit.

Checks:

```bash
npm run lint && npm run test && npm run build
pytest
ruff check .
terraform fmt -check -recursive infrastructure/terraform
```

---

## How machines are discovered

`vending.pokemon.com` serves its locator behind an Imperva bot-protection layer,
so **the HTML is never scraped**. That page is a client for a public,
unauthenticated JSON API, and that endpoint is what `PokemonLocatorSource` uses:

```
GET https://api.vending.prod.pokemon.com/v1/machines
    ?swLat=&swLng=&neLat=&neLng=&unit=mi
```

**The API returns at most 20 machines per bounding box.** A single query covering
10 miles around 98092 returns exactly 20 — silently truncated. The search box is
therefore split into a 4×4 grid (`sources.pokemon_locator.tile_grid`), each tile
queried separately, and the results merged and de-duplicated by machine id. That
is how the run finds 23 machines where one query found 20; two of the machines
inside the radius (Enumclaw and one Kent store) only appear once tiling is on.

If any single tile comes back at the cap, the job logs a warning telling you to
raise `tile_grid`.

---

## How the 10-mile radius is calculated

1. ZIP 98092 resolves to a centroid: a local table first (deterministic and
   offline-capable), then `api.zippopotam.us`, then the configured fallback. The
   provenance is recorded in `machines.json` as `centroidSource`.
2. A bounding box is built around that centroid and tiled for querying. The box
   is a square, so its corner is ~14.1 miles out — wider than the circle.
3. Every returned machine is measured against the centroid with the **Haversine
   formula**, and `distance_miles` is computed locally. The API returns its own
   `distance` field; it is measured from the bbox centre and is **not trusted**.
4. Machines are kept when `distance <= 10.0` (inclusive of the boundary) and
   sorted nearest-first.

**City names never decide inclusion.** The 16 machines inside the radius span
Covington, Kent, Auburn, Maple Valley, Sumner, Enumclaw, Bonney Lake and Milton.
A Covington machine 4.8 miles away is kept; an Auburn machine 14 miles away is
dropped. `tests/test_radius_filter.py` asserts exactly this, including the
9.9 / 10.0 / 10.1-mile boundary cases and direction independence.

---

## Data sources, and what each one is allowed to do

| Source | Authority | Status | Notes |
|---|---|---|---|
| `pokemon_locator` | `OFFICIAL` | **Healthy** | Public JSON API. Sole source of machine records. Carries no stock data. |
| `pokemonmap` | `COMMUNITY` | **Healthy** | PokéVend Tracker. Unauthenticated `/api/machines` with a north/south/east/west bounding box, no result cap, no robots.txt and no stated restriction on automated access. Community-contributed status (`INSTOCK` / `OUT_OF_STOCK` / `MAINTENANCE`) plus `lastUpdated`, keyed by the same `Q#####` ids the official locator uses — so attribution is exact, not fuzzy. One polite request per run. |
| `retailer_pages:safeway` | `VERIFICATION` | **Healthy** | `local.safeway.com/robots.txt` allows everything except `/locator`, which this adapter never touches. Confirms the store, address, hours and the `Pokémon Kiosk` service listing. |
| `retailer_pages:fred_meyer` | `VERIFICATION` | **Disabled** | Store pages sit behind bot protection. Off in `sources.yaml` rather than worked around. |
| `reddit` | `COMMUNITY` | **`SOURCE_SKIPPED`** | `robots.txt` is `Disallow: /` and unauthenticated JSON returns 403. The adapter only talks to the official OAuth API and contributes nothing without credentials. |
| `third_party_directories` | `SUPPLEMENTAL` | **Disabled** | Aggregators republish scraped data of unknown provenance. |

Source authority is enforced in code: `merge_machine` lets a lower-authority
source *fill in* a blank field but never *overwrite* one set by the official
locator. A directory cannot quietly relocate an officially-listed machine.

### Compliance rules

The shared `PoliteSession` enforces these in one place, and
`tests/test_http_compliance.py` asserts each one:

- `robots.txt` is fetched and honoured before any request.
- Per-host rate limiting, configurable per source.
- `ETag` / `Last-Modified` conditional requests; a 304 serves the cached body
  and the origin is not asked to resend it.
- `401/403/407/451` are treated as refusals: **surfaced as a skip, never
  retried, never circumvented**.
- `429/5xx` back off, honouring `Retry-After`.
- A `User-Agent` that identifies the project.

Nothing bypasses authentication, CAPTCHAs, rate limits or bot protection. The
locator bundle embeds a Google Maps API key; it is that site's credential and
is **not** used here.

### Refresh cadence

The scheduled pipeline runs every 30 minutes by default. Machine discovery is
cheap and re-run each time; retailer verification is bounded by a 3-second
per-request rate limit and conditional caching, so an unchanged store page costs
one 304.

---

## What is actually available online

Official sources publish **where** machines are, not **when** they dispense.
This was verified directly: the locator's per-machine endpoint
(`/v1/machines/Q00164`) returns address and coordinates and **no stock field at
all**. Pokémon states there is no publicly disclosed restock schedule.

So every timing signal has to come from community reporting. Each candidate was
probed before any adapter was written:

| Source | Permitted? | Reachable? | Per-machine timing data? |
|---|---|---|---|
| **pokemonmap.com** (PokéVend Tracker) | No robots.txt, no stated restriction | Yes | **Yes — current status + timestamp, keyed by `Q#####`** |
| Reddit | `robots.txt: Disallow: /`; OAuth API is the approved route | Needs credentials | Yes, highest volume |
| Bluesky | robots explicitly allows API crawling | `searchPosts` returns 403 unauthenticated | Yes, with an app password |
| Mastodon | Tag timelines public; status search needs auth | Yes | **No** — 0 vending posts in 120 sampled |
| Lemmy | Public API, permitted | Yes | **No** — 0 results |
| PokeTrack.io | HTML allowed, **`/api/` disallowed** | Yes | Sightings are behind the disallowed API |
| Google News RSS | Permitted | Yes | Articles, not per-machine timing |

**The finding: exactly one credential-free source carries real observations.**
It is wired up and running. Everything else either has no relevant content or
needs a free API credential.

### The network prior

pokemonmap exposes each machine's **current** status only — there is no history
endpoint — so one poll yields at most one observation per machine, and the ones
inside the 10-mile radius are 129–230 days old. That is nowhere near enough for
a machine-specific forecast.

But the same source covers a much wider area. One regional query
(`network_radius_miles`, default 300) returns **95 reports across ~370
machines**, and those reports carry a real signal:

```
in-stock rate by local hour (93 regional reports)
  14:00  25%
  15:00  11%
  16:00  47%   <- best hour
  18:00   9%
```

So when a machine lacks its own history the engine falls back to that
population rate instead of showing nothing. This is ordinary shrinkage toward a
prior, and it is hedged in four explicit ways:

1. Status is `NETWORK_PATTERN`, never `OK`, and is styled differently.
2. Every figure is captioned **"Network-wide, not this machine"**.
3. Windows are a **whole hour**, because that is the prior's resolution —
   emitting 5-minute windows would imply precision it does not have.
4. Probability is capped at `network_prior.max_probability` (0.35), well below
   what genuine machine history can earn.

A machine that *does* have enough history is never downgraded to the prior; it
is scored from its own data and marked `OK`. Set `network_prior.enabled: false`
to turn the fallback off and return to a bare `INSUFFICIENT DATA`.

Machines also show their real last-known status, with its age:

```
Last known status            STALE
Sold out or unavailable
Reported 230 days ago via a community tracker.
This is 230 days old, so it describes what was true then, not what is likely now.
```

### How this becomes a machine-specific forecast

Three paths, all already implemented:

1. **Let the schedule run.** Every 30-minute poll captures the current status.
   The observation fingerprint is machine + `lastUpdated`, so an unchanged
   status de-duplicates to one record while a genuine change becomes a new
   observation. Polling is what turns a current-state API into a time series.
2. **Add free credentials** for the high-volume sources. Reddit is a two-minute
   signup (`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`), and its adapter,
   parser and tests are already in place.
3. **Report from the machine page.** First-party reports are the strongest
   evidence there is and take effect immediately.

---

## How forecasting works

The target is **not** "when was this machine restocked?" but:

> P(product purchasable during window *t* | machine, history, recent reports, timing pattern)

### Observations

An observation is one timestamped statement about whether a machine could
dispense. Each carries an evidence weight from `config/forecast_config.yaml`:

| Evidence | Weight |
|---|---|
| Confirmed purchase | 1.00 |
| User report with photo | 0.95 |
| User "available" | 0.85 |
| User "not available" | 0.75 |
| Reliable timestamped community report | 0.65 |
| General community report | 0.40 |
| Third-party inferred | 0.25 |

A confirmed purchase is the strongest evidence available: it proves the machine
actually dispensed at that moment.

Each observation's effective weight is `source confidence × machine-match
confidence × recency decay`.

### Feature extraction

Computed per machine in the machine's local time (`America/Los_Angeles`):
counts and hit rates by hour / weekday / weekday-hour; minutes since the last
available, not-available, restock and confirmed purchase; minute-of-hour
pattern; recurring interval; nearby-machine activity; mean source and match
confidence.

### Minute-of-hour pattern

Reports cluster near a minute rather than landing on it exactly. Clustering runs
**on the circle of minutes**, so `:58, :59, :00, :01` is one cluster, not two.
Given `09:37, 10:36, 11:38, 12:37, 13:38` with a ±3 tolerance:

```json
{ "patternMinute": 37, "toleranceMinutes": 3, "support": 0.78, "sampleCount": 18 }
```

Below `minute_pattern_min_samples` no pattern is claimed.

### Interval detection

Gaps between consecutive positive events are tested against 30 / 60 / 90 / 120
minutes. Multiples count: if a machine runs hourly but nobody reported the 3pm
event, the 120-minute gap still supports a 60-minute cadence. Because 60 is a
multiple of 30, ties break toward the interval closest to the median observed
gap — so `12:37, 1:37, 2:37, 3:37` reports 60, and `12:12, 12:42, 1:12, 1:42`
reports 30. Nothing is called established below `interval_min_samples` and
`interval_min_support`.

### Recency decay

`weight = exp(-lambda × age_hours)`, lambda configurable (default 0.0058/hour,
a ~5-day half-life). This is what lets new evidence overturn an old pattern:
`tests/test_recency.py` includes a machine that used to dispense at `:37` and
now only at `:05`, and asserts the detected pattern switches — with a control
showing it does *not* switch when decay is disabled.

### Scoring

```
score = minute_pattern      × 0.30
      + interval            × 0.20
      + historical_hit_rate × 0.20
      + recency             × 0.15
      + weekday_hour        × 0.10
      + nearby_activity     × 0.05
```

All weights live in `forecast_config.yaml` and are validated to sum to 1.0 at
load time. The result is then scaled by:

- **sample size** — few observations shrink the score toward zero,
- **source confidence** — weak or loosely-matched evidence is discounted,
- **horizon** — `exp(-0.08 × hours_ahead)`, because a window six hours out rests
  on the same pattern but far more can change before it arrives.

Normalised to 0–100% and presented as a **Forecast score**, never as statistical
certainty.

### Nearby machines

Activity within 3 / 5 / 10 miles in the last 90 minutes is a **secondary**
signal at 0.05 weight. It never implies that a particular machine was restocked.

### Explainability

Every scored window carries its component breakdown and a plain-English
justification:

```
14 of 18 recent positive observations fell near :37 past the hour.
Most common interval between positive reports: 60 minutes (support 100%).
Last confirmed purchase was 132 minutes ago.
3 nearby machine(s) reported product in the last 90 minutes.
```

---

## How predictions differ from actual inventory

The forecast is an estimate from historical and community observations. It is
not an inventory feed, and no retailer or Pokémon system is queried for stock.
A high score means the machine has dispensed around this time before and was
recently confirmed active — not that product is there now.

---

## Parser architecture

Every adapter implements the same three methods, so sources are independently
replaceable and jobs never need to know which one they are talking to:

```python
class DataSource(Protocol):
    def fetch(self): ...
    def normalize(self, raw): ...
    def health_check(self): ...
```

Parsing is deliberately split from fetching. `parse_machines_payload`,
`parse_retailer_store_page`, `parse_listing` and `parse_community_post` are pure
functions tested against fixtures in `apps/ingestion/tests/fixtures/`:

- `pokemon_locator_bbox.json` — a real, unmodified API response for 98092
- `pokemon_locator_malformed.json` — degraded rows
- `safeway_store_page.html` — a real public store page extract
- `reddit_listing.json` — **synthetic**, because Reddit cannot be fetched

**A parser failure never crashes the pipeline.** Bad rows are dropped with a
warning, a broken post is skipped, a blocked source is recorded as skipped, and
the run continues. Retailer pages embed their profile JSON with no stable
container variable, so extraction anchors on a key and reads a balanced
object — durable across layout changes.

### Machine matching

Community reports say "Covington Fred Meyer", not a machine id. `MachineMatcher`
scores retailer, city, ZIP and alias matches additively; a literal machine id or
printed cabinet name (`Q01401`) is decisive. Below
`min_machine_match_confidence` (0.70) the observation is **kept as area-level
evidence but attributed to no machine**. Two identical stores in one city
produce a tie, and a tie is rejected rather than guessed.

### De-duplication

Observations get a deterministic fingerprint over source, source identifier,
machine, timestamp (minute resolution) and normalized text hash. Re-crawls,
cross-posts and mirrors collapse to one record, and the strongest copy survives.
`tests/test_dedup.py` asserts duplicates cannot inflate a machine past the
minimum-sample gate.

Only normalized fields plus a source URL are stored. Post bodies are reduced to
a hash and never republished.

---

## First-party reporting

Each machine page collects `AVAILABLE NOW` / `NOT AVAILABLE`, the product seen,
and whether the purchase succeeded. The timestamp is recorded automatically.

GitLab Pages is static hosting and cannot accept writes, so
`ObservationSubmissionService` stores reports in `localStorage` and says exactly
that:

> Local observation saved. Community synchronization will be enabled when the API backend launches.

It never claims a local report was uploaded. Set `VITE_SUBMISSION_ENDPOINT` and
the same service POSTs instead; a failed POST keeps the report and says it is
not yet synced. Dashboard components do not change when the backend arrives.

---

## How GitLab Pages gets updated data

```
Public sources → Python ingestion → normalize → forecast → JSON
                                                            ↓
                                          apps/web/public/data/
                                                            ↓
                                    build-web → pages → GitLab Pages
                                                            ↓
                                                    React dashboard
```

Published files:

```
/data/machines.json        machines, distances, verifications, search metadata
/data/observations.json    normalized observations (no raw text)
/data/forecasts.json       per-machine forecasts, windows, features, explanations
/data/source-health.json   per-source status and skip reasons
/data/generated-at.json    { "generatedAt": "..." }
```

The dashboard displays `Forecast data updated: 8 minutes ago` and re-reads the
bundle every 5 minutes.

### GitLab scheduled pipeline setup

1. **CI/CD → Schedules → New schedule**, cron `*/30 * * * *` (any interval; keep
   it aligned with `forecast.window_minutes`).
2. Target the default branch. Ingestion jobs only run when
   `$CI_PIPELINE_SOURCE == "schedule"`, so pushes and MRs stay fast.
3. To persist observation history across runs, create a project access token
   with `write_repository` and expose it as the masked CI variable
   `GITLAB_PUSH_TOKEN`. The `persist-data` job commits `data/` back with
   `[skip ci]`. Without the token the job is skipped and history survives only
   as pipeline artifacts.
4. Optionally add `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` (masked) to
   enable the community source.
5. **Settings → Pages** for the URL. `VITE_BASE_PATH` is set to
   `/$CI_PROJECT_NAME/` so the bundle and router resolve under the project path,
   and `index.html` is copied to `404.html` so deep links work.

Stages: `validate → test → ingest → forecast → build → deploy`.
Jobs: `lint:python`, `lint:web`, `config:validate`, `terraform:fmt`,
`test:python`, `test:web`, `refresh-machines`, `collect-public-observations`,
`generate-forecast`, `persist-data`, `build-web`, `pages`.

Caching: pip and npm keyed on their lockfiles; `.cache/http` carries
ETag/Last-Modified state between runs so unchanged pages return 304.

---

## GitHub Actions

The project ships CI for both hosts. `.gitlab-ci.yml` and `.github/workflows/`
run the same checks and the same three ingestion jobs; use whichever host the
repository lives on.

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | push, PR | ruff, config validation, pytest, eslint, vitest, build, `terraform fmt` |
| `ingest.yml` | every 30 min, manual | refresh machines, collect observations, build forecasts, commit the data back, then deploy |
| `pages.yml` | push to `main`, manual, or called by `ingest.yml` | build and publish to GitHub Pages |

One-time setup:

1. **Settings → Pages → Source: GitHub Actions.**
2. **Settings → Actions → General → Workflow permissions: Read and write**, so
   the scheduled job can commit refreshed data.
3. Optionally add `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` as repository
   secrets to enable the Reddit source. Without them it reports
   `SOURCE_SKIPPED` and contributes nothing.

Two details worth knowing:

- `VITE_BASE_PATH` is set to `/<repo>/` because project Pages are served from
  `https://<owner>.github.io/<repo>/`, and `index.html` is copied to `404.html`
  so client-side routes survive a refresh.
- A commit pushed with `GITHUB_TOKEN` does not trigger other workflows, so
  `ingest.yml` calls `pages.yml` directly rather than relying on its own data
  commit to set off a deploy.

**The schedule is the point.** The community status API exposes only each
machine's current state, so a single run yields at most one observation per
machine. History accumulates because the job runs every 30 minutes and
de-duplication keeps an unchanged status from being counted twice.

---

## Configuration

### How to disable a source

Set `enabled: false` in `config/sources.yaml`:

```yaml
sources:
  reddit:
    enabled: false
```

It disappears from every job and is reported as `DISABLED` in
`source-health.json` — never silently absent. Per-source `rate_limit_seconds`,
`timeout_seconds`, `max_retries`, `user_agent` and `respect_robots` are all
configurable there.

### How to add another source

1. Add a class in `apps/ingestion/pokevend/sources/` implementing `fetch`,
   `normalize` and `health_check`. Subclass `CommunityObservationSource` for
   observations and you inherit the text parsing.
2. Keep parsing in a **pure function** taking a payload and returning models, so
   it is testable without network access.
3. Register it in `config/sources.yaml` with an `authority` and `enabled: false`
   to start.
4. Wire it into `build_community_sources` (or `refresh_machines` for discovery).
5. Save a sanitized fixture under `tests/fixtures/` and test extraction,
   classification, malformed input and missing fields.
6. Confirm the source permits automated access. If it does not, leave it
   disabled and log `SOURCE_SKIPPED`.

### Tuning the forecast

Everything is in `config/forecast_config.yaml` — scoring weights, evidence
weights, window size, minimum samples, tolerances, decay rates, nearby radii.
No magic numbers in source code. Invalid configuration fails at load time
(`config:validate` in CI), not silently at scoring time.

---

## AWS migration

The ingestion package has no GitLab-specific code. Jobs are plain functions over
a `DataStore` interface, so a Lambda handler is a wrapper:

```python
from pokevend.jobs import refresh_machines

def handler(event, context):
    return {"machines": refresh_machines.run(verify=True)}
```

Target architecture:

```
EventBridge → Lambda (discovery / community ingestion) → SQS
           → Normalization Lambda → DynamoDB → Forecast service
           → API Gateway → FastAPI → React → CloudFront
```

Migration order:

1. **DynamoDB** (`modules/database`) — implement `DataStore`'s methods against
   the tables. Access patterns already match: machines by id, observations by
   `machineId` + `observedAt`, fingerprint as a unique key for de-duplication.
2. **Ingestion Lambdas** (`modules/ingestion`) — EventBridge replaces the GitLab
   schedule. **Source adapters, normalizers and the forecast engine are
   unchanged.**
3. **Queues** (`modules/queues`) — SQS between fetch and normalize, with a DLQ.
4. **API** (`modules/api`) — FastAPI exposing `POST /api/v1/observations`. Point
   `VITE_SUBMISSION_ENDPOINT` at it; `ObservationSubmissionService` starts
   syncing with no component changes.
5. **Frontend** (`modules/frontend`) — S3 + CloudFront. The built bundle is
   identical; only `VITE_BASE_PATH` changes.
6. **Auth** (`modules/auth`) — Cognito, so a reporter with history can carry
   more weight than an anonymous one.
7. **Monitoring** (`modules/monitoring`) — CloudWatch alarms on ingestion
   errors, a non-empty DLQ and stale forecasts. Same rule as `source-health.json`:
   ingestion never fails silently.

`terraform fmt -check -recursive` and `terraform validate` both pass today.
**Nothing is provisioned for the GitLab Pages MVP.**

The natural next step after this MVP is GitLab Pages plus a small AWS write API
for user reports only — that yields real crowdsourced data immediately while the
rest of the application stays static and cheap.

---

## Design

The look is "modern TCG": cues taken from the cards themselves rather than from
characters or logos. A Poké Ball is drawn as SVG geometry at 11% opacity behind
the hero, machine cards carry a thin accent rule across the top like a card
frame with a very restrained holographic sweep on hover, and headings use
Outfit — a geometric sans with softly rounded terminals — while body copy stays
on the system stack. No mascots, no comic type.

Theme tokens are declared once using `light-dark()`, so the OS setting works out
of the box and `<html data-theme="dark">` overrides it without a second copy of
the palette.

The data colours were **not** chosen by eye. They were run through the palette
validator for lightness band, chroma floor, colour-vision separation and
contrast against each surface, in both modes:

| Mode | Accent | Gold | Good | Bad | Result |
|---|---|---|---|---|---|
| Light | `#2a4d9b` | `#9a6c0f` | `#0d7d63` | `#bd2a20` | all six checks pass |
| Dark | `#5f7ce4` | `#b3862a` | `#1f9575` | `#d95751` | all six checks pass |

The first attempt failed two of them — red/green were 6.2 ΔE apart under deutan
simulation, and the gold sat at 2.74:1 against white — so the green was stepped
toward teal and the gold darkened until both passed. Red and green are never the
only signal either: every status also carries a word.

Gold is reserved for exactly one thing, the machine-specific headline number. A
network-pattern figure is deliberately smaller and in muted ink so the two can
never be mistaken for each other.

The forecast chart follows the same rules: single series so no legend, zero
baseline with a clean adaptive ceiling (a fixed 0–100% squashed a forecast that
never exceeds 25%), one direct label on the selected bar rather than a number
above every column, and recessive grid and axes.

---

## Tests

```bash
pytest          # 265 tests
npm run test    # 60 tests
```

Coverage of note: radius boundary cases (9.9 / 10.0 / 10.1 miles) and direction
independence; city-name independence; fixture-based parser tests including
malformed and missing-field input; machine matching and ambiguity rejection;
de-duplication and its effect on sample counts; minute clustering including the
hour boundary; interval detection including the 30-vs-60 ambiguity; recency
decay overturning a stale pattern; `INSUFFICIENT_DATA` emitting no probability;
robots.txt enforcement and no-retry-on-403; local reports never reported as
uploaded.

---

## Disclaimer

**Independent community forecasting tool.**

Not affiliated with, endorsed by, or operated by The Pokémon Company
International or participating retailers.

Availability forecasts are estimates based on historical and community
observations and do not guarantee inventory or successful purchase.
