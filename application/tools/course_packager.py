import sys
import os
import argparse
import logging
import yaml
import zipfile
from typing import Dict, Any, Optional, Tuple, List

# --- Logging Configuration (used by CLI, GUI will use its own display) ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def read_manifest(manifest_filepath: str, messages: List[str]) -> Optional[Dict[str, Any]]:
    """Reads and parses the manifest YAML file, adding messages to the list."""
    if not os.path.exists(manifest_filepath):
        messages.append(f"Error: Manifest file not found: {manifest_filepath}")
        return None
    try:
        with open(manifest_filepath, 'r', encoding='utf-8') as f:
            manifest_data = yaml.safe_load(f)
        if not isinstance(manifest_data, dict):
            messages.append(f"Error: Manifest file '{manifest_filepath}' does not contain valid YAML dictionary.")
            return None
        messages.append(f"Info: Successfully read manifest: {manifest_filepath}")
        return manifest_data
    except yaml.YAMLError as e:
        messages.append(f"Error: Parsing manifest YAML file '{manifest_filepath}': {e}")
    except Exception as e:
        messages.append(f"Error: An unexpected error occurred while reading manifest '{manifest_filepath}': {e}")
    return None

def create_package_for_gui(
        manifest_filepath: str, 
        output_dir_override: Optional[str] = None, 
        package_name_override: Optional[str] = None
    ) -> Tuple[bool, Optional[str], List[str]]: # Returns (success, package_path, messages)
    """
    Creates a zip package for the course defined by the manifest.
    Returns a tuple: (success_bool, path_to_created_package, list_of_messages).
    """
    messages = []
    success = False
    package_path_created = None

    manifest_data = read_manifest(manifest_filepath, messages)
    if not manifest_data:
        return False, None, messages

    # Validate essential manifest fields
    course_id = manifest_data.get("course_id")
    version = manifest_data.get("version")
    content_filename = manifest_data.get("content_file")

    if not course_id or not course_id.strip():
        messages.append("Error: Manifest is missing or has empty 'course_id'. Cannot determine package name.")
        return False, None, messages
    if not version or not version.strip():
        messages.append("Warning: Manifest is missing or has empty 'version'. Package name will use 'unknown_version'.")
        version = "unknown_version"
    if not content_filename or not content_filename.strip():
        messages.append("Error: Manifest is missing or has empty 'content_file'. Cannot package course content.")
        return False, None, messages

    manifest_dir = os.path.dirname(os.path.abspath(manifest_filepath))
    abs_content_filepath = os.path.join(manifest_dir, content_filename)

    if not os.path.exists(abs_content_filepath):
        messages.append(f"Error: Course content file '{content_filename}' (referenced in manifest) not found at '{abs_content_filepath}'.")
        return False, None, messages

    # Determine output package name and path
    if package_name_override and package_name_override.strip():
        final_package_name_stem = package_name_override.strip()
    else:
        final_package_name_stem = f"{course_id.replace(' ', '_')}_{version.replace(' ', '_')}" # Sanitize spaces for filename
    
    final_package_name = f"{final_package_name_stem}.lcpkg" # LinguaLearn Course Package (custom extension, still a zip)

    output_dir_to_use = output_dir_override if output_dir_override else manifest_dir
    
    if not os.path.exists(output_dir_to_use):
        try:
            os.makedirs(output_dir_to_use, exist_ok=True)
            messages.append(f"Info: Created output directory: {output_dir_to_use}")
        except OSError as e:
            messages.append(f"Error: Could not create output directory '{output_dir_to_use}': {e}")
            return False, None, messages
            
    output_package_path = os.path.join(output_dir_to_use, final_package_name)
    messages.append(f"Info: Attempting to create course package: {output_package_path}")

    try:
        with zipfile.ZipFile(output_package_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add manifest file (as manifest.yaml at the root of zip)
            manifest_arcname = "manifest.yaml" # Standardize name in package
            zf.write(manifest_filepath, arcname=manifest_arcname)
            messages.append(f"Info: Added '{os.path.basename(manifest_filepath)}' to package as '{manifest_arcname}'.")
            
            # Add content file (with its original name at the root of zip)
            content_arcname = os.path.basename(abs_content_filepath)
            zf.write(abs_content_filepath, arcname=content_arcname)
            messages.append(f"Info: Added '{os.path.basename(abs_content_filepath)}' to package as '{content_arcname}'.")

            # --- Future: Add other assets here ---
            # This would involve reading the course content YAML for asset paths
            # and adding them, possibly to a subdirectory like 'assets/'.

        success = True
        package_path_created = output_package_path
        messages.append(f"Success: Course package created at: {output_package_path}")
    except Exception as e:
        messages.append(f"Error: An unexpected error occurred during packaging: {e}")
    
    return success, package_path_created, messages


# --- Original Main Function (kept for CLI compatibility) ---
def main():
    parser = argparse.ArgumentParser(description="Package a LinguaLearn course into a distributable archive.")
    parser.add_argument("manifest_file", help="Path to the manifest.yaml file for the course.")
    parser.add_argument("--output_dir", "-o", help="Directory to save the course package. Defaults to the manifest file's directory.")
    parser.add_argument("--name", "-n", help="Custom name for the output package (without .zip or .lcpkg extension). Overrides default naming.")
    
    args = parser.parse_args()

    abs_manifest_path = os.path.abspath(args.manifest_file)

    success, package_path, messages = create_package_for_gui(abs_manifest_path, args.output_dir, args.name)

    for msg in messages:
        logger.info(msg) # Output all messages to console

    if success:
        logger.info("Course packaging completed successfully.")
        sys.exit(0)
    else:
        logger.error("Course packaging failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()