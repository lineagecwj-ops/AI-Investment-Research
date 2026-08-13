"""Research-scoped OOS contracts for technical risk methodology work."""

from risk_oos.aligned_dataset import AlignedTechnicalRiskOOSRow
from risk_oos.aligned_dataset import TARGET_MAE20
from risk_oos.aligned_dataset import TARGET_MAE60
from risk_oos.aligned_dataset import TECHNICAL_RISK_OOS_DATASET_BUILDER_VERSION
from risk_oos.aligned_dataset import TECHNICAL_RISK_OOS_DATASET_SCHEMA_VERSION
from risk_oos.aligned_dataset import TECHNICAL_RISK_V1_FEATURE_SET_ID
from risk_oos.aligned_dataset import TECHNICAL_RISK_V1_TARGET_IDENTITIES
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetBuilder
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetError
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetResult
from risk_oos.aligned_dataset import TechnicalRiskOOSDatasetSpec
from risk_oos.aligned_dataset import TechnicalRiskOOSExclusionReason
from risk_oos.aligned_dataset import TechnicalRiskOOSExclusionRecord
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitRole
from risk_oos.aligned_dataset import TechnicalRiskOOSSplitSpec
from risk_oos.historical_features import EXCLUSION_FEATURE_CALCULATION_FAILED
from risk_oos.historical_features import EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY
from risk_oos.historical_features import EXCLUSION_INVALID_PRICE
from risk_oos.historical_features import EXCLUSION_MISSING_AS_OF_CLOSE
from risk_oos.historical_features import HISTORICAL_RISK_FEATURE_SET_V1
from risk_oos.historical_features import HistoricalRiskFeatureExclusion
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationContext
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationError
from risk_oos.historical_features import HistoricalRiskFeatureMaterializationResult
from risk_oos.historical_features import HistoricalRiskFeatureMaterializer
from risk_oos.historical_features import HistoricalRiskFeatureObservation
from risk_oos.historical_features import HistoricalRiskFeatureStatus

__all__ = [
    "AlignedTechnicalRiskOOSRow",
    "EXCLUSION_FEATURE_CALCULATION_FAILED",
    "EXCLUSION_INSUFFICIENT_REQUIRED_FEATURE_HISTORY",
    "EXCLUSION_INVALID_PRICE",
    "EXCLUSION_MISSING_AS_OF_CLOSE",
    "HISTORICAL_RISK_FEATURE_SET_V1",
    "HistoricalRiskFeatureExclusion",
    "HistoricalRiskFeatureMaterializationContext",
    "HistoricalRiskFeatureMaterializationError",
    "HistoricalRiskFeatureMaterializationResult",
    "HistoricalRiskFeatureMaterializer",
    "HistoricalRiskFeatureObservation",
    "HistoricalRiskFeatureStatus",
    "TARGET_MAE20",
    "TARGET_MAE60",
    "TECHNICAL_RISK_OOS_DATASET_BUILDER_VERSION",
    "TECHNICAL_RISK_OOS_DATASET_SCHEMA_VERSION",
    "TECHNICAL_RISK_V1_FEATURE_SET_ID",
    "TECHNICAL_RISK_V1_TARGET_IDENTITIES",
    "TechnicalRiskOOSDatasetBuilder",
    "TechnicalRiskOOSDatasetError",
    "TechnicalRiskOOSDatasetResult",
    "TechnicalRiskOOSDatasetSpec",
    "TechnicalRiskOOSExclusionReason",
    "TechnicalRiskOOSExclusionRecord",
    "TechnicalRiskOOSSplitRole",
    "TechnicalRiskOOSSplitSpec",
]
