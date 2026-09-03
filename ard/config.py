"""Runtime configuration, which is loaded from .env / environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _parse_targets(raw: str) -> dict:
    """Parse SOURCE_DB_TARGETS"""
    targets = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, _, dsn = entry.partition("=")
        if dsn:
            targets[name.strip()] = dsn.strip()
    return targets


@dataclass
class Config:
    db_host: str = os.getenv("ARD_DB_HOST", "localhost")
    db_port: int = int(os.getenv("ARD_DB_PORT", "5432"))
    db_name: str = os.getenv("ARD_DB_NAME", "ard")
    db_user: str = os.getenv("ARD_DB_USER", "ard")
    db_password: str = os.getenv("ARD_DB_PASSWORD", "ard_pass")

    poll_interval_minutes: int = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))
    timezone: str = os.getenv("APP_TIMEZONE", "Asia/Dhaka")
    output_dir: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
    log_dir: Path = BASE_DIR / os.getenv("LOG_DIR", "logs")

    source_targets: dict = field(
        default_factory=lambda: _parse_targets(os.getenv("SOURCE_DB_TARGETS", ""))
    )

    smtp_dry_run: bool = _bool("SMTP_DRY_RUN", True)
    smtp_host: str = os.getenv("SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _bool("SMTP_USE_TLS", True)
    smtp_from: str = os.getenv("SMTP_FROM", "ard-bot@example.com")

    @property
    def app_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def dsn_for_target(self, db_target: str) -> str:
        """QUERY.db_target"""
        return self.source_targets.get(db_target, self.app_dsn)


config = Config()
config.output_dir.mkdir(parents=True, exist_ok=True)
config.log_dir.mkdir(parents=True, exist_ok=True)
