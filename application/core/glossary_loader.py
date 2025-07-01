import yaml
import logging
import os
from typing import List, Dict, Any, Optional

from .models import GlossaryEntry
from .course_loader import _validate_asset_path

logger = logging.getLogger(__name__)


def load_glossary(glossary_path: str, course_base_dir: str, pool_base_dir: str) -> List[GlossaryEntry]:
    """
    Loads and parses the glossary YAML file into a list of GlossaryEntry objects.
    Returns an empty list if the file is not found or parsing fails.
    """
    logger.debug(f"Attempting to load glossary from: {glossary_path}")
    if not os.path.exists(glossary_path):
        logger.info(
            f"Glossary file not found at expected path: {glossary_path}. Returning empty list."
        )
        return []

    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            raw_glossary_data = yaml.safe_load(f)
        logger.info(f"Successfully loaded raw glossary data from {glossary_path}")
    except (
        FileNotFoundError
    ):  # This is technically redundant due to os.path.exists check, but kept for defense-in-depth or if file disappears
        logger.error(f"Glossary file not found: {glossary_path}")
        return []
    except yaml.YAMLError as e:
        logger.error(f"Error parsing glossary YAML file {glossary_path}: {e}")
        return []
    except Exception as e:
        logger.error(
            f"An unexpected error occurred loading glossary content from {glossary_path}: {e}"
        )
        return []

    if not isinstance(raw_glossary_data, list):
        logger.error(
            f"Glossary content file {glossary_path} is not a list of entries. Found type: {type(raw_glossary_data).__name__}. Returning empty list."
        )
        return []

    glossary_entries: List[GlossaryEntry] = []
    for i, entry_data in enumerate(raw_glossary_data):
        if not isinstance(entry_data, dict):
            logger.warning(
                f"Skipping malformed glossary entry at index {i} in {glossary_path}: Expected dictionary, got {type(entry_data).__name__}."
            )
            continue

        word = entry_data.get("word")
        translation = entry_data.get("translation")

        if not word or not translation:
            logger.warning(
                f"Skipping malformed glossary entry at index {i} in {glossary_path}: Missing 'word' or 'translation'. Data: {entry_data}"
            )
            continue

        try:
            audio_file = entry_data.get("audio_file")
            _validate_asset_path(audio_file, course_base_dir, pool_base_dir)
            glossary_entries.append(
                GlossaryEntry(
                    word=word,
                    translation=translation,
                    part_of_speech=entry_data.get("part_of_speech"),
                    example_sentence=entry_data.get("example_sentence"),
                    notes=entry_data.get("notes"),
                    audio_file=audio_file,
                )
            )
            logger.debug(f"Successfully parsed glossary entry for word: '{word}'")
        except Exception as e:
            logger.warning(
                f"Error creating GlossaryEntry from entry at index {i} in {glossary_path}: {e}. Data: {entry_data}"
            )

    logger.info(
        f"Loaded {len(glossary_entries)} glossary entries from {glossary_path}."
    )
    return glossary_entries
