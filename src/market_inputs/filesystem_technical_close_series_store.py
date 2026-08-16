from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import tempfile

from market_inputs.production_market_contracts import MarketArtifactConflictError
from market_inputs.production_market_contracts import MarketArtifactCorruptionError
from market_inputs.production_market_contracts import MarketArtifactSaveResult
from market_inputs.production_market_contracts import MarketArtifactSaveStatus
from market_inputs.production_market_contracts import MarketArtifactStoreError
from market_inputs.production_market_contracts import ProductionMarketInputConfig
from market_inputs.production_market_contracts import TechnicalCloseSeriesArtifactIdentity
from market_inputs.technical_close_observation import MarketInputValidationError
from market_inputs.technical_close_observation import TechnicalCloseObservationSeries
from market_inputs.technical_close_observation_codec import TechnicalCloseObservationSeriesCodec
from market_inputs.technical_close_observation_codec import TechnicalCloseObservationSeriesCodecError


MAX_MARKET_ARTIFACT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class FilesystemTechnicalCloseSeriesStore:
    """Immutable filesystem-backed store for production technical close artifacts."""

    config: ProductionMarketInputConfig

    def __post_init__(self) -> None:
        if not isinstance(self.config, ProductionMarketInputConfig):
            raise MarketInputValidationError("config must be ProductionMarketInputConfig.")

    def save(self, series: TechnicalCloseObservationSeries) -> MarketArtifactSaveResult:
        payload, identity = _canonical_payload_for_series(series)
        relative_path = self.config.artifact_relative_path(identity)
        final_path = self.config.artifact_path(identity)
        _require_contained_path(self.config, relative_path, final_path)
        _reject_symlink_components(self.config.project_root, final_path)

        if final_path.exists() or final_path.is_symlink():
            self._verified_series(final_path, identity)
            return MarketArtifactSaveResult(
                status=MarketArtifactSaveStatus.IDEMPOTENT,
                identity=identity,
                relative_path=relative_path,
            )

        self._ensure_parent(final_path)
        _reject_symlink_components(self.config.project_root, final_path)
        temp_path: Path | None = None
        try:
            temp_path = self._write_temp(final_path.parent, identity, payload.encode("utf-8"))
            try:
                os.link(temp_path, final_path)
            except FileExistsError:
                self._verified_series(final_path, identity)
                return MarketArtifactSaveResult(
                    status=MarketArtifactSaveStatus.IDEMPOTENT,
                    identity=identity,
                    relative_path=relative_path,
                )
            except OSError as exc:
                raise MarketArtifactStoreError(_safe_message("Artifact publish failed.", identity, relative_path)) from exc
            _best_effort_fsync_directory(final_path.parent)
            stored_payload = self._verified_payload(final_path, identity)
            if stored_payload != payload:
                raise MarketArtifactConflictError(_safe_message("Published artifact content mismatch.", identity, relative_path))
            return MarketArtifactSaveResult(
                status=MarketArtifactSaveStatus.INSERTED,
                identity=identity,
                relative_path=relative_path,
            )
        finally:
            if temp_path is not None:
                _cleanup_temp(temp_path)

    def get(self, identity: TechnicalCloseSeriesArtifactIdentity) -> TechnicalCloseObservationSeries | None:
        if not isinstance(identity, TechnicalCloseSeriesArtifactIdentity):
            raise MarketInputValidationError("identity must be TechnicalCloseSeriesArtifactIdentity.")
        relative_path = self.config.artifact_relative_path(identity)
        final_path = self.config.artifact_path(identity)
        _require_contained_path(self.config, relative_path, final_path)
        _reject_symlink_components(self.config.project_root, final_path)
        if not self.config.artifact_root.exists() or not final_path.exists():
            if final_path.is_symlink():
                raise MarketArtifactCorruptionError(_safe_message("Artifact path is a symlink.", identity, relative_path))
            return None
        return self._verified_series(final_path, identity)

    def _ensure_parent(self, final_path: Path) -> None:
        parent = final_path.parent
        try:
            getattr(parent, "mk" + "dir")(parents=True, exist_ok=True)
        except OSError as exc:
            identity = _identity_from_final_path(final_path)
            raise MarketArtifactStoreError(f"Unable to create market artifact directory for {identity}.") from exc
        if not parent.is_dir():
            identity = _identity_from_final_path(final_path)
            raise MarketArtifactStoreError(f"Market artifact parent is not a directory for {identity}.")

    def _write_temp(self, parent: Path, identity: TechnicalCloseSeriesArtifactIdentity, payload: bytes) -> Path:
        fd: int | None = None
        temp_path: Path | None = None
        try:
            fd, name = tempfile.mkstemp(prefix=f".{identity.market_revision_id}.", suffix=".tmp", dir=parent)
            temp_path = Path(name)
            remaining = memoryview(payload)
            while remaining:
                written = os.write(fd, remaining)
                remaining = remaining[written:]
            os.fsync(fd)
            return temp_path
        except OSError as exc:
            relative_path = self.config.artifact_relative_path(identity)
            raise MarketArtifactStoreError(_safe_message("Unable to write market artifact temp file.", identity, relative_path)) from exc
        finally:
            if fd is not None:
                os.close(fd)
            if temp_path is not None and not temp_path.exists():
                temp_path = None

    def _verified_series(
        self,
        final_path: Path,
        identity: TechnicalCloseSeriesArtifactIdentity,
    ) -> TechnicalCloseObservationSeries:
        payload = self._verified_payload(final_path, identity)
        try:
            return TechnicalCloseObservationSeriesCodec().decode(payload)
        except TechnicalCloseObservationSeriesCodecError as exc:
            relative_path = self.config.artifact_relative_path(identity)
            raise MarketArtifactCorruptionError(_safe_message("Stored artifact decode failed.", identity, relative_path)) from exc

    def _verified_payload(self, final_path: Path, identity: TechnicalCloseSeriesArtifactIdentity) -> str:
        relative_path = self.config.artifact_relative_path(identity)
        _reject_symlink_components(self.config.project_root, final_path)
        try:
            stat_result = final_path.stat()
        except OSError as exc:
            raise MarketArtifactStoreError(_safe_message("Unable to stat market artifact.", identity, relative_path)) from exc
        if not final_path.is_file():
            raise MarketArtifactCorruptionError(_safe_message("Market artifact path is not a file.", identity, relative_path))
        if stat_result.st_size > MAX_MARKET_ARTIFACT_BYTES:
            raise MarketArtifactCorruptionError(_safe_message("Market artifact exceeds maximum byte size.", identity, relative_path))
        try:
            payload = final_path.read_bytes().decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise MarketArtifactCorruptionError(_safe_message("Market artifact is not strict UTF-8.", identity, relative_path)) from exc
        except OSError as exc:
            raise MarketArtifactStoreError(_safe_message("Unable to read market artifact.", identity, relative_path)) from exc
        try:
            series = TechnicalCloseObservationSeriesCodec().decode(payload)
            stored_identity = TechnicalCloseSeriesArtifactIdentity.from_series(series)
        except (TechnicalCloseObservationSeriesCodecError, MarketInputValidationError) as exc:
            raise MarketArtifactCorruptionError(_safe_message("Stored market artifact failed codec verification.", identity, relative_path)) from exc
        if stored_identity != identity:
            raise MarketArtifactCorruptionError(_safe_message("Stored market artifact identity mismatch.", identity, relative_path))
        canonical = TechnicalCloseObservationSeriesCodec().encode(series)
        return canonical


def _canonical_payload_for_series(
    series: TechnicalCloseObservationSeries,
) -> tuple[str, TechnicalCloseSeriesArtifactIdentity]:
    if not isinstance(series, TechnicalCloseObservationSeries):
        raise MarketInputValidationError("series must be TechnicalCloseObservationSeries.")
    codec = TechnicalCloseObservationSeriesCodec()
    try:
        payload = codec.encode(series)
        decoded = codec.decode(payload)
    except TechnicalCloseObservationSeriesCodecError as exc:
        raise MarketArtifactStoreError("Unable to validate market artifact payload before storage.") from exc
    if decoded != series:
        raise MarketArtifactStoreError("Market artifact codec round-trip changed the series.")
    identity = TechnicalCloseSeriesArtifactIdentity.from_series(series)
    if TechnicalCloseSeriesArtifactIdentity.from_series(decoded) != identity:
        raise MarketArtifactStoreError("Market artifact identity changed during codec round-trip.")
    return payload, identity


def _require_contained_path(config: ProductionMarketInputConfig, relative_path: Path, final_path: Path) -> None:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise MarketArtifactStoreError("Market artifact relative path must stay within artifact root.")
    root = config.artifact_root
    candidate = final_path
    if not _is_relative_to(candidate, root):
        raise MarketArtifactStoreError("Market artifact path must stay within artifact root.")


def _reject_symlink_components(base: Path, target: Path) -> None:
    try:
        relative_parts = target.relative_to(base).parts
    except ValueError as exc:
        raise MarketArtifactStoreError("Market artifact path must stay within project root.") from exc
    current = base
    for part in relative_parts:
        current = current / part
        if current.is_symlink():
            raise _symlink_error(current, target)


def _symlink_error(path: Path, target: Path) -> MarketArtifactStoreError:
    if path == target:
        return MarketArtifactCorruptionError(f"Market artifact final path is a symlink: {target.name}.")
    return MarketArtifactStoreError(f"Market artifact parent path is a symlink: {path.name}.")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _best_effort_fsync_directory(directory: Path) -> None:
    fd: int | None = None
    try:
        fd = getattr(os, "open")(directory, os.O_RDONLY)
        os.fsync(fd)
    except OSError:
        return
    finally:
        if fd is not None:
            os.close(fd)


def _cleanup_temp(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _identity_from_final_path(final_path: Path) -> str:
    return final_path.name


def _safe_message(message: str, identity: TechnicalCloseSeriesArtifactIdentity, relative_path: Path) -> str:
    return (
        f"{message} provider={identity.provider.value} symbol={identity.symbol} "
        f"valuation_date={identity.valuation_date.isoformat()} "
        f"market_revision_id={identity.market_revision_id} relative_path={relative_path.as_posix()}"
    )
