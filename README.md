# LL: A PySide6 Language Learning Platform & Content Editor

Welcome to LL, a desktop application inspired by Duolingo for interactive language learning, built with PySide6. This project includes a comprehensive suite of tools for creating, managing, and distributing custom language course content.

>[!IMPORTANT]
>This project only supports Windows 10/11.

## Table of Contents

- [Setup](#setup)
- [How to Run](#how-to-run)
- [Compilation to Executable](#compilation-to-executable)

## Setup

To set up and run the LL project, follow these steps:

1.  **Clone the Repository (or download the files):**
    ```bash
    git clone https://github.com/CooperElektrik/LanguageLearningApp
    cd LanguageLearningApp
    ```

2.  **Create a Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    ```bash
    .\venv\Scripts\activate # Or scripts\activation.bat, which does the same thing
    ```

4.  **Install Dependencies:**
    All required Python packages are listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```
    See [Nuitka's setup guide](https://nuitka.net/user-documentation/tutorial-setup-and-build.html) for compilation.

## How to Run

The easiest and canonical way to run the different components of the LL project is by using the provided `run_menu.bat` script.

1.  **Open Command Prompt/Terminal:** Navigate to the `PROJECT_ROOT` directory where `run_menu.bat` is located.
2.  **Run the Menu Script:**
    ```bash
    run_menu.bat
    ```
3.  **Follow the Menu:** A command-line menu will appear, allowing you to choose from a list of what to run.

    When prompted for file paths, you can provide paths relative to `PROJECT_ROOT` (e.g., `application\manifest.yaml`) or full absolute paths.

## Compilation to Executable

The `run_menu.bat` script provides options to compile the `main.py` application and the `main_editor.py` tool into standalone Windows executables (`.exe`) using Nuitka.

-   Compiled applications will be placed in the `application/dist/` directory.
-   Ensure Nuitka and a compatible C/C++ compiler are installed before attempting compilation.