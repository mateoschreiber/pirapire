from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pirapire"
    app_env: str = "local"
    app_timezone: str = "America/Asuncion"
    app_public_url: str = ""
    database_url: str = "sqlite:////app/data/pirapire.db"
    log_level: str = "INFO"
    admin_token: str = ""

    # HTTP
    http_timeout_connect: float = 5.0
    http_timeout_read: float = 20.0
    http_timeout_write: float = 5.0
    http_timeout_pool: float = 5.0

    # LoL Data sources
    datadragon_base_url: str = "https://ddragon.leagueoflegends.com"
    datadragon_locale: str = "es_MX"
    riot_api_key: str = ""
    leaguepedia_user_agent: str = "PirapireLocal/1.0"
    leaguepedia_sync_enabled: bool = True
    leaguepedia_base_url: str = "https://lol.fandom.com/wiki/Special:CargoExport"
    leaguepedia_import_lookback_days: int = 21
    leaguepedia_import_lookahead_days: int = 14

    # LoL competitive history (Oracle's Elixir)
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
    lol_history_import_dir: str = "/app/data/imports/oracles"
    lol_history_allow_download: bool = False

    # LoL odds
    lol_odds_import_dir: str = "/app/data/imports/lol_odds"

    # Worker
    lol_schedule_interval_minutes: int = 30
    lol_history_interval_minutes: int = 240
    datadragon_interval_minutes: int = 1440
    lol_import_poll_interval_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
