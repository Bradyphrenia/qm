from qm_app import windows_instance
import sys


def test_non_windows_instance_guard_is_a_noop(monkeypatch):
    monkeypatch.setattr(windows_instance.sys, "platform", "linux")
    guard = windows_instance.acquire_application_instance()
    assert guard is not None
    guard.close()
    guard.close()


def test_windows_mutex_rejects_second_instance():
    if sys.platform != "win32":
        return
    first = windows_instance.acquire_application_instance()
    assert first is not None
    try:
        assert windows_instance.acquire_application_instance() is None
    finally:
        first.close()
    replacement = windows_instance.acquire_application_instance()
    assert replacement is not None
    replacement.close()
