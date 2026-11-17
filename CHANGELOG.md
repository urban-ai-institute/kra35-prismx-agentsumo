# Changelog

All notable changes to AgentSUMO are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).
Versions below refer to the publicly released `agentsumo-mcp` PyPI package;
the AgentSUMO framework (this repository) tracks the same cadence and is
currently at framework version 0.1.0.

## [Unreleased]

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
