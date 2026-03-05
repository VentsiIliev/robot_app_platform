from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.vision.implementation.VisionSystem.features.contour_matching.settings.contour_matching_settings_data import ContourMatchingSettingsData
from src.engine.vision.implementation.VisionSystem.features.contour_matching.settings.setting_key import ContourMatchingSettingKey


class ContourMatchingSettingsSerializer(ISettingsSerializer[ContourMatchingSettingsData]):

    @property
    def settings_type(self) -> str:
        return "contour_matching"

    def get_default(self) -> ContourMatchingSettingsData:
        return ContourMatchingSettingsData()

    def to_dict(self, settings: ContourMatchingSettingsData) -> dict:
        k = ContourMatchingSettingKey
        return {
            k.SIMILARITY_THRESHOLD.value:        settings.similarity_threshold,
            k.REFINEMENT_THRESHOLD.value:        settings.refinement_threshold,
            k.DEBUG_SIMILARITY.value:            settings.debug_similarity,
            k.DEBUG_CALCULATE_DIFFERENCES.value: settings.debug_calculate_differences,
            k.DEBUG_ALIGN_CONTOURS.value:        settings.debug_align_contours,
            k.USE_COMPARISON_MODEL.value:        settings.use_comparison_model,
        }

    def from_dict(self, data: dict) -> ContourMatchingSettingsData:
        d = ContourMatchingSettingsData()
        k = ContourMatchingSettingKey
        return ContourMatchingSettingsData(
            similarity_threshold=data.get(k.SIMILARITY_THRESHOLD.value, d.similarity_threshold),
            refinement_threshold=data.get(k.REFINEMENT_THRESHOLD.value, d.refinement_threshold),
            debug_similarity=data.get(k.DEBUG_SIMILARITY.value, d.debug_similarity),
            debug_calculate_differences=data.get(k.DEBUG_CALCULATE_DIFFERENCES.value, d.debug_calculate_differences),
            debug_align_contours=data.get(k.DEBUG_ALIGN_CONTOURS.value, d.debug_align_contours),
            use_comparison_model=data.get(k.USE_COMPARISON_MODEL.value, d.use_comparison_model),
        )

