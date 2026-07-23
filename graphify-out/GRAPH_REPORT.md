# Graph Report - .  (2026-07-23)

## Corpus Check
- 143 files · ~179,577 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 621 nodes · 1217 edges · 55 communities (41 shown, 14 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 101 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Team Logos & Brand Assets
- Match Events & Odds Models
- Data Import Pipeline
- Frontend JavaScript
- Core LoL Domain Models
- Oracle's Elixir Importer
- Database & Migrations
- Deployment & Architecture Docs
- Config, HTTP & Utils
- Background Worker Jobs
- Graphify Skill Reference
- Match Statistics Engine
- Team Logos (Worlds Batch)
- Team Logo Sync Service
- README & Base Templates
- Graphify Query & Traversal
- CI & Agent Config
- Extraction Spec Rules
- Graphify Pipeline Concepts
- API Pydantic Schemas
- Source Base Classes
- Team Logos (LCK)
- Team Logos (LPL / Mixed)
- Team Logos (CBLOL A)
- Install Script
- Graphify Update & Cache
- Team Logos (LEC)
- Team Logos (LPL A)
- Team Logos (LTA North)
- OpenCode Plugin Config
- OpenWiki Domain Docs
- Team Logos (LCP)
- Team Logos (LTA South)
- Team Logos (CBLOL B)
- Graphify OpenCode Plugin
- Team Logos (BNK/DPlus)
- Team Logos (PCS)
- Favicon Asset
- Team Logo (Furia)
- Team Logo (GAM)
- Team Logo (Invictus)
- Team Logo (LCS)
- Team Logo (MVK)
- Team Logo (NaVi)
- Team Logo (Deep Cross)
- Team Logo (First Stand)
- Team Logo (Fnatic)
- OpenWiki DataDragon Docs

## God Nodes (most connected - your core abstractions)
1. `LolMatchEvent` - 23 edges
2. `_import_csv_file()` - 22 edges
3. `Graphify Knowledge Graph Tool` - 22 edges
4. `SourceRun` - 19 edges
5. `LolGameHistory` - 17 edges
6. `synchronize_known_aliases()` - 17 edges
7. `Worlds Tournament Logo` - 16 edges
8. `LolTeamGameStat` - 15 edges
9. `_source()` - 15 edges
10. `el()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `CLAUDE.md Agent Instructions` --semantically_similar_to--> `OpenWiki in AGENTS.md`  [INFERRED] [semantically similar]
  CLAUDE.md → AGENTS.md
- `Pirapire Jinja2 Base Template` --conceptually_related_to--> `Pirapire Analytics Platform`  [INFERRED]
  backend/app/templates/base.html → README.md
- `Graphify in AGENTS.md` --conceptually_related_to--> `Graphify Knowledge Graph Tool`  [EXTRACTED]
  AGENTS.md → .opencode/skills/graphify/SKILL.md
- `LoL Metrics Engine Service` --semantically_similar_to--> `Statistics Engine (on-demand)`  [INFERRED] [semantically similar]
  openwiki/architecture/overview.md → openwiki/domain/lol-metrics.md
- `Docker Compose Deployment Procedure` --conceptually_related_to--> `pirapire_app Docker Service`  [INFERRED]
  openwiki/operations/runbook.md → docker-compose.yml

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Graphify Export Format Group** — _opencode_skills_graphify_references_exports_graphify_wiki, _opencode_skills_graphify_references_exports_graphify_neo4j, _opencode_skills_graphify_references_exports_graphify_falkordb, _opencode_skills_graphify_references_exports_graphify_mcp [INFERRED 0.85]
- **Graphify Core Pipeline Steps** — _opencode_skills_graphify_skill_ast_extraction, _opencode_skills_graphify_skill_semantic_extraction, _opencode_skills_graphify_skill_community_detection, _opencode_skills_graphify_skill_god_nodes, _opencode_skills_graphify_skill_surprising_connections [EXTRACTED 1.00]
- **Graphify Query Command Family** — _opencode_skills_graphify_references_query_graphify_query, _opencode_skills_graphify_references_query_graphify_path, _opencode_skills_graphify_references_query_graphify_explain [EXTRACTED 1.00]
- **Data Ingestion to Odds Pipeline** — openwiki_integrations_overview_leaguepedia, openwiki_integrations_overview_oracles_elixir, openwiki_domain_lol_metrics_lol_match_event, openwiki_domain_lol_metrics_lol_game_history, openwiki_domain_lol_metrics_lol_series, openwiki_domain_lol_metrics_statistics_engine, openwiki_domain_lol_metrics_estimated_market [INFERRED 0.95]
- **Two-Container Docker Deployment Pattern** — docker_compose_pirapire_app, docker_compose_pirapire_worker, docker_compose_healthcheck, openwiki_architecture_overview_two_container_deployment, openwiki_architecture_overview_sqlite_concurrent_access [EXTRACTED 1.00]
- **LPL (China) Teams** — backend_app_static_team_logos_anyone_s_legend, backend_app_static_team_logos_beijing_jdg_esports, backend_app_static_team_logos_bilibili_gaming, backend_app_static_team_logos_edward_gaming [INFERRED]
- **LTA North Teams** — backend_app_static_team_logos_cloud9_kia, backend_app_static_team_logos_dignitas, backend_app_static_team_logos_disguised, backend_app_static_team_logos_flyquest [INFERRED]
- **LTA South Teams** — backend_app_static_team_logos_cnb_legends, backend_app_static_team_logos_dn_soopers, backend_app_static_team_logos_fluxo_w7m [INFERRED]

## Communities (55 total, 14 thin omitted)

### Community 0 - "Team Logos & Brand Assets"
Cohesion: 0.02
Nodes (85): ag-al, anyone-s-legend, beijing-jdg-esports, bilibili-gaming, bnk-fearx, cloud9, cloud9-kia, cnb-legends (+77 more)

### Community 1 - "Match Events & Odds Models"
Cohesion: 0.08
Nodes (37): LolMatchEvent, LolOddsSnapshot, LolTeamAlias, LolTeamOdd, Upcoming or finished professional LoL series., Immutable capture of general winner odds for a series., One team selection inside a snapshot., _competition_code() (+29 more)

### Community 2 - "Data Import Pipeline"
Cohesion: 0.13
Nodes (48): DataSource, ImportBatch, ImportError, SourceRun, aliases(), _batch_view(), _config(), _configuration_view() (+40 more)

### Community 3 - "Frontend JavaScript"
Cohesion: 0.15
Nodes (40): averageValue(), el(), esc(), fetchJSON(), fmtDate(), fmtNumber(), fmtOdds(), fmtPct() (+32 more)

### Community 4 - "Core LoL Domain Models"
Cohesion: 0.10
Nodes (30): LolChampion, LolDataCoverage, LolLeague, LolLeagueAlias, LolMatchStatisticsReadModel, LolPatch, LolPlayer, LolPlayerExternalIdentity (+22 more)

### Community 5 - "Oracle's Elixir Importer"
Cohesion: 0.11
Nodes (31): LolGameHistory, LolPlayerGameStat, LolTeamGameStat, _bool(), _import_csv_file(), import_oracles_inbox(), _int(), _normalized_row() (+23 more)

### Community 6 - "Database & Migrations"
Cohesion: 0.10
Nodes (16): get_session(), init_db(), Session, lifespan(), _add(), _columns(), Session, Preserve a pre-LoL table that reuses a current table name.      Earlier versions (+8 more)

### Community 7 - "Deployment & Architecture Docs"
Cohesion: 0.07
Nodes (29): Docker Health Check (curl /health), pirapire_app Docker Service, pirapire_worker Docker Service, APScheduler Background Worker, LoL Metrics Engine Service, Phase 1 Refactor (commit b8e1b04), Series Builder Service, Sources Admin API (+21 more)

### Community 8 - "Config, HTTP & Utils"
Cohesion: 0.12
Nodes (20): Settings, get_client(), Shared httpx wrapper for all external API calls., Fetch JSON returning a structured result (never raises).      Returns {"ok": b, request_json(), safe_get(), safe_get_json(), format_local() (+12 more)

### Community 9 - "Background Worker Jobs"
Cohesion: 0.21
Nodes (21): WorkerHeartbeat, Session, rebuild_series(), _finish_remote_run(), job_heartbeat(), job_import_odds(), job_import_oracles(), job_precompute_stats() (+13 more)

### Community 10 - "Graphify Skill Reference"
Cohesion: 0.11
Nodes (18): Graphify add URL Command, Graphify Watch Mode (--watch), Graphify Token-Reduction Benchmark, Graphify FalkorDB Export, Graphify MCP Server, Graphify Neo4j Export, Graphify Wiki Export, Graphify Cross-Repo Graph Merge (+10 more)

### Community 11 - "Match Statistics Engine"
Cohesion: 0.27
Nodes (15): LolSeries, compute_match_statistics(), _estimated_market(), _players(), precompute_upcoming_stats(), datetime, Session, Traceable, series-based LoL statistics. (+7 more)

### Community 12 - "Team Logos (Worlds Batch)"
Cohesion: 0.30
Nodes (17): Shenzhen Ninjas in Pyjamas Logo, Shifters Logo, Shopify Rebellion Logo, SK Gaming Logo, Suzhou LNG Esports Logo, T1 Logo, Team Heretics Logo, Team Liquid Alienware Logo (+9 more)

### Community 13 - "Team Logo Sync Service"
Cohesion: 0.19
Nodes (13): apply_display_aliases(), _entries(), Local cache for official team logos published by LoL Esports., Map provider spelling variants to an already cached official logo., Cache assets published by a team when it is not in Riot's current feed., Refresh the local cache from official Riot LoL Esports pages., sync_known_official_assets(), sync_official_team_logos() (+5 more)

### Community 14 - "README & Base Templates"
Cohesion: 0.18
Nodes (11): Pirapire Live Clock Component, Pirapire Jinja2 Base Template, Data Dragon Static Metadata Source, Docker Compose Deployment, FastAPI, Leaguepedia Cargo Data Source, LoL Odds CSV Format, Oracle's Elixir Data Source (+3 more)

### Community 15 - "Graphify Query & Traversal"
Cohesion: 0.20
Nodes (10): Graphify BFS Traversal, Graphify DFS Traversal, Graphify Explain Command, Graphify Path Command, Graphify Query CLI, Graphify LESSONS.md Reflections, Graphify save-result Feedback Loop, Graphify Constrained Query Expansion (+2 more)

### Community 16 - "CI & Agent Config"
Cohesion: 0.25
Nodes (8): LangSmith Tracing, OpenRouter API Provider, OpenWiki Documentation Tool, OpenWiki Update GitHub Actions Workflow, AGENTS.md Agent Instructions, Graphify in AGENTS.md, OpenWiki in AGENTS.md, CLAUDE.md Agent Instructions

### Community 17 - "Extraction Spec Rules"
Cohesion: 0.29
Nodes (7): Graphify Confidence Score Rubric, Graphify Cross-Language Call Guard, Graphify Extraction Subagent, Graphify Hyperedges, Graphify Node ID Format Convention, Graphify Semantic Similarity Edge, Graphify source_file Verbatim Rule

### Community 18 - "Graphify Pipeline Concepts"
Cohesion: 0.29
Nodes (7): AST Structural Extraction, Graphify Community Detection, Graphify Extraction Pipeline, Gemini API Backend, Graphify God Nodes Analysis, Semantic Extraction (LLM), Graphify Surprising Connections Analysis

### Community 19 - "API Pydantic Schemas"
Cohesion: 0.48
Nodes (6): MatchResponse, OddsImportRequest, BaseModel, StatisticsResponse, UpcomingMatch, UpcomingResponse

### Community 20 - "Source Base Classes"
Cohesion: 0.38
Nodes (5): parse_iso_datetime(), datetime, Shared helpers for source connectors., SyncCounters, utcnow()

### Community 21 - "Team Logos (LCK)"
Cohesion: 1.00
Nodes (6): Team Logo: Gen.G Esports, Team Logo: Hanjin Brion, Team Logo: Hanwha Life Esports, Team Logo: Kiwoom DRX, Team Logo: KT Rolster, League Logo: LCK

### Community 22 - "Team Logos (LPL / Mixed)"
Cohesion: 0.47
Nodes (6): Team Logo: LGD Gaming, League Logo: LPL, Team Logo: Movistar KOI, Tournament Logo: MSI, Team Logo: Nongshim RedForce, Team Logo: Oh My God

### Community 23 - "Team Logos (CBLOL A)"
Cohesion: 1.00
Nodes (5): Team Logo: Los Grandes, Team Logo: LOUD, Team Logo: MIBR, Team Logo: paiN Gaming, Team Logo: RED Kalunga

### Community 24 - "Install Script"
Cohesion: 0.70
Nodes (4): err(), log(), ok(), install.sh script

### Community 25 - "Graphify Update & Cache"
Cohesion: 0.50
Nodes (4): Graphify build_merge Function, Graphify Code-Only Update Optimization, Graphify detect_incremental Function, Graphify Incremental Update (--update)

### Community 26 - "Team Logos (LEC)"
Cohesion: 1.00
Nodes (4): Team Logo: G2 Esports, Team Logo: GiantX, Team Logo: Karmine Corp, League Logo: LEC

### Community 27 - "Team Logos (LPL A)"
Cohesion: 1.00
Nodes (4): Team Logo: Anyone's Legend, Team Logo: JD Gaming, Team Logo: Bilibili Gaming, Team Logo: EDward Gaming

### Community 28 - "Team Logos (LTA North)"
Cohesion: 1.00
Nodes (4): Team Logo: Cloud9, Team Logo: Dignitas, Team Logo: Disguised, Team Logo: FlyQuest

### Community 29 - "OpenCode Plugin Config"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 30 - "OpenWiki Domain Docs"
Cohesion: 0.50
Nodes (4): League Catalog, Team Aliases Service, Competition Classification, Official 2026 Competition Rosters

### Community 31 - "Team Logos (LCP)"
Cohesion: 1.00
Nodes (3): Team Logo: Fukuoka SoftBank Hawks Gaming, Team Logo: Ground Zero Gaming, League Logo: LCP

### Community 32 - "Team Logos (LTA South)"
Cohesion: 1.00
Nodes (3): Team Logo: Leviatán, Team Logo: Lyon Gaming, Team Logo: Sentinels

### Community 33 - "Team Logos (CBLOL B)"
Cohesion: 1.00
Nodes (3): Team Logo: CNB Legends, Team Logo: DN Soopers, Team Logo: Fluxo W7M

## Knowledge Gaps
- **164 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `ag-al`, `anyone-s-legend`, `beijing-jdg-esports` (+159 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LolMatchEvent` connect `Match Events & Odds Models` to `Data Import Pipeline`, `Match Statistics Engine`, `Core LoL Domain Models`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `_import_csv_file()` connect `Oracle's Elixir Importer` to `Background Worker Jobs`, `Data Import Pipeline`, `Match Events & Odds Models`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `sync_official_team_logos()` connect `Team Logo Sync Service` to `Background Worker Jobs`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `LolMatchEvent` (e.g. with `get_match()` and `upcoming_matches()`) actually correct?**
  _`LolMatchEvent` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `_import_csv_file()` (e.g. with `LolGameHistory` and `LolPlayerGameStat`) actually correct?**
  _`_import_csv_file()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `ag-al` to the rest of the system?**
  _164 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Team Logos & Brand Assets` be split into smaller, more focused modules?**
  _Cohesion score 0.023255813953488372 - nodes in this community are weakly interconnected._