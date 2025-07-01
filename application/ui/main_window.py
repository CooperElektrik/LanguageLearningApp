import sys
import logging
import os
import subprocess
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
    QToolBar,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import QPropertyAnimation, QPoint, QEasingCurve
from PySide6.QtGui import (
    QAction,
    QFont,
    QGuiApplication,
    QCloseEvent,
    QIcon,
)

from PySide6.QtCore import (
    Qt,
    QCoreApplication,
    QSettings,
    QTranslator,
    QLocale,
    QEvent,
    QTimer,
    QSize,
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
from core.models import Exercise
from ui.views.course_overview_view import CourseOverviewView
from ui.views.lesson_view import LessonView
from ui.views.review_view import ReviewView
from ui.views.progress_view import ProgressView
from ui.views.glossary_view import GlossaryView
from ui.views.course_selection_view import CourseSelectionView
from ui.views.course_editor_view import CourseEditorView
from ui.dialogs.unified_setup_dialog import UnifiedSetupDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.dev_info_dialog import DevInfoDialog
from ui.dialogs.help_dialog import HelpDialog
from ui.dialogs.pyglet_script_runner_dialog import PygletScriptRunnerDialog
from ui.widgets.animated_placeholder import AnimatedPlaceholder

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, stt_manager, parent=None):
        super().__init__(parent)
        self.course_manager: Optional[CourseManager] = None
        self.progress_manager: Optional[ProgressManager] = None
        self.stt_manager = stt_manager
        self.current_translator: Optional[QTranslator] = (
            None  # Store the active translator
        )

        logger.info("MainWindow initializing...")
        self.setWindowTitle(self.tr("LanguageLearningApp"))
        self.setGeometry(100, 100, 1024, 768)
        self.showFullScreen()

        # Main stack to switch between app states (selection, learning, editing)
        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)
        logger.debug("Main QStackedWidget set as central widget.")

        self._setup_main_toolbar()
        self._setup_main_menu() # <<<< UNIFIED MENU SETUP

        # Create the permanent course selection page
        self.course_selection_view = CourseSelectionView()
        self.course_selection_view.course_selected.connect(
            self._load_course_for_learning
        )
        self.main_stack.addWidget(self.course_selection_view)
        logger.debug("CourseSelectionView added to main stack.")

        # Placeholders for other modes' main widgets
        self.learning_widget = None
        self.editor_view = None

        # Animation objects for learning view's central stack
        self.central_stack_fade_effect: Optional[QGraphicsOpacityEffect] = None
        self.central_stack_fade_animation: Optional[QPropertyAnimation] = None

        # Status bar button for dev info
        self.dev_info_button: Optional[QPushButton] = None
        self._setup_status_bar()

        self.current_translator = utils.setup_initial_translation(
            QApplication.instance()
        )
        self._setup_ui_elements()
        self._load_and_apply_initial_theme()
        self._return_to_selection_screen() # This will set the initial menu state

        # New: Check for initial UI setup after everything is ready
        self._setup_animations()

        # New: Check for initial UI setup after everything is ready
        QTimer.singleShot(500, self._check_and_show_initial_setup)
        logger.info("MainWindow initialization complete.")

    def _setup_animations(self):
        self.fade_effect = QGraphicsOpacityEffect(self)
        self.fade_animation = QPropertyAnimation(self.fade_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.main_stack.currentChanged.connect(self._animate_fade_transition)
        logger.debug("Main stack animations set up.")

    def _animate_fade_transition(self, index):
        current_widget = self.main_stack.widget(index)

        # --- FIX ---
        # The learning_widget has its own internal animation system. Applying a
        # second graphics effect to it from the main stack causes QPainter
        # conflicts. We must prevent this.
        if current_widget is self.learning_widget:
            # Explicitly remove any effect from the main animation system.
            # This ensures the internal animations of the learning view
            # can run without conflicts.
            if current_widget.graphicsEffect() is not None:
                 current_widget.setGraphicsEffect(None)
            return  # Stop here and let the internal animation handle the fade

        # For all other widgets, apply the standard fade-in.
        self._animate_fade_in(current_widget)

    def _animate_fade_in(self, widget):
        if widget is None: return
        widget.setGraphicsEffect(self.fade_effect)
        self.fade_animation.setTargetObject(self.fade_effect)
        self.fade_animation.setPropertyName(b"opacity")
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

    def _animate_central_stack_fade(self, index: int):
        """Animates a fade-in for the central widget stack in the learning view."""
        if self.central_stack_fade_animation and self.central_stack_fade_animation.targetObject():
            # Stop any ongoing animation
            self.central_stack_fade_animation.stop()
            # Set start and end values for a fade-in effect
            self.central_stack_fade_animation.setStartValue(0.0)
            self.central_stack_fade_animation.setEndValue(1.0)
            # Start the animation
            self.central_stack_fade_animation.start()

    def _setup_main_toolbar(self):
        self.main_toolbar = QToolBar("Main Toolbar")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setFloatable(False)
        self.main_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.main_toolbar)

        self._update_toolbar_icons()

    def _update_toolbar_icons(self):
        self.main_toolbar.clear()

        q_settings = QSettings()
        theme_name = q_settings.value(
            app_settings.QSETTINGS_KEY_UI_THEME, "Nao Tomori", type=str
        )

        is_dark_theme = app_settings.AVAILABLE_THEMES.get(theme_name, {}).get("is_dark", False)
        icon_suffix = "_dark.png" if is_dark_theme else "_light.png"

        # Icon paths
        exit_icon_path = utils.get_resource_path(os.path.join("assets", "icons", f"power{icon_suffix}"))
        settings_icon_path = utils.get_resource_path(os.path.join("assets", "icons", f"cog{icon_suffix}"))
        help_icon_path = utils.get_resource_path(os.path.join("assets", "icons", f"help{icon_suffix}"))
        pyglet_icon_path = utils.get_resource_path(os.path.join("assets", "icons", f"code{icon_suffix}"))

        # Exit Action
        exit_action = QAction(QIcon(exit_icon_path), self.tr("Exit"), self)
        exit_action.setToolTip(self.tr("Close the application"))
        exit_action.triggered.connect(self.close)
        self.main_toolbar.addAction(exit_action)

        # Settings Action
        settings_action = QAction(QIcon(settings_icon_path), self.tr("Settings"), self)
        settings_action.setToolTip(self.tr("Open application settings"))
        settings_action.triggered.connect(self.show_settings_dialog)
        self.main_toolbar.addAction(settings_action)

        # Help Action
        help_action = QAction(QIcon(help_icon_path), self.tr("Help"), self)
        help_action.setToolTip(self.tr("Show help and FAQ"))
        help_action.triggered.connect(self._show_help_dialog)
        self.main_toolbar.addAction(help_action)

        # Pyglet App Action
        pyglet_action = QAction(QIcon(pyglet_icon_path), self.tr("Pyglet App"), self)
        pyglet_action.setToolTip(self.tr("Run a sample Pyglet application"))
        pyglet_action.triggered.connect(self._run_pyglet_app)
        self.main_toolbar.addAction(pyglet_action)

    def _show_help_dialog(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def _run_pyglet_app(self):
        dialog = PygletScriptRunnerDialog(self)
        dialog.exec()

    def _load_and_apply_initial_theme(self):
        q_settings = QSettings()
        theme_name = q_settings.value(
            app_settings.QSETTINGS_KEY_UI_THEME, "Nao Tomori", type=str
        )
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str):
        logger.info(f"Attempting to apply theme: {theme_name}")
        self._update_toolbar_icons()
        qss_filename = app_settings.AVAILABLE_THEMES.get(theme_name)["file"]

        if theme_name == "System" or qss_filename == "system_default":
            QApplication.instance().setStyleSheet("")
            logger.info("Applied system default theme.")
            return

        if qss_filename:
            theme_abs_path = utils.get_resource_path(
                os.path.join(app_settings.THEME_DIR, qss_filename)
            )
            utils.apply_stylesheet(QApplication.instance(), theme_abs_path)
        else:
            logger.warning(
                f"Theme '{theme_name}' not found in AVAILABLE_THEMES. Applying system default."
            )
            QApplication.instance().setStyleSheet("")

    def apply_font_size(self, new_size: int):
        font = QApplication.instance().font()
        font.setPointSize(new_size)
        QApplication.instance().setFont(font)
        logger.info(f"Global font size changed to: {new_size} pt")

    def _setup_ui_elements(self):
        q_settings = QSettings()
        saved_font_size = q_settings.value(
            app_settings.QSETTINGS_KEY_FONT_SIZE,
            app_settings.DEFAULT_FONT_SIZE,
            type=int,
        )
        self.apply_font_size(saved_font_size)

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
        self._update_dev_info_button_visibility()

    def _load_course_for_learning(self, manifest_path: str):
        logger.info(f"Attempting to load course for learning from manifest: {manifest_path}")
        self.course_manager = CourseManager(manifest_path=manifest_path, parent=self)
        if not self.course_manager.course:
            logger.error(f"Failed to load course from {manifest_path}. Displaying error message.")
            QMessageBox.critical(
                self, self.tr("Course Load Error"), self.tr("Failed to load course.")
            )
            return
        logger.info(f"Course '{self.course_manager.get_course_title()}' loaded successfully for learning.")
        self.progress_manager = ProgressManager(
            course_id=self.course_manager.course.course_id
        )
        logger.debug(f"ProgressManager initialized for course ID: {self.course_manager.course.course_id}")

        self._setup_learning_ui()
        self.setWindowTitle(f"LL - {self.course_manager.get_course_title()}")
        
        # Ensure the learning_widget is added before setting it as current
        if self.learning_widget not in [self.main_stack.widget(i) for i in range(self.main_stack.count())]:
            self.main_stack.addWidget(self.learning_widget)
        
        # Set the learning_widget as current. The transition is handled by the
        # main_stack.currentChanged signal, which has special logic to prevent
        # QPainter errors with the learning view's internal animations.
        self.main_stack.setCurrentWidget(self.learning_widget)
        
        QTimer.singleShot(150, self._check_and_show_onboarding)
        self._update_dev_info_button_visibility()
        self._update_menu_state()

    def _load_course_for_editing(self):
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
            return

        self._setup_editing_ui(editor_course_manager)
        self.setWindowTitle(f"LL Editor - {editor_course_manager.get_course_title()}")
        self._update_dev_info_button_visibility()

    def _setup_learning_ui(self):
        self.learning_widget = QMainWindow()
        # IMPORTANT: Prevent the nested QMainWindow from having its own menu bar
        self.learning_widget.setMenuBar(None)

        right_panel_stack = QStackedWidget()
        self.learning_widget.setCentralWidget(right_panel_stack)

        # --- Animation setup for the central learning area ---
        self.central_stack_fade_effect = QGraphicsOpacityEffect(right_panel_stack)
        right_panel_stack.setGraphicsEffect(self.central_stack_fade_effect)

        self.central_stack_fade_animation = QPropertyAnimation(
            self.central_stack_fade_effect, b"opacity"
        )
        self.central_stack_fade_animation.setDuration(250)
        self.central_stack_fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        right_panel_stack.currentChanged.connect(self._animate_central_stack_fade)
        # --- END ---

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
        self.progress_dock_widget.setVisible(False)

        # Store the toggle actions to add them to the main menu
        self.toggle_nav_dock_action = self.navigation_dock_widget.toggleViewAction()
        self.toggle_progress_dock_action = self.progress_dock_widget.toggleViewAction()
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.toggle_nav_dock_action)
        self.view_menu.addAction(self.toggle_progress_dock_action)

        self.learning_ui_views = {
            "overview": course_overview_view,
            "progress": progress_view,
            "lesson": LessonView(
                self.course_manager, self.progress_manager, self.stt_manager
            ),
            "review": ReviewView(
                self.course_manager, self.progress_manager, self.stt_manager
            ),
            "glossary": GlossaryView(self.course_manager),
            "placeholder": AnimatedPlaceholder(),
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
        self._update_menu_state()

    def _setup_editing_ui(self, course_manager):
        self.editor_view = CourseEditorView(course_manager)
        self.editor_view.editor_closed.connect(self._return_to_selection_screen)

        self.main_stack.addWidget(self.editor_view)
        self.main_stack.setCurrentWidget(self.editor_view)
        self._update_menu_state()

    def _setup_main_menu(self):
        """Creates the main, unified menu bar and all possible actions ONCE."""
        self.menuBar().clear()

        # --- File Menu ---
        file_menu = self.menuBar().addMenu(self.tr("&File"))
        self.return_to_selection_action = QAction(self.tr("Return to Course Selection"), self)
        self.return_to_selection_action.triggered.connect(self._return_to_selection_screen)
        file_menu.addAction(self.return_to_selection_action)

        self.open_for_editing_action = QAction(self.tr("Open Course for Editing..."), self)
        self.open_for_editing_action.triggered.connect(self._load_course_for_editing)
        file_menu.addAction(self.open_for_editing_action)

        file_menu.addSeparator()
        self.settings_action = QAction(self.tr("&Settings..."), self)
        self.settings_action.triggered.connect(self.show_settings_dialog)
        file_menu.addAction(self.settings_action)
        
        file_menu.addSeparator()
        self.quit_action = QAction(self.tr("&Quit"), self)
        self.quit_action.triggered.connect(self.close)
        file_menu.addAction(self.quit_action)

        # --- Learning Menu ---
        learning_menu = self.menuBar().addMenu(self.tr("&Learning"))
        self.start_due_review_action = QAction(self.tr("Start Due Review"), self)
        self.start_due_review_action.triggered.connect(self.start_review_session)
        learning_menu.addAction(self.start_due_review_action)

        # --- View Menu ---
        self.view_menu = self.menuBar().addMenu(self.tr("&View"))
        toggle_toolbar_action = self.main_toolbar.toggleViewAction()
        toggle_toolbar_action.setText(self.tr("Toggle Toolbar"))
        self.view_menu.addAction(toggle_toolbar_action)

        # Dock actions will be added dynamically when the learning UI is created
        self.toggle_nav_dock_action = None
        self.toggle_progress_dock_action = None

    def _update_menu_state(self):
        """Updates the enabled/disabled state of all menu actions based on the current view."""
        current_view = self.main_stack.currentWidget()
        is_selection_view = current_view == self.course_selection_view
        is_learning_view = current_view == self.learning_widget
        is_editor_view = current_view == self.editor_view

        # File Menu Actions
        self.return_to_selection_action.setEnabled(is_learning_view or is_editor_view)
        self.open_for_editing_action.setEnabled(is_selection_view)
        # Settings and Quit are always enabled
        self.settings_action.setEnabled(True)
        self.quit_action.setEnabled(True)

        # Learning Menu Actions
        self.start_due_review_action.setEnabled(is_learning_view)
        
        # View Menu Dock Actions (check if they exist)
        if self.toggle_nav_dock_action:
            self.toggle_nav_dock_action.setEnabled(is_learning_view)
            self.toggle_nav_dock_action.setVisible(is_learning_view)
        if self.toggle_progress_dock_action:
            self.toggle_progress_dock_action.setEnabled(is_learning_view)
            self.toggle_progress_dock_action.setVisible(is_learning_view)

    def _return_to_selection_screen(self):
        self._clear_dynamic_widgets()
        self.setWindowTitle(self.tr("LanguageLearningApp"))
        self.main_stack.setCurrentWidget(self.course_selection_view)
        self._update_dev_info_button_visibility()
        self._update_menu_state()

    def _clear_dynamic_widgets(self):
        if self.learning_widget:
            # Remove dynamic dock actions from the main menu
            if self.toggle_nav_dock_action:
                self.view_menu.removeAction(self.toggle_nav_dock_action)
                self.toggle_nav_dock_action = None
            if self.toggle_progress_dock_action:
                self.view_menu.removeAction(self.toggle_progress_dock_action)
                self.toggle_progress_dock_action = None

            # Clear animation objects to prevent dangling references
            self.central_stack_fade_animation = None
            self.central_stack_fade_effect = None

            self.main_stack.removeWidget(self.learning_widget)
            self.learning_widget.deleteLater()
            self.learning_widget = None
            self.learning_ui_views = {}
            # Clean up dock widget references to be safe
            self.navigation_dock_widget = None
            self.progress_dock_widget = None

        if self.editor_view:
            self.main_stack.removeWidget(self.editor_view)
            self.editor_view.deleteLater()
            self.editor_view = None

        self.course_manager = None
        self.progress_manager = None
        self._update_dev_info_button_visibility()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.stt_manager, self)
        dialog.theme_changed.connect(self.apply_theme)
        dialog.locale_changed.connect(self.apply_locale)
        dialog.font_size_changed.connect(self.apply_font_size)
        dialog.exec()

    def apply_locale(self, locale_code: str):
        app = QApplication.instance()
        if self.current_translator:
            app.removeTranslator(self.current_translator)
            self.current_translator = None
            logger.debug("Removed existing translator.")

        actual_locale_to_load = ""
        if locale_code == app_settings.DEFAULT_LOCALE:
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
        if not loaded_successfully:
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
                f"Successfully loaded translator for locale: {actual_locale_to_load}"
            )
        else:
            logger.warning(
                f"Failed to load translator for locale: {actual_locale_to_load}"
            )

        self._retranslate_main_window_ui()

    def _update_dev_info_button_visibility(self):
        if self.dev_info_button:
            is_dev_mode = utils.is_developer_mode_active()
            self.dev_info_button.setVisible(is_dev_mode)
            self.status_bar.setVisible(is_dev_mode)

    def _show_dev_info_dialog(self):
        current_exercise: Optional[Exercise] = None
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
        q_settings = QSettings()
        ui_setup_done = q_settings.value(
            app_settings.QSETTINGS_KEY_INITIAL_UI_SETUP_DONE, False, type=bool
        )
        audio_setup_done = q_settings.value(
            app_settings.QSETTINGS_KEY_INITIAL_AUDIO_SETUP_DONE, False, type=bool
        )

        # Show the unified dialog if either setup has not been completed.
        if not ui_setup_done or not audio_setup_done:
            logger.info("Initial setup not fully completed. Showing unified setup dialog.")
            dialog = UnifiedSetupDialog(self)
            dialog.theme_changed.connect(self.apply_theme)
            dialog.locale_changed.connect(self.apply_locale)
            dialog.font_size_changed.connect(self.apply_font_size)
            dialog.exec()


    def _check_and_show_onboarding(self):
        if not self.learning_widget or not self.learning_widget.isVisible():
            QTimer.singleShot(250, self._check_and_show_onboarding)
            return

        q_settings = QSettings()
        onboarding_seen = q_settings.value(
            app_settings.QSETTINGS_KEY_GLOBAL_ONBOARDING_SEEN, False, type=bool
        )
        if not onboarding_seen:
            logger.info("Displaying onboarding message.")
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
            QMessageBox.information(self.learning_widget, title, message)
            q_settings.setValue(app_settings.QSETTINGS_KEY_GLOBAL_ONBOARDING_SEEN, True)
            logger.info("Onboarding message shown and flag set.")

    # --- Learning Mode Methods ---
    def show_course_overview(self):
        if not self.learning_widget: 
            return
        
        # Reveal navigation dock
        if self.navigation_dock_widget:
            self.navigation_dock_widget.setVisible(True)
        
        # Existing refresh logic
        self.learning_ui_views["overview"].refresh_view()
        self.learning_ui_views["progress"].refresh_view()
        self.learning_ui_views["central_stack"].setCurrentWidget(
            self.learning_ui_views["placeholder"]
        )

    def start_lesson(self, lesson_id: str):
        if not self.learning_widget:
            return

        # Hide navigation dock when starting a lesson
        if self.navigation_dock_widget:
            self.navigation_dock_widget.setVisible(False)

        lesson_view = self.learning_ui_views["lesson"]
        lesson_view.start_lesson(lesson_id)
        self.learning_ui_views["central_stack"].setCurrentWidget(lesson_view)

    def start_review_session(self):
        if not self.learning_widget: return
        review_view = self.learning_ui_views["review"]
        review_view.start_review_session()
        if review_view.total_exercises_in_session > 0:
            self.learning_ui_views["central_stack"].setCurrentWidget(review_view)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen(): self.showNormal()
            else: self.showFullScreen()
        elif event.key() == Qt.Key.Key_Alt:
            self.menuBar().setVisible(not self.menuBar().isVisible())
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent):
        if self.progress_manager: self.progress_manager.save_progress()
        self.stt_manager.unload_model()
        if self.editor_view and self.editor_view.is_dirty:
            self.editor_view.close_editor()
            if self.editor_view.isVisible():
                event.ignore()
                return
        super().closeEvent(event)

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            logger.debug("MainWindow received LanguageChange event.")
            self._retranslate_main_window_ui()
        super().changeEvent(event)

    def _retranslate_main_window_ui(self):
        logger.debug("MainWindow UI elements re-translation starting.")
        # Window Title
        if self.course_manager and self.course_manager.course:
            self.setWindowTitle(f"LL - {self.course_manager.get_course_title()}")
        elif self.editor_view:
            pass  # Title is set when editor is loaded
        else:
            self.setWindowTitle(self.tr("LanguageLearningApp"))
        
        self._update_toolbar_icons()
        
        # --- Retranslate the persistent menu bar ---
        # Menu Titles
        self.menuBar().actions()[0].setText(self.tr("&File"))
        self.menuBar().actions()[1].setText(self.tr("&Learning"))
        self.menuBar().actions()[2].setText(self.tr("&View"))
        
        # Action Texts
        self.return_to_selection_action.setText(self.tr("Return to Course Selection"))
        self.open_for_editing_action.setText(self.tr("Open Course for Editing..."))
        self.settings_action.setText(self.tr("&Settings..."))
        self.quit_action.setText(self.tr("&Quit"))
        self.start_due_review_action.setText(self.tr("Start Due Review"))
        self.view_menu.actions()[0].setText(self.tr("Toggle Toolbar")) # Toolbar toggle

        # --- Retranslate dynamic parts ---
        if hasattr(MainWindow, "navigation_dock_widget"):
            if self.navigation_dock_widget:
                self.navigation_dock_widget.setWindowTitle(self.tr("Course Navigation"))
        if hasattr(MainWindow, "progress_dock_widget"):
            if self.progress_dock_widget:
                self.progress_dock_widget.setWindowTitle(self.tr("Progress"))

        if self.dev_info_button:
            self.dev_info_button.setText(self.tr("Dev Info"))

        # The changeEvent should propagate to child widgets, so they handle their own retranslation.
        logger.debug("MainWindow UI elements re-translation attempted.")