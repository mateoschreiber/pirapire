import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pirapire"
    app_env: str = "local"
    app_timezone: str = "America/Asuncion"
    app_public_url: str = ""
    database_url: str = "sqlite:////app/data/pirapire.db"
    log_level: str = "INFO"

    # External data sources (all optional; empty means "not configured").
    football_data_api_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_competitions: str = "WC,CL,PL,BL1,SA,PD,FL1"
    football_data_request_delay_seconds: float = 7.0
    football_data_max_competitions_per_run: int = 3
    football_data_respect_retry_after: bool = True
    football_data_cache_ttl_seconds: int = 300
    football_data_sync_wc_squads: bool = True
    riot_api_key: str = ""
    thesportsdb_api_key: str = ""
    thesportsdb_free_key: str = "123"
    thesportsdb_request_delay_seconds: float = 2.0
    thesportsdb_cache_ttl_seconds: int = 900
    thesportsdb_max_entities_per_run: int = 5
    riot_default_platform: str = "la2"
    riot_default_region: str = "americas"
    riot_request_delay_seconds: float = 1.25
    riot_cache_ttl_seconds: int = 300
    riot_max_identities_per_run: int = 5
    riot_matches_per_identity: int = 5
    riot_esports_access: str = ""
    leaguepedia_user_agent: str = "PirapireLocal/1.0"

    openligadb_league_shortcut: str = ""
    openligadb_season: str = ""
    openligadb_base_url: str = "https://api.openligadb.de"

    datadragon_base_url: str = "https://ddragon.leagueoflegends.com"
    datadragon_locale: str = "es_MX"

    sync_default_lookback_days: int = 45
    sync_default_lookahead_days: int = 21

    http_timeout_connect: float = 5.0
    http_timeout_read: float = 20.0
    http_timeout_write: float = 5.0
    http_timeout_pool: float = 5.0

    # Aposta.LA (placeholder in Fase 4A: no browser worker configured yet)
    aposta_sync_enabled: bool = True
    aposta_browser_worker_url: str = ""
    aposta_sync_mode: str = "csv_folder"
    aposta_json_url: str = ""
    aposta_fetch_urls: str = "https://api.aposta.la/apuestas/deporte/1/4"
    aposta_browser_fetch_enabled: bool = False
    aposta_browser_fetch_url: str = "https://aposta.la/bets"
    aposta_browser_fetch_esports: str = "https://aposta.la/bets#sports-hub/esports"

    aposta_import_dir: str = "/app/data/imports/aposta"
    aposta_archive_dir: str = "/app/data/imports/archive"
    aposta_error_dir: str = "/app/data/imports/errors"
    auto_recommend_on_aposta_sync: bool = True
    auto_sync_sports_before_recommend: bool = True
    source_stale_hours: int = 12
    recommender_event_grace_minutes: int = 30
    leaguepedia_sync_enabled: bool = True
    leaguepedia_base_url: str = "https://lol.fandom.com/wiki/Special:CargoExport"
    leaguepedia_import_lookback_days: int = 21
    leaguepedia_import_lookahead_days: int = 14

    # LoL historical competitive data
    lol_history_enabled: bool = True
    lol_history_start_year: int = 2021
    lol_history_end_year: str = "auto"
    lol_history_active_leagues: str = "LCK,LPL,LEC,LCS,CBLOL,LCP,MSI,WORLDS,FIRST_STAND"
    lol_history_include_legacy: bool = True
    lol_history_legacy_leagues: str = "LTA,LLA,PCS,VCS,LJL,LCO,TCL,LCL"
    lol_history_import_on_startup: bool = False
    lol_history_refresh_hours: int = 24
    lol_history_min_games_team: int = 8
    lol_history_min_games_player: int = 5
    lol_history_recent_games_window: int = 20
    lol_history_patch_weighting: bool = True
    lol_history_patch_half_life: int = 3
    lol_history_source_priority: str = "oracles_elixir,lolesports,leaguepedia"
    lol_aposta_min_match_confidence: float = 0.70
    lol_history_import_dir: str = "/app/data/imports/oracles"
    lol_history_allow_download: bool = False
    lol_history_download_url_template: str = ""

    # Recommendation engine
    recommender_default_mode: str = "probability"
    recommender_min_probability: float = 0.55
    recommender_max_combo_legs: int = 3
    recommender_max_suggestions: int = 20
    recommender_min_edge: float = 0.02
    recommender_min_ev: float = 0.0
    recommender_only_positive_ev: bool = False
    recommender_min_match_confidence: float = 0.70
    recommender_include_stale_odds: bool = False
    build_commit: str = "unknown"
    integration_master_key_path: str = "/app/data/secrets/integration-master.key"
    config_admin_password_path: str = "/app/data/secrets/config-admin.password"
    config_session_key_path: str = "/app/data/secrets/config-session.key"
    config_session_ttl_seconds: int = 1800
    config_login_rate_limit: int = 5
    config_test_rate_limit: int = 10
    model_config = SettingsConfigDict(
        env_file=os.getenv("PIRAPIRE_ENV_FILE", ".env"),
        extra="ignore",
    )

    @property
    def competitions_list(self) -> list[str]:
        return [
            c.strip() for c in self.football_data_competitions.split(",") if c.strip()
        ]


settings = Settings()
