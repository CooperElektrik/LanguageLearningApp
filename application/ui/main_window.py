import sys
import logging
import os
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QMessageBox,
    QLabel,
    QWidget,
    QFileDialog,
    QVBoxLayout,
    QDockWidget,
    QApplication,
    QPushButton,
    QStatusBar,
)
from PySide6.QtGui import (
    QAction,
    QFont,
    QGuiApplication,
    QCloseEvent,
)  # Keep QCloseEvent
from PySide6.QtCore import (
    Qt,
    QCoreApplication,
    QSettings,
    QTranslator,
    QLocale,
    QEvent,
    QTimer,
)
from PySide6.QtMultimedia import QMediaDevices

from typing import Optional

try:
    from application import settings as app_settings, utils
except ImportError:
    import settings as app_settings
    import utils
from core.course_manager import CourseManager
from core.progress_manager import ProgressManager
from core.whisper_manager import WhisperManager
from core.models import Exercise
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView
from ui.views.progress_view import ProgressView
from ui.views.glossary_view import GlossaryView
from ui.views.course_selection_view import CourseSelectionView
from ui.views.course_editor_view import CourseEditorView
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.initial_audio_setup_dialog import InitialAudioSetupDialog
from ui.dialogs.dev_info_dialog import DevInfoDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.course_manager: Optional[CourseManager] = None
        self.progress_manager: Optional[ProgressManager] = None
        self.whisper_manager = WhisperManager(self)
        self.current_translator: Optional[QTranslator] = (
            None  # Store the active translator
        )

        self.setWindowTitle(self.tr("LanguageLearningApp"))
        self.setGeometry(100, 100, 1024, 768)

        # Main stack to switch between app states (selection, learning, editing)
        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)  # Set this ONCE and never change it.

        # Create the permanent course selection page
        self.course_selection_view = CourseSelectionView()
        self.course_selection_view.course_selected.connect(
            self._load_course_for_learning
        )
        self.main_stack.addWidget(self.course_selection_view)

        # Placeholders for other modes' main widgets
        self.learning_widget = None
        self.editor_view = None

        # Status bar button for dev info
        self.dev_info_button: Optional[QPushButton] = None
        self._setup_status_bar()

        self.current_translator = utils.setup_initial_translation(
            QApplication.instance()
        )
        self._setup_ui_elements()  # Set up early UI related stuff
        self._load_and_apply_initial_theme()
        self._return_to_selection_screen()  # Start in the selection screen

    def _load_and_apply_initial_theme(self):
        q_settings = QSettings()
        theme_name = q_settings.value(
            app_settings.QSETTINGS_KEY_UI_THEME, "Fancy Light", type=str
        )
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str):
        logger.info(f"Attempting to apply theme: {theme_name}")
        qss_filename = app_settings.AVAILABLE_THEMES.get(theme_name)

        if theme_name == "System" or qss_filename == "system_default":
            QApplication.instance().setStyleSheet(
                ""
            )  # Clear stylesheet to use system default
            logger.info("Applied system default theme.")
            return

        if qss_filename:
            theme_abs_path = utils.get_resource_path(
                os.path.join(app_settings.THEME_DIR, qss_filename)
            )
            utils.apply_stylesheet(
                QApplication.instance(), theme_abs_path
            )  # Use a utility for this
        else:
            logger.warning(
                f"Theme '{theme_name}' not found in AVAILABLE_THEMES. Applying system default."
            )
            QApplication.instance().setStyleSheet("")

    def apply_font_size(self, new_size: int):
        """
        Applies a new base font size to the entire application.
        """
        font = QApplication.instance().font()
        font.setPointSize(new_size)
        QApplication.instance().setFont(font)
        logger.info(f"Global font size changed to: {new_size} pt")

    def _setup_ui_elements(self):
        """
        Set font before any widgets are created (MainWindow's UI)
        """
        q_settings = QSettings()
        saved_font_size = q_settings.value(
            app_settings.QSETTINGS_KEY_FONT_SIZE,
            app_settings.DEFAULT_FONT_SIZE,
            type=int,
        )
        self.apply_font_size(saved_font_size)  # Apply saved or default font size

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.dev_info_button = QPushButton("Dev Info")
        self.dev_info_button.setObjectName("dev_info_status_button")
        self.dev_info_button.setToolTip(
            "Show current course/exercise developer information"
        )
        self.dev_info_button.clicked.connect(self._show_dev_info_dialog)
        self.status_bar.addPermanentWidget(self.dev_info_button)
        # Visibility is controlled by _update_dev_info_button_visibility
        self._update_dev_info_button_visibility()

    def _load_course_for_learning(self, manifest_path: str):
        """Initializes services and UI for the LEARNING mode."""
        self.course_manager = CourseManager(manifest_path=manifest_path, parent=self)
        if not self.course_manager.course:
            QMessageBox.critical(
                self, self.tr("Course Load Error"), self.tr("Failed to load course.")
            )
            return
        self.progress_manager = ProgressManager(
            course_id=self.course_manager.course.course_id
        )

        self._setup_learning_ui()
        self.setWindowTitle(f"LL - {self.course_manager.get_course_title()}")
        self.show_course_overview()  # Shows the central placeholder

        # Check and show onboarding AFTER learning UI is set up and visible
        QTimer.singleShot(
            150, self._check_and_show_onboarding
        )  # Small delay for UI to settle
        self._update_dev_info_button_visibility()
        QTimer.singleShot(200, self._check_and_show_initial_setup)

    def _load_course_for_editing(self):  # Keep existing definition
        """Opens a file dialog and loads a course into the EDITOR mode."""
        manifest_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Open Course Manifest"), "", "YAML Files (*.yaml)"
        )
        if not manifest_path:
            return

        editor_course_manager = CourseManager(manifest_path=manifest_path, parent=self)
        if not editor_course_manager.course:
            QMessageBox.critical(
                self,
                self.tr("Course Load Error"),
                self.tr("Failed to load selected course for editing."),
            )

        self._setup_editing_ui(editor_course_manager)
        self.setWindowTitle(f"LL Editor - {editor_course_manager.get_course_title()}")
        self._update_dev_info_button_visibility()

    def _setup_learning_ui(self):
        """Builds the main learning interface with docks and views."""
        # self._clear_dynamic_widgets()

        # The learning UI has docks, so it needs its own QMainWindow instance.
        # We then add this entire QMainWindow as a page to the main stack.
        self.learning_widget = QMainWindow()

        right_panel_stack = QStackedWidget()
        self.learning_widget.setCentralWidget(right_panel_stack)

        self.navigation_dock_widget = QDockWidget(
            self.tr("Course Navigation"), self.learning_widget
        )
        course_overview_view = CourseOverviewView(
            self.course_manager, self.progress_manager
        )
        self.navigation_dock_widget.setWidget(course_overview_view)
        self.learning_widget.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock_widget
        )

        self.progress_dock_widget = QDockWidget(
            self.tr("Progress"), self.learning_widget
        )
        progress_view = ProgressView(self.course_manager, self.progress_manager)
        self.progress_dock_widget.setWidget(progress_view)
        self.learning_widget.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.progress_dock_widget
        )
        self.progress_dock_widget.setVisible(False) # Hide initially

        # We need to store these view references to switch the stack inside this learning_widget
        self.learning_ui_views = {
            "overview": course_overview_view,
            "progress": progress_view,
            "lesson": LessonView(
                self.course_manager, self.progress_manager, self.whisper_manager
            ),
            "review": ReviewView(
                self.course_manager, self.progress_manager, self.whisper_manager
            ),
            "glossary": GlossaryView(self.course_manager),
            "placeholder": QLabel(
                self.tr("Select a lesson or start a review."), alignment=Qt.AlignCenter
            ),
            "central_stack": right_panel_stack,
        }

        right_panel_stack.addWidget(self.learning_ui_views["placeholder"])
        right_panel_stack.addWidget(self.learning_ui_views["lesson"])
        right_panel_stack.addWidget(self.learning_ui_views["review"])
        right_panel_stack.addWidget(self.learning_ui_views["glossary"])

        course_overview_view.lesson_selected.connect(self.start_lesson)
        course_overview_view.start_review_session_requested.connect(
            self.start_review_session
        )
        self.learning_ui_views["review"].review_session_finished.connect(
            self.show_course_overview
        )
        self.learning_ui_views["review"].back_to_overview_signal.connect(
            self.show_course_overview
        )
        self.learning_ui_views["lesson"].back_to_overview_signal.connect(
            self.show_course_overview
        )

        self.main_stack.addWidget(self.learning_widget)
        self.main_stack.setCurrentWidget(self.learning_widget)
        self._setup_learning_menu()

        self.menuBar().setVisible(False)

    def _setup_editing_ui(self, course_manager):
        """Builds the editing interface."""
        # self._clear_dynamic_widgets()

        self.editor_view = CourseEditorView(course_manager)
        self.editor_view.editor_closed.connect(self._return_to_selection_screen)

        self.main_stack.addWidget(self.editor_view)
        self.main_stack.setCurrentWidget(self.editor_view)
        self.menuBar().clear()

        self.menuBar().setVisible(False)

    def _setup_file_menu(self):
        """Menu for the initial selection screen."""
        self.menuBar().clear()
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(
            self.tr("Open Course for Editing..."), self._load_course_for_editing
        )
        file_menu.addSeparator()
        file_menu.addAction("&Settings...", self.show_settings_dialog)
        file_menu.addSeparator()
        file_menu.addAction("&Quit", self.close)

    def _setup_learning_menu(self):
        """Menu for the main learning mode."""
        # Use the menu bar from the nested QMainWindow for learning mode
        menu_bar = self.learning_widget.menuBar()
        menu_bar.clear()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(
            self.tr("Return to Course Selection"), self._return_to_selection_screen
        )
        file_menu.addSeparator()
        file_menu.addAction("&Settings...", self.show_settings_dialog)

        learning_menu = menu_bar.addMenu("&Learning")
        learning_menu.addAction(self.tr("Start Due Review"), self.start_review_session)

        view_menu = menu_bar.addMenu("&View")
        if hasattr(self, "navigation_dock_widget") and self.navigation_dock_widget:
            view_menu.addAction(self.navigation_dock_widget.toggleViewAction())
        if hasattr(self, "progress_dock_widget") and self.progress_dock_widget:
            view_menu.addAction(self.progress_dock_widget.toggleViewAction())

    def _return_to_selection_screen(self):
        self._clear_dynamic_widgets()
        self.setWindowTitle(self.tr("LanguageLearningApp"))
        self.main_stack.setCurrentWidget(self.course_selection_view)
        self.menuBar().setVisible(True)
        self._update_dev_info_button_visibility()

        self._setup_file_menu()

    def _clear_dynamic_widgets(self):
        """Removes learning or editor widgets from the stack to prevent memory leaks."""
        if self.learning_widget:
            self.main_stack.removeWidget(self.learning_widget)
            self.learning_widget.deleteLater()
            self.learning_widget = None
            self.learning_ui_views = {}
        if self.editor_view:
            self.main_stack.removeWidget(self.editor_view)
            self.editor_view.deleteLater()
            self.editor_view = None

        self.course_manager = None
        self.progress_manager = None
        self._update_dev_info_button_visibility()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.whisper_manager, self)  # Pass the manager
        dialog.theme_changed.connect(self.apply_theme)  # Connect to the new signal
        dialog.locale_changed.connect(self.apply_locale)
        dialog.font_size_changed.connect(
            self.apply_font_size
        )  # Connect font size changes
        dialog.exec()

    def apply_locale(self, locale_code: str):
        """Applies a new locale to the application."""
        app = QApplication.instance()
        if self.current_translator:
            app.removeTranslator(self.current_translator)
            self.current_translator = None
            logger.debug("Removed existing translator.")

        actual_locale_to_load = ""
        if locale_code == app_settings.DEFAULT_LOCALE:  # "System"
            actual_locale_to_load = (
                app_settings.FORCE_LOCALE
                if app_settings.FORCE_LOCALE
                else QLocale.system().name()
            )
        else:
            actual_locale_to_load = locale_code

        new_translator = QTranslator(app)
        qm_file_path = utils.get_resource_path(
            os.path.join(
                app_settings.LOCALIZATION_DIR, f"app_{actual_locale_to_load}.qm"
            )
        )

        loaded_successfully = new_translator.load(qm_file_path)
        if not loaded_successfully:  # Try short code if full (e.g. en_US) failed
            short_locale_code = actual_locale_to_load.split("_")[0]
            if short_locale_code != actual_locale_to_load:
                qm_file_path = utils.get_resource_path(
                    os.path.join(
                        app_settings.LOCALIZATION_DIR, f"app_{short_locale_code}.qm"
                    )
                )
                loaded_successfully = new_translator.load(qm_file_path)

        if loaded_successfully:
            app.installTranslator(new_translator)
            self.current_translator = new_translator
            logger.info(
                f"Successfully loaded and installed translator for locale code: {actual_locale_to_load} from {qm_file_path}"
            )
        else:
            logger.warning(
                f"Failed to load translator for locale code: {actual_locale_to_load}. Tried path: {qm_file_path}. UI might not update."
            )

        self._retranslate_main_window_ui()

    def _update_dev_info_button_visibility(self):
        if self.dev_info_button:
            is_dev_mode = utils.is_developer_mode_active()
            # Only show if in dev mode AND a course is loaded (for learning or editing)
            # Or always show in dev mode, and dialog handles "no course"
            self.dev_info_button.setVisible(is_dev_mode)

    def _show_dev_info_dialog(self):
        current_exercise: Optional[Exercise] = None

        # Check if we are in learning mode and which view is active
        if self.learning_widget and self.learning_widget.isVisible():
            central_stack = self.learning_ui_views.get("central_stack")
            if central_stack:
                current_player_widget = central_stack.currentWidget()
                if hasattr(current_player_widget, "current_exercise_obj"):
                    current_exercise = current_player_widget.current_exercise_obj

        dialog = DevInfoDialog(
            self.course_manager, self.progress_manager, current_exercise, self
        )
        dialog.exec()

    def _check_and_show_initial_setup(self):
        """Checks if the initial audio setup has been done and shows the dialog if not."""
        q_settings = QSettings()
        setup_done = q_settings.value(
            app_settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, False, type=bool
        )

        # Only show if not done, and if there are any audio input devices.
        if not setup_done and QMediaDevices.audioInputs():
            logger.info("Initial audio setup not completed. Showing setup dialog.")
            dialog = InitialAudioSetupDialog(self)
            dialog.exec()
            # After this, settings are saved. The app will use them on the next exercise.
        elif not setup_done and not QMediaDevices.audioInputs():
            logger.warning("Initial audio setup skipped: No audio input devices found.")

    def _check_and_show_onboarding(self):
        """Checks if onboarding has been seen and shows it if not."""
        if not self.learning_widget or not self.learning_widget.isVisible():
            # If learning widget isn't ready, try again shortly
            QTimer.singleShot(250, self._check_and_show_onboarding)
            return

        q_settings = QSettings()
        onboarding_seen = q_settings.value(
            app_settings.QSETTINGS_KEY_GLOBAL_ONBOARDING_SEEN, False, type=bool
        )

        if not onboarding_seen:
            logger.info(
                "First time loading a course or onboarding not seen. Displaying onboarding message."
            )

            title = self.tr("Welcome to LanguageLearningApp!")
            message = self.tr(
                "Welcome to your language course!\n\n"
                "Here's a quick guide to the interface:\n\n"
                "• Left Panel (Course Navigation):\n"
                "  - Displays course units and lessons. Click a lesson to start.\n"
                "  - Use 'Review Due' or 'Review Weak' to practice.\n\n"
                "• Right Panel (Progress):\n"
                "  - Shows your XP, study streak, and achievements.\n\n"
                "• Central Area: Lessons and review exercises appear here.\n\n"
                "Happy learning!"
            )
            QMessageBox.information(
                self.learning_widget, title, message
            )  # Parent to learning_widget

            q_settings.setValue(app_settings.QSETTINGS_KEY_GLOBAL_ONBOARDING_SEEN, True)
            logger.info("Onboarding message shown and flag set.")

    # --- Learning Mode Methods ---
    def show_course_overview(self):
        if not self.learning_widget:
            return
        self.learning_ui_views["overview"].refresh_view()
        self.learning_ui_views["progress"].refresh_view()
        self.learning_ui_views["central_stack"].setCurrentWidget(
            self.learning_ui_views["placeholder"]
        )

    def start_lesson(self, lesson_id: str):
        if not self.learning_widget:
            return
        lesson_view = self.learning_ui_views["lesson"]
        lesson_view.start_lesson(lesson_id)
        self.learning_ui_views["central_stack"].setCurrentWidget(lesson_view)

    def start_review_session(self):
        if not self.learning_widget:
            return
        review_view = self.learning_ui_views["review"]
        review_view.start_review_session()
        if review_view.total_exercises_in_session > 0:
            self.learning_ui_views["central_stack"].setCurrentWidget(review_view)

    # --- Overridden Events ---
    def closeEvent(self, event: QCloseEvent):  # Added type hint
        if self.progress_manager:
            self.progress_manager.save_progress()

        self.whisper_manager.unload_model()

        if self.editor_view and self.editor_view.is_dirty:
            self.editor_view.close_editor()
            if self.editor_view.isVisible():
                event.ignore()
                return

        super().closeEvent(event)

    def changeEvent(self, event: QEvent):  # Add changeEvent for MainWindow itself
        if event.type() == QEvent.Type.LanguageChange:
            logger.debug("MainWindow received LanguageChange event.")
            self._retranslate_main_window_ui()
        super().changeEvent(event)

    def _retranslate_main_window_ui(self):
        """Retranslates parts of the MainWindow UI that might not update automatically."""
        # Window Title
        current_title = self.windowTitle()
        if self.course_manager and self.course_manager.course:
            self.setWindowTitle(f"LL - {self.course_manager.get_course_title()}")
        elif self.editor_view:
            # Assuming editor_view has a way to get its course title
            pass  # self.setWindowTitle(f"LL Editor - {self.editor_view.get_course_title()}")
        else:
            self.setWindowTitle(self.tr("LanguageLearningApp"))

        # Menus (re-creating them is a common way to ensure re-translation)
        if self.main_stack.currentWidget() == self.course_selection_view:
            self._setup_file_menu()
        elif self.main_stack.currentWidget() == self.learning_widget:
            self._setup_learning_menu()

        # Dock widget titles (if they exist and are set directly)
        if hasattr(self, "navigation_dock_widget") and self.navigation_dock_widget:
            self.navigation_dock_widget.setWindowTitle(self.tr("Course Navigation"))
        if hasattr(self, "progress_dock_widget") and self.progress_dock_widget:
            self.progress_dock_widget.setWindowTitle(self.tr("Progress"))

        # Retranslate currently visible views if they have a retranslateUi method
        # This is a fallback / explicit call, QEvent.LanguageChange should handle most of it.
        current_main_widget = self.main_stack.currentWidget()
        if hasattr(current_main_widget, "retranslateUi"):
            logger.debug(
                f"Explicitly calling retranslateUi for {current_main_widget.__class__.__name__}"
            )
            current_main_widget.retranslateUi()

        if self.learning_widget and self.learning_widget.isVisible():
            # The learning_widget is a QMainWindow, its menuBar should update.
            # Its internal views (overview, progress, lesson, etc.) should handle their own retranslation via changeEvent.
            # pass

            if self.dev_info_button:
                self.dev_info_button.setText(self.tr("Dev Info"))

        # Inform child views if necessary (more advanced)
        # For now, rely on QEvent.LanguageChange and the restart prompt.
        logger.debug("MainWindow UI elements re-translation attempted.")
