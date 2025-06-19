# LL: A PySide6 Language Learning Platform & Content Editor

Welcome to LL, a desktop application inspired by Duolingo for interactive language learning, built with PySide6. This project includes a comprehensive suite of tools for creating, managing, and distributing custom language course content.

>[!IMPORTANT]
>This project currently primarily supports Windows 10/11.

## Table of Contents

- [Features](#features)
- [Setup](#setup)
- [How to Run](#how-to-run)
- [Compilation to Executable](#compilation-to-executable)

## Features

LL offers a rich set of features to enhance your language learning journey:

*   **Interactive Lessons & Review:** Engage with diverse exercise types, including translation, multiple-choice, fill-in-the-blank, and sentence jumble.
*   **Spaced Repetition System (SRS):** Exercises are intelligently scheduled for review to maximize retention based on your performance.
*   **Pronunciation Practice (Whisper):**
    *   Record yourself speaking and get instant transcription.
    *   Select your preferred **microphone input device**.
    *   Choose between **Whisper Base, Small, or Medium models** for transcription accuracy (models are downloaded on first use).
    *   **Load/unload** speech-to-text models from memory on demand via a dedicated button or through settings.
*   **Contextual Glossary Lookup:** Click on highlighted vocabulary within sentences or notes to instantly view detailed glossary definitions.
*   **Detailed Mistake Explanations:** Receive specific feedback on incorrect answers to understand *why* you made a mistake and improve faster.
*   **Keyboard Shortcuts:** Navigate exercises and submit answers efficiently using intuitive keyboard commands (e.g., number keys for options, Ctrl+H for hints, Ctrl+N for notes).
*   **Personalized Progress Tracking:** Monitor your total XP, study streaks, and unlock achievements as you progress.
*   **Customizable Settings:** Adjust audio (volume, sound effects, autoplay), UI theme, font size, and developer options.
*   **User Onboarding:** A helpful welcome guide appears for new users, explaining core features and initial setup.
*   **Course Content Editor:** A built-in editor allows for creating and modifying course units, lessons, and exercises (currently basic, with plans for more advanced features).

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
    .\venv\Scripts\activate
    ```

4.  **Install Dependencies:**
    All required Python packages are listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```
    *Note: For `faster-whisper` (used for pronunciation), ensure you have a compatible PyTorch installation. Refer to PyTorch's website for CUDA/CPU versions if `pip install torch` doesn't work out-of-the-box. A sufficiently powerful computer is required to use larger models (i.e. Whisper medium).*

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