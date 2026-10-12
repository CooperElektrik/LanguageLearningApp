"""Shared building blocks for the settings and unified-setup dialogs.

``SettingsDialog`` and ``UnifiedSetupDialog`` had near-identical copies of the
Whisper/Vosk model population, microphone enumeration, locale population and
the CUDA probe.  The copies had already drifted (the unified dialog's tooltip
dropped a line).  These helpers centralise the logic; the dialogs keep their own
widget names and wording.
"""

import logging
from collections.abc import Callable

import settings
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QComboBox

logger = logging.getLogger(__name__)

# Result codes for detect_cuda_status(); each dialog maps these to its own text.
CUDA_AVAILABLE = "available"
CUDA_NOT_AVAILABLE = "not_available"
CUDA_TORCH_MISSING = "torch_missing"
CUDA_ERROR = "error"


def detect_cuda_status() -> str:
    """Probes PyTorch/CUDA and returns one of the ``CUDA_*`` status codes."""
    try:
        from core.whisper_engine import _TORCH_AVAILABLE

        if not _TORCH_AVAILABLE:
            return CUDA_TORCH_MISSING
        import torch  # type: ignore

        return CUDA_AVAILABLE if torch.cuda.is_available() else CUDA_NOT_AVAILABLE
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Error checking PyTorch/CUDA availability: {e}")
        return CUDA_ERROR


def populate_whisper_model_combo(
    combo: QComboBox,
    translate: Callable[[str], str],
    include_processing_time: bool = True,
) -> None:
    """Fills a Whisper model combo box with download status and tooltips."""
    combo.addItem("None", userData="None")  # Option to disable

    from core.whisper_engine import check_whisper_model_downloaded

    for model_name, info in settings.WHISPER_MODEL_INFO.items():
        if check_whisper_model_downloaded(model_name):
            display_name = model_name + translate(" (Downloaded)")
        else:
            display_name = model_name + translate(" (Not Downloaded)")
        combo.addItem(display_name, userData=model_name)

        if include_processing_time:
            tooltip_key = (
                "Model: {model_name}\n"
                "Size: {size}\n"
                "Parameters: {params}\n"
                "Recommended Device: {device_rec}\n"
                "Expected processing time (CPU): {ptime}\n"
            )
        else:
            tooltip_key = (
                "Model: {model_name}\n"
                "Size: {size}\n"
                "Parameters: {params}\n"
                "Recommended Device: {device_rec}"
            )
        tooltip_text = translate(tooltip_key).format(**info, model_name=model_name)
        combo.setItemData(combo.count() - 1, tooltip_text, Qt.ItemDataRole.ToolTipRole)


def populate_vosk_model_combo(
    combo: QComboBox, translate: Callable[[str], str]
) -> None:
    """Fills a Vosk model combo box with tooltips."""
    combo.addItem("None", userData="None")  # Option to disable
    for model_name, info in settings.VOSK_MODEL_INFO.items():
        combo.addItem(model_name, userData=model_name)
        tooltip_text = translate(
            "Model: {model_name}\n"
            "Size: {size}\n"
            "Language: {lang}\n"
            "Description: {description}\n"
        ).format(**info, model_name=model_name)
        combo.setItemData(combo.count() - 1, tooltip_text, Qt.ItemDataRole.ToolTipRole)


def populate_audio_input_devices(combo: QComboBox) -> None:
    """Fills an audio-input combo box, selecting the system default device."""
    combo.clear()
    default_device = QMediaDevices.defaultAudioInput()
    default_device_id = (
        default_device.id().toStdString() if not default_device.isNull() else ""
    )
    for device in QMediaDevices.audioInputs():
        combo.addItem(device.description(), userData=device.id().toStdString())

    if default_device_id:
        index = combo.findData(default_device_id)
        if index != -1:
            combo.setCurrentIndex(index)


def populate_locale_combo(combo: QComboBox, available_locales: dict[str, str]) -> None:
    """Fills a locale combo box, keeping "System" first."""
    sorted_display_names = sorted(
        available_locales.keys(),
        key=lambda x: (x != settings.DEFAULT_LOCALE, x),
    )
    for display_name in sorted_display_names:
        combo.addItem(display_name, userData=available_locales[display_name])
