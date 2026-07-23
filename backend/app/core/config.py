from dataclasses import dataclass
from pathlib import Path

APP_NAME = "AI 错题复盘工作台"
API_VERSION = "v1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path
    database: Path
    uploads: Path
    exports: Path
    logs: Path
    runtime: Path
    config: Path
    secrets: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "AppPaths":
        root = data_dir.resolve()
        return cls(
            data_dir=root,
            database=root / "app.db",
            uploads=root / "uploads",
            exports=root / "exports",
            logs=root / "logs",
            runtime=root / "runtime",
            config=root / "config",
            secrets=root / "config" / "secrets",
        )

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.uploads.mkdir(exist_ok=True)
        self.exports.mkdir(exist_ok=True)
        self.logs.mkdir(exist_ok=True)
        self.runtime.mkdir(exist_ok=True)
        self.config.mkdir(exist_ok=True)
        self.secrets.mkdir(exist_ok=True)
