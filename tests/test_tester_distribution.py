from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_tester_launch_files_exist():
    assert (ROOT / "setup_windows.bat").exists()
    assert (ROOT / "launch_studio.bat").exists()
    assert (ROOT / "create_desktop_shortcut.ps1").exists()


def test_tester_quickstart_documents_desktop_shortcut():
    guide = (ROOT / "docs" / "TESTER_QUICKSTART.md").read_text(encoding="utf-8")

    assert "Download ZIP" in guide
    assert "setup_windows.bat" in guide
    assert "create_desktop_shortcut.ps1" in guide
    assert "http://127.0.0.1:8765/overlay" in guide
