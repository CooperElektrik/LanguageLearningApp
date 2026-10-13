"""Unit tests for application splash screen handling."""

from PySide6.QtCore import QElapsedTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMainWindow, QSplashScreen

from application.main import finish_splash_screen


def test_finish_splash_screen_none(q_app):
    """Calling finish_splash_screen with None does nothing and does not raise."""
    window = QMainWindow()
    finish_splash_screen(None, None, window)


def test_finish_splash_screen_immediate(q_app):
    """When elapsed time exceeds minimum display time, splash finishes immediately."""
    pixmap = QPixmap(10, 10)
    splash = QSplashScreen(pixmap)
    splash.show()
    assert splash.isVisible()

    window = QMainWindow()
    window.show()

    timer = QElapsedTimer()
    timer.start()

    # Pass minimum_display_time_ms=0 so elapsed is >= minimum
    finish_splash_screen(splash, timer, window, minimum_display_time_ms=0)
    assert not splash.isVisible()


def test_finish_splash_screen_without_timer(q_app):
    """When splash_timer is None, splash finishes immediately."""
    pixmap = QPixmap(10, 10)
    splash = QSplashScreen(pixmap)
    splash.show()
    assert splash.isVisible()

    window = QMainWindow()
    window.show()

    finish_splash_screen(splash, None, window)
    assert not splash.isVisible()


def test_finish_splash_screen_delayed(q_app):
    """When elapsed time is less than minimum, splash finish is scheduled."""
    pixmap = QPixmap(10, 10)
    splash = QSplashScreen(pixmap)
    splash.show()
    assert splash.isVisible()

    window = QMainWindow()
    window.show()

    timer = QElapsedTimer()
    timer.start()

    finish_splash_screen(splash, timer, window, minimum_display_time_ms=50)
    # Immediately after call, splash should still be visible because timer hasn't fired
    assert splash.isVisible()

    # Process events after waiting for the timer to expire
    import time
    time.sleep(0.06)
    q_app.processEvents()

    assert not splash.isVisible()


def test_finish_splash_screen_handles_exception(q_app, monkeypatch):
    """finish_splash_screen safely handles any unexpected exceptions during splash.finish."""
    pixmap = QPixmap(10, 10)
    splash = QSplashScreen(pixmap)
    window = QMainWindow()

    def buggy_finish(widget):
        raise RuntimeError("C++ object already deleted")

    monkeypatch.setattr(splash, "finish", buggy_finish)
    # Should not raise
    finish_splash_screen(splash, None, window)
