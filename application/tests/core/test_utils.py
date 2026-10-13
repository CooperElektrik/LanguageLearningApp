"""Unit tests for application/utils.py functionality."""

import os

from application import utils

try:
    from application import settings
except ImportError:
    import settings


def test_get_available_locales():
    """Verify locales dictionary includes System and discovers available QM files."""
    locales = utils.get_available_locales()
    assert settings.DEFAULT_LOCALE in locales
    assert locales[settings.DEFAULT_LOCALE] == settings.DEFAULT_LOCALE
    # At least some translations should be detected from localization/
    assert len(locales) > 1


def test_is_developer_mode_active_env_var(monkeypatch):
    """Verify developer mode honours environment variables with cache invalidation."""
    utils.invalidate_developer_mode_cache()
    monkeypatch.setenv(settings.ENV_VAR_DEVELOPER_MODE, "1")
    assert utils.is_developer_mode_active() is True

    # Invalidate and check negative env var
    utils.invalidate_developer_mode_cache()
    monkeypatch.setenv(settings.ENV_VAR_DEVELOPER_MODE, "0")
    assert utils.is_developer_mode_active() is False

    # Clean up cache
    utils.invalidate_developer_mode_cache()


def test_get_resource_path():
    """Verify get_resource_path locates project assets and handles relative paths."""
    res_path = utils.get_resource_path("settings.py")
    assert os.path.exists(res_path)
