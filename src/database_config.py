from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESEARCH_SNAPSHOT_ID = "research_snapshot_candidate_a_composite_twse_validation_2018_2025_v1"
DEFAULT_RESEARCH_SNAPSHOT_VERSION = "v1"
DEFAULT_RESEARCH_MATERIALIZATION_VERSION = "v2"
DEFAULT_RESEARCH_SEMANTIC_CHECKSUM = "a1f793b520766ab94f7b2234b54773cee78424f1a2efbf6b9de5379d0ff01f91"
DEFAULT_RESEARCH_DB_SHA256 = "3417b34a11660e672d75c5879d0d8f9e177c574b603b540274bad7acb2215de0"
DEFAULT_USE_PHYSICAL_STORE_SPLIT = True


@dataclass(frozen=True)
class DatabasePathConfig:
    """Central database path contract for the future research/live split."""

    project_root: Path
    legacy_db_path: Path
    research_db_path: Path
    live_db_path: Path
    research_snapshot_id: str = DEFAULT_RESEARCH_SNAPSHOT_ID
    research_snapshot_version: str = DEFAULT_RESEARCH_SNAPSHOT_VERSION
    research_materialization_version: str = DEFAULT_RESEARCH_MATERIALIZATION_VERSION
    research_semantic_checksum: str = DEFAULT_RESEARCH_SEMANTIC_CHECKSUM
    research_db_sha256: str = DEFAULT_RESEARCH_DB_SHA256
    manifest_path: Path | None = None

    def __post_init__(self) -> None:
        if self.manifest_path is None:
            object.__setattr__(
                self,
                "manifest_path",
                self.project_root
                / "data"
                / "research"
                / "manifests"
                / f"{self.research_snapshot_id}_materialization_{self.research_materialization_version}_manifest.json",
            )

    @classmethod
    def default(cls, project_root: Path | None = None) -> "DatabasePathConfig":
        root = project_root or PROJECT_ROOT
        legacy_db_path = root / "data" / "stocks.db"
        research_snapshot_id = DEFAULT_RESEARCH_SNAPSHOT_ID
        return cls(
            project_root=root,
            legacy_db_path=legacy_db_path,
            research_db_path=(
                root
                / "data"
                / "research"
                / "snapshots"
                / f"{research_snapshot_id}_materialization_{DEFAULT_RESEARCH_MATERIALIZATION_VERSION}.db"
            ),
            live_db_path=root / "data" / "live" / "stocks_live.db",
            research_snapshot_id=research_snapshot_id,
            research_snapshot_version=DEFAULT_RESEARCH_SNAPSHOT_VERSION,
            research_materialization_version=DEFAULT_RESEARCH_MATERIALIZATION_VERSION,
            research_semantic_checksum=DEFAULT_RESEARCH_SEMANTIC_CHECKSUM,
            research_db_sha256=DEFAULT_RESEARCH_DB_SHA256,
            manifest_path=(
                root
                / "data"
                / "research"
                / "manifests"
                / f"{research_snapshot_id}_materialization_{DEFAULT_RESEARCH_MATERIALIZATION_VERSION}_manifest.json"
            ),
        )


@dataclass(frozen=True)
class DatabaseRuntimeResolution:
    """Resolved database paths for a prospective physical-store split."""

    use_physical_store_split: bool
    active_db_mode: str
    active_live_db_path: Path
    active_research_db_path: Path
    legacy_db_path: Path
    live_db_path: Path
    research_db_path: Path
    research_snapshot_id: str
    research_snapshot_version: str
    research_materialization_version: str
    research_semantic_checksum: str
    research_db_sha256: str
    manifest_path: Path


def resolve_database_runtime_config(
    *,
    use_physical_store_split: bool = DEFAULT_USE_PHYSICAL_STORE_SPLIT,
    path_config: DatabasePathConfig | None = None,
) -> DatabaseRuntimeResolution:
    """Resolve runtime paths for the physical-store split cutover."""

    config = path_config or DEFAULT_DATABASE_PATH_CONFIG
    active_live_db_path = config.live_db_path if use_physical_store_split else config.legacy_db_path
    return DatabaseRuntimeResolution(
        use_physical_store_split=use_physical_store_split,
        active_db_mode="physical_split" if use_physical_store_split else "legacy",
        active_live_db_path=active_live_db_path,
        active_research_db_path=config.research_db_path,
        legacy_db_path=config.legacy_db_path,
        live_db_path=config.live_db_path,
        research_db_path=config.research_db_path,
        research_snapshot_id=config.research_snapshot_id,
        research_snapshot_version=config.research_snapshot_version,
        research_materialization_version=config.research_materialization_version,
        research_semantic_checksum=config.research_semantic_checksum,
        research_db_sha256=config.research_db_sha256,
        manifest_path=config.manifest_path,
    )


DEFAULT_DATABASE_PATH_CONFIG = DatabasePathConfig.default()
