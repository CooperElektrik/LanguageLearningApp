import sys
import os
import argparse
import logging
import yaml
import zipfile
from typing import Dict, Any, Optional, Tuple, List

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def read_manifest(
    manifest_filepath: str, messages: List[str]
) -> Optional[Dict[str, Any]]:
    """Reads and parses the manifest YAML file, adding messages to the list."""
    if not os.path.exists(manifest_filepath):
        messages.append(f"Error: Manifest file not found: {manifest_filepath}")
        return None
    try:
        with open(manifest_filepath, "r", encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)
        if not isinstance(manifest_data, dict):
            messages.append(
                f"Error: Manifest file '{manifest_filepath}' does not contain valid YAML dictionary."
            )
            return None
        messages.append(f"Info: Successfully read manifest: {manifest_filepath}")
        return manifest_data
    except yaml.YAMLError as e:
        messages.append(f"Error: Parsing manifest YAML file '{manifest_filepath}': {e}")
    except Exception as e:
        messages.append(
            f"Error: An unexpected error occurred while reading manifest '{manifest_filepath}': {e}"
        )
    return None


def create_package_for_gui(
    manifest_filepath: str,
    output_dir_override: Optional[str] = None,
    package_name_override: Optional[str] = None,
) -> Tuple[bool, Optional[str], List[str]]:
    messages = []
    manifest_data = read_manifest(manifest_filepath, messages)
    if not manifest_data:
        return False, None, messages
    course_id = manifest_data.get("course_id")
    version = manifest_data.get("version", "unknown")
    content_filename = manifest_data.get("content_file")
    if not all([course_id, content_filename]):
        messages.append(
            "Error: Manifest missing critical fields (course_id or content_file)."
        )
        return False, None, messages

    manifest_dir = os.path.dirname(os.path.abspath(manifest_filepath))
    abs_content_filepath = os.path.join(manifest_dir, content_filename)

    if not os.path.exists(abs_content_filepath):
        messages.append(
            f"Error: Course content file '{content_filename}' not found at '{abs_content_filepath}'."
        )
        return False, None, messages

    course_content_data = None
    try:
        with open(abs_content_filepath, "r", encoding="utf-8") as f_content:
            course_content_data = yaml.safe_load(f_content)
    except Exception as e:
        messages.append(
            f"Error: Could not read course content file '{abs_content_filepath}' to find assets: {e}"
        )
        return False, None, messages

    if package_name_override and package_name_override.strip():
        final_package_name_stem = package_name_override.strip()
    else:
        final_package_name_stem = (
            f"{str(course_id).replace(' ', '_')}_{str(version).replace(' ', '_')}"
        )
    final_package_name = f"{final_package_name_stem}.lcpkg"
    output_dir_to_use = output_dir_override if output_dir_override else manifest_dir
    if not os.path.exists(output_dir_to_use):
        try:
            os.makedirs(output_dir_to_use, exist_ok=True)
            messages.append(f"Info: Created output directory: {output_dir_to_use}")
        except OSError as e:
            messages.append(
                f"Error: Could not create output directory '{output_dir_to_use}': {e}"
            )
            return False, None, messages
    output_package_path = os.path.join(output_dir_to_use, final_package_name)
    messages.append(f"Info: Attempting to create course package: {output_package_path}")

    try:
        with zipfile.ZipFile(output_package_path, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest_arcname = "manifest.yaml"
            zf.write(manifest_filepath, arcname=manifest_arcname)
            messages.append(
                f"Info: Added '{os.path.basename(manifest_filepath)}' to package as '{manifest_arcname}'."
            )

            content_arcname = os.path.basename(abs_content_filepath)
            zf.write(abs_content_filepath, arcname=content_arcname)
            messages.append(
                f"Info: Added '{os.path.basename(abs_content_filepath)}' to package as '{content_arcname}'."
            )

            assets_to_add = set()
            if course_content_data and "units" in course_content_data:
                for unit in course_content_data.get("units", []):
                    for lesson in unit.get("lessons", []):
                        for exercise in lesson.get("exercises", []):
                            if isinstance(exercise, dict):
                                audio_path = exercise.get("audio_file")
                                image_path = exercise.get("image_file")
                                if audio_path and isinstance(audio_path, str):
                                    assets_to_add.add(audio_path)
                                if image_path and isinstance(image_path, str):
                                    assets_to_add.add(image_path)

            for asset_relative_path in assets_to_add:
                abs_asset_path = os.path.join(manifest_dir, asset_relative_path)
                if os.path.exists(abs_asset_path):
                    zf.write(abs_asset_path, arcname=asset_relative_path)
                    messages.append(
                        f"Info: Added asset '{asset_relative_path}' to package."
                    )
                else:
                    messages.append(
                        f"Warning: Asset file '{asset_relative_path}' referenced in course content not found at '{abs_asset_path}'. Not added to package."
                    )

        messages.append(f"Success: Course package created at: {output_package_path}")
        return True, output_package_path, messages
    except Exception as e:
        messages.append(f"Error: An unexpected error occurred during packaging: {e}")
        return False, None, messages


def main():
    parser = argparse.ArgumentParser(
        description="Package a LL course into a distributable archive."
    )
    parser.add_argument(
        "manifest_file", help="Path to the manifest.yaml file for the course."
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        help="Directory to save the course package. Defaults to the manifest file's directory.",
    )
    parser.add_argument(
        "--name",
        "-n",
        help="Custom name for the output package (without .zip or .lcpkg extension). Overrides default naming.",
    )

    args = parser.parse_args()

    abs_manifest_path = os.path.abspath(args.manifest_file)

    success, package_path, messages = create_package_for_gui(
        abs_manifest_path, args.output_dir, args.name
    )

    for msg in messages:
        logger.info(msg)

    if success:
        logger.info("Course packaging completed successfully.")
        sys.exit(0)
    else:
        logger.error("Course packaging failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
