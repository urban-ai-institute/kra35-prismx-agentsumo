# Changelog

All notable changes to AgentSUMO are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).
Versions below refer to the publicly released `agentsumo-mcp` PyPI package;
the AgentSUMO framework (this repository) tracks the same cadence and is
currently at framework version 0.1.0.

## [Unreleased]

## [0.1.3] — 2026-11-17

### Added
- Fail-fast environment validation at web startup. Missing
  `ANTHROPIC_API_KEY`, `MAPBOX_TOKEN`, `SUMO_HOME`, or an invalid
  `SUMO_HOME/bin/sumo` path now logs an actionable ERROR line before
  the first chat message, instead of surfacing as a generic MCP
  connection failure.
- Standalone vs full-framework clarification on the PyPI README so
  Claude Desktop users know the Planner Agent + IPP live in the
  framework repository, not in the standalone server.
- Comment markers above every `agentsumo.server` import in the
  framework explaining that the fallback supports the dev-ko branch.

### Changed
- Manhattan tutorial spells out that *Real OD* mode means
  `trip_type="real"` (coordinate-based OD CSV) rather than RandomOD.
- README places a `<version>` placeholder in the macOS Eclipse SUMO
  `SUMO_HOME` example so users on SUMO 1.25 or later don't have to
  guess.
- Token-file fallback (`claude_api.txt`, `mapbox_token.txt`) now emits
  a `DeprecationWarning` at import time and the README marks it for
  removal in 0.2.0; the `.env` workflow is the only supported path
  going forward.
- OSM extraction tries Overpass over HTTP first, then a cached or
  downloaded Geofabrik PBF cut with osmium, replacing the old osmGet.py
  path (which could report success without writing the file).
- `sumo_runner` fails fast with SUMO's own error message and status
  `"error"` (no output paths) instead of retrying for ~60 s and returning
  `"warning"` with paths to files that were never written. Each run
  writes SUMO's messages to `<prefix>_sumo_<timestamp>.log`, returned as
  `sumo_log`; `replay_file` is returned at the top level.
- `xml_to_sqlite_tool`: an existing `simulation_id` is replaced (its rows
  deleted from every table, in one transaction); without an id a new
  unused auto id is generated; other simulations are never skipped or
  deleted. Edge metrics SUMO did not write are stored as NULL, not 0.
- `simulation_report_tool` reports total fuel in kg (SUMO writes
  `fuel_abs` in mg); it was labelled litres.
- RandomOD writes one file per demand level
  (`<net>_<condition>.trips.xml`), so generating "light" and "heavy"
  no longer overwrites one with the other.
- Without `AGENTSUMO_MCP_OUTPUT_BASE`, outputs fall back to
  `~/agentsumo-output` when the working directory is not writable (MCP
  hosts often start servers in `/`). A relative value is made absolute.
- The CLI (`chat.py`) enables the Filesystem MCP, which the rerouter,
  VSS and vType guide workflows require. It needs Node.js 18+ with npx;
  without it the agent warns and continues.
- The agent's default `max_tokens` is 16000 (thinking budget 10000);
  4096 left about 1,000 tokens for the visible reply.

### Fixed
- `mcp` is pinned below 2.0 in both the framework and `agentsumo-mcp`.
  mcp 2.x (August 2026) removed FastMCP, so on a fresh install the
  AgentSUMO MCP server failed to import and the agent had no SUMO
  tools. Existing environments with mcp 1.x were unaffected.
- `traci` is now a declared dependency. sumolib bundled it up to 1.25;
  from 1.26 it ships separately, so a fresh install had no `traci` and
  every `sumo_runner` call failed with "No module named 'traci'".
- SUMO tool and data paths resolve on every install layout. They were
  built as `SUMO_HOME/share/sumo/tools`, which only exists for the macOS
  framework installer, so with the README's Homebrew, Windows and Linux
  `SUMO_HOME` values RandomOD and zone OD trip generation, traffic-light
  tools, every plot, and `net_convert` outside Korea failed.
- SUMO's Python scripts run with the server's own interpreter instead of
  a bare `python` / `python3` from PATH (macOS has no `python`, and MCP
  hosts often start servers with a minimal PATH).
- Plotting tools no longer hang: SUMO's plot scripts call `plt.show()`
  unless given `--blind`, which opened a window and blocked the tool
  until it was closed. `visualize_edgedata_tool` also returns the image it
  actually wrote instead of the `..._%s.png` pattern.
- The SQLite MCP Server now installs from PyPI as the
  `mcp-server-sqlite>=2025.4.25` dependency. The client used to launch
  it from a `sqlite-mcp-server/` folder that was git-ignored and never
  shipped, so on a fresh clone the connection failed, the agent logged
  the error and continued, and every `read_query` call returned "SQLite
  MCP is not connected".
- `ensure_vehicle_types_default` surfaces an actionable
  `PermissionError` ("set AGENTSUMO_MCP_OUTPUT_BASE to a writable
  directory") instead of failing silently when the destination cannot
  be created.
- Agent state: a failed tool no longer overwrites state (a failed
  `xml_to_sqlite_tool` used to store a `None` simulation id that broke
  every later turn, even after restart); the SQLite MCP reconnects when
  the analysis DB changes instead of querying the previous area's DB;
  every new base network becomes the policy baseline; the context lists
  only the current DB's simulations; route files written by vehicle,
  flow and vType tools are tracked.
- A reply cut off at `max_tokens` no longer leaves a dangling `tool_use`
  in history (which made every later API call fail until `reset`).
- `chat.py` loads `.env` with python-dotenv; its own parser kept quotes
  and inline comments in values (breaking the API key or `SUMO_HOME`).
- Shutdown closes MCP clients in reverse order; `quit` with a database
  open used to end in a CancelledError traceback.
- The system prompt no longer names tools that do not exist
  (`tls_optimize`, `reduce_lanes`, ...), and its worked example stores
  results with `xml_to_sqlite_tool` before querying them.
- `sumo_runner` with only a trip file wrote `<trip-files>`, which SUMO
  rejects; trips now load through `route-files`. SUMO's console output
  and TraCI's retry messages no longer leak into the MCP stdio channel.
- Vehicles and flows added by `vehicle_generation_tool` and
  `flow_generation_tool` were appended out of departure order, so SUMO
  silently dropped them and the scenario matched the baseline. The route
  file is now kept sorted.
- `reduce_lanes_tool` recomputes only the junctions the edited edges
  touch, keeping their edge-to-edge movements; it used to rebuild every
  junction and signal program, changing unrelated intersections (and OSM
  turn restrictions) and contaminating policy comparisons. Edits that
  match no edge now return an error instead of success.
- `simulation_report_tool`: no crash on a scenario with 0 completed
  trips, no `NameError` when the stored network cannot be read, and no
  empty DB file created for a wrong `db_path`.
- `xml_to_sqlite_tool` creates missing tables in an existing or 0-byte
  database file instead of failing with "no such table".
- RandomOD checks randomTrips' exit code instead of returning a stale
  trips file as success; zone OD matches numeric zone ids; netconvert,
  duarouter, polyconvert and od2trips failures include their stderr.
- `agentsumo-mcp` declares `matplotlib`, which the visualization tools
  need; a standalone install had none, so every plot failed.
- The framework package no longer bundles a second copy of
  `agentsumo_mcp`, and ships its prompt template and guides, so a
  non-editable install works.

## [0.1.2] — 2026-06-05

### Added
- Packaged default `vehicle_types.add.xml` (passenger / electric /
  gasoline) under `agentsumo_mcp/defaults/`. Auto-seeded into the
  simulation directory on the first `sumo_runner` call and at
  `AgentSUMO.start()`, so a fresh `pip install agentsumo-mcp` or
  `git clone` works without manual setup.
- `agentsumo_mcp.utils.defaults.ensure_vehicle_types_default()` helper.
- `output/` directory layout (eight categories with `.gitkeep`) tracked
  in the repository for discoverability on clone.
- `CITATION.cff` for the GitHub "Cite this repository" widget and
  third-party citation tools.
- GitHub Actions tests workflow (Ubuntu + macOS, Python 3.12, pytest +
  Sphinx `-W` doc build) and a build-status badge on the README.

### Changed
- Web UI file explorer and the MCP server now resolve outputs through
  `AgentSUMOConfig.OUTPUT_DIR` (= `PROJECT_ROOT/output`), so new
  simulation runs appear in the web tree without symlinks.
- `LICENSE` rewritten as a single-line SPDX-conformant copyright with
  Urban AI Institute + Spacetime Intelligence Lab affiliations. PEP 639
  `license = "MIT"` + `license-files` adopted in both pyproject files,
  build backend pinned to `setuptools>=77.0`. GitHub now auto-detects
  MIT.
- Docs footer credit moved from KAIST Graduate School of Data Science
  to KAIST Urban AI Institute + Spacetime Intelligence Lab (STIL).
- README, docs, and PyPI README aligned to the CEUS manuscript: 26 MCP
  tools across the paper's five categories; SQLite MCP six-tool
  surface; Filesystem MCP thirteen-tool surface; the three Filesystem
  MCP guide files normalized to `rerouter.md` / `vss.md` / `vtype.md`.
- macOS Homebrew install command unified to `brew install sumo`
  (formula) so the `SUMO_HOME` example in the README matches the
  installed layout.

### Fixed
- SUMO MCP client server-module probe survives the absent
  `agentsumo.server` parent on the public `main` branch
  (`importlib.util.find_spec` previously raised `ModuleNotFoundError`
  before the alternative branch could fire, breaking `python web.py`
  and `python chat.py` end-to-end on a fresh checkout).
- Chat avatar PNG now ships with a transparent background driven by a
  connected-component pass so the dark chat UI no longer renders a
  white card behind the bot icon.

## [0.1.1] — 2026-05-31

### Added
- arXiv badge, unified Eclipse SUMO link, and BibTeX citation block on
  the PyPI README.

### Changed
- PyPI metadata refreshed (Homepage, Documentation, Repository, Issues)
  so the sidebar links resolve correctly.
- Server registered on the official MCP Registry under
  `io.github.mw-jeong/agentsumo-mcp`.

## [0.1.0] — 2026-05-31

### Added
- Initial public release of the AgentSUMO MCP Server.
- 26 tools across Scenario Generation, Policy Experimentation, Result
  Analysis, Visualization, and Utility categories.
- Published on PyPI as `agentsumo-mcp` and on the official MCP Registry.
- AgentSUMO framework (Planner Agent + Interactive Planning Protocol +
  web interface) hosted at
  [github.com/mw-jeong/AgentSUMO](https://github.com/mw-jeong/AgentSUMO).
