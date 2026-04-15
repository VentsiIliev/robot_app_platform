import logging


_logger = logging.getLogger(__name__)


def get_target_marker_ids(context) -> list[int]:
    if context.target_plan.target_marker_ids:
        return list(context.target_plan.target_marker_ids)
    if context.target_plan.required_ids:
        return list(context.target_plan.required_ids)
    return sorted(list(context.required_ids))


def get_recovery_marker_id(context) -> int | None:
    recovery_marker_id = context.target_plan.recovery_marker_id
    if recovery_marker_id is not None:
        return int(recovery_marker_id)
    target_ids = get_target_marker_ids(context)
    return int(target_ids[0]) if target_ids else None


def record_known_unreachable_marker(context, marker_id: int, reason: str) -> None:
    settings_service = context.settings_service
    calibration_key = context.calibration_settings_key
    if settings_service is None or calibration_key is None:
        return

    try:
        calibration_settings = settings_service.get(calibration_key)
        if calibration_settings is None:
            return

        auto_skip_enabled = bool(
            getattr(calibration_settings, "auto_skip_known_unreachable_markers", True)
        )
        if not auto_skip_enabled:
            _logger.info(
                "Skipping persistence of unreachable calibration marker %s because auto-skip is disabled",
                int(marker_id),
            )
            return

        counts = {
            int(saved_marker_id): int(count)
            for saved_marker_id, count in (
                getattr(calibration_settings, "unreachable_marker_failure_counts", {}) or {}
            ).items()
        }
        count = counts.get(int(marker_id), 0) + 1
        counts[int(marker_id)] = count

        threshold = max(
            1,
            int(getattr(calibration_settings, "unreachable_marker_failure_threshold", 1) or 1),
        )
        known_ids = {
            int(saved_marker_id)
            for saved_marker_id in (
                getattr(calibration_settings, "known_unreachable_marker_ids", []) or []
            )
        }
        promoted = count >= threshold
        if promoted:
            known_ids.add(int(marker_id))

        calibration_settings.unreachable_marker_failure_counts = counts
        calibration_settings.known_unreachable_marker_ids = sorted(known_ids)
        settings_service.save(calibration_key, calibration_settings)

        context.unreachable_marker_failure_counts = counts
        context.known_unreachable_marker_ids = set(known_ids)

        _logger.warning(
            "Recorded unreachable calibration marker %s: count=%s threshold=%s known_unreachable=%s reason=%s",
            int(marker_id),
            count,
            threshold,
            promoted,
            reason,
        )
    except Exception as exc:
        _logger.warning(
            "Failed to persist unreachable calibration marker %s: %s",
            int(marker_id),
            exc,
        )


def try_activate_fallback_target(context, failed_marker_id: int, reason: str) -> bool:
    settings_service = context.settings_service
    calibration_key = context.calibration_settings_key
    if settings_service is not None and calibration_key is not None:
        try:
            calibration_settings = settings_service.get(calibration_key)
            if calibration_settings is not None and not bool(
                getattr(calibration_settings, "auto_skip_known_unreachable_markers", True)
            ):
                _logger.info(
                    "Auto-skip disabled; not replacing failed calibration target %s",
                    int(failed_marker_id),
                )
                return False
        except Exception:
            pass

    target_ids = get_target_marker_ids(context)
    progress = context.progress
    artifacts = context.artifacts
    target_plan = context.target_plan
    current_marker_id = progress.current_marker_id
    marker_neighbor_ids = target_plan.marker_neighbor_ids or {}
    failed_target_ids = artifacts.failed_target_ids
    markers_offsets_mm = artifacts.markers_offsets_mm

    if current_marker_id >= len(target_ids):
        return False

    active_ids = set(target_ids)
    neighbor_ids = marker_neighbor_ids.get(failed_marker_id, [])
    for candidate_id in neighbor_ids:
        if candidate_id in active_ids or candidate_id in failed_target_ids:
            continue
        if candidate_id not in markers_offsets_mm:
            continue
        old_id = target_ids[current_marker_id]
        target_ids[current_marker_id] = candidate_id
        target_plan.target_marker_ids = list(target_ids)
        context.target_marker_ids = target_ids
        context.failed_target_ids.add(int(old_id))
        context.skipped_target_ids.add(int(old_id))
        _logger.warning(
            "Replacing calibration target %s with nearby marker %s due to %s",
            old_id,
            candidate_id,
            reason,
        )
        return True
    return False


def get_marker_offset_mm(context, marker_id: int) -> tuple[float, float]:
    markers_offsets_mm = context.artifacts.markers_offsets_mm
    stored_offset = markers_offsets_mm.get(int(marker_id))
    if stored_offset is None:
        return 0.0, 0.0

    # These offsets are already the calibration-frame robot targets for each
    # marker. They must remain in that global frame for every initial jump; the
    # refined working PPM is only for local iterative recentering once a marker
    # is in view.
    return float(stored_offset[0]), float(stored_offset[1])
