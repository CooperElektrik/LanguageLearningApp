import yaml
import logging
import os
from typing import List, Dict, Any, Optional
from .models import GlossaryEntry # <-- Import the new dataclass

logger = logging.getLogger(__name__)


def load_glossary(glossary_path: str) -> List[GlossaryEntry]:
    """
    Loads and parses the glossary YAML file into a list of GlossaryEntry objects.
    """
    if not os.path.exists(glossary_path):
        logger.info(f"Glossary file not found: {glossary_path}. Returning empty list.")
        return []

    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            raw_glossary_data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Glossary file not found: {glossary_path}")
        return []
    except yaml.YAMLError as e:
        logger.error(f"Error parsing glossary YAML file {glossary_path}: {e}")
        return []
    except Exception as e:
        logger.error(
            f"An unexpected error occurred loading glossary content {glossary_path}: {e}"
        )
        return []

    if not isinstance(raw_glossary_data, list):
        logger.error(
            f"Glossary content file {glossary_path} is not a list of entries."
        )
        return []

    glossary_entries: List[GlossaryEntry] = []
    for entry_data in raw_glossary_data:
        if not isinstance(entry_data, dict) or not entry_data.get("word") or not entry_data.get("translation"):
            logger.warning(
                f"Skipping malformed glossary entry in {glossary_path}: {entry_data}"
            )
            continue
        try:
            glossary_entries.append(
                GlossaryEntry(
                    word=entry_data["word"],
                    translation=entry_data["translation"],
                    part_of_speech=entry_data.get("part_of_speech"),
                    example_sentence=entry_data.get("example_sentence"),
                    notes=entry_data.get("notes"),
                    audio_file=entry_data.get("audio_file"),
                )
            )
        except Exception as e:
            logger.warning(f"Error creating GlossaryEntry from {entry_data}: {e}")

    logger.info(f"Loaded {len(glossary_entries)} glossary entries from {glossary_path}.")
    return glossary_entries