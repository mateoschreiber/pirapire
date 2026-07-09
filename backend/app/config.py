from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pirapire"
    app_env: str = "local"
    database_url: str = "sqlite:////app/data/pirapire.db"
    log_level: str = "INFO"

    # External data sources (all optional; empty means "not configured").
    football_data_api_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_competitions: str = "WC,CL,PL,BL1,SA,PD,FL1"
    football_data_request_delay_seconds: float = 7.0
    football_data_max_competitions_per_run: int = 3
    football_data_respect_retry_after: bool = True
    riot_api_key: str = ""
    thesportsdb_api_key: str = ""
    riot_esports_access: str = ""
    leaguepedia_user_agent: str = "PirapireLocal/1.0"

    openligadb_league_shortcut: str = ""
    openligadb_season: str = ""
    openligadb_base_url: str = "https://api.openligadb.de"

    datadragon_base_url: str = "https://ddragon.leagueoflegends.com"
    datadragon_locale: str = "es_MX"

    sync_default_lookback_days: int = 30
    sync_default_lookahead_days: int = 14

    http_timeout_connect: float = 5.0
    http_timeout_read: float = 20.0
    http_timeout_write: float = 5.0
    http_timeout_pool: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def competitions_list(self) -> list[str]:
        return [c.strip() for c in self.football_data_competitions.split(",") if c.strip()]


settings = Settings()
