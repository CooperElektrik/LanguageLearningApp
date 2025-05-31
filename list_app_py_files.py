import os
import sys

def get_app_py_files_for_lupdate():
    """
    Scans the 'application' directory for .py files and returns their
    paths relative to the project root, suitable for pyside6-lupdate.

    This is a bandaid while I figure out why lupdate's recursive
    scanning doesn't work.
    """
    file_paths = []
    
    # Assume script is run from PROJECT_ROOT.
    # The 'application' directory is expected to be directly under PROJECT_ROOT.
    application_dir = os.path.join(os.getcwd(), "application")

    if not os.path.exists(application_dir):
        print(f"Error: 'application' directory not found at {application_dir}", file=sys.stderr)
        sys.exit(1)

    for root, _, files in os.walk(application_dir):
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                # Get path relative to PROJECT_ROOT
                relative_path = os.path.relpath(full_path, os.getcwd())
                # pyside6-lupdate expects forward slashes even on Windows
                if not relative_path.endswith('__init__.py'):
                    file_paths.append(relative_path.replace(os.sep, '/'))

    return " ".join(file_paths)

if __name__ == "__main__":
    print(f"Run this command: pyside6-lupdate {get_app_py_files_for_lupdate()} -ts application/localization/ll_vi.ts")