import json

from production import sim_racing_apps
from tools import sim_racing_apps_probe


class Response:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return self.text.encode("utf-8")


def test_choose_base_url_prefers_requested_working_url(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=0):
        calls.append(url)
        if url.startswith("http://192.168.1.11/SIMRacingApps/"):
            return Response(json.dumps({"State": "NORMAL", "Value": 28}))
        raise OSError("not running here")

    monkeypatch.setattr(sim_racing_apps_probe, "urlopen", fake_urlopen)
    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()

    assert (
        sim_racing_apps_probe.choose_base_url("http://192.168.1.11/SIMRacingApps/")
        == "http://192.168.1.11/SIMRacingApps/"
    )
    assert calls[0] == "http://192.168.1.11/SIMRacingApps/Data/Session/Cars"


def test_safe_filename_removes_path_characters():
    assert sim_racing_apps_probe.safe_filename("34 / T.J. Lee") == "34___T_J__Lee"
