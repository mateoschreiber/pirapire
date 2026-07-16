"""Refresh local official LoL Esports logos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.team_logo_sync import sync_official_team_logos


def main():
    result = sync_official_team_logos()
    print(f"downloaded {result['downloaded']} logos; cached {result['total']}")


if __name__ == "__main__":
    main()
