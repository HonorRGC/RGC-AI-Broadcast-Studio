from production import sim_racing_apps
from production.sim_racing_apps import build_sim_racing_apps_car_image_url


class Response:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return self.text.encode("utf-8")


def test_build_car_image_url_uses_live_car_idx_endpoint(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=0):
        calls.append((url, timeout))
        return Response(
            '{"State":"NORMAL","Value":"iRacing/pk_car.png?carPath=stockcars2%5Ccamaro2019&carCustPaint=car_num_90223.tga"}'
        )

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()

    url = build_sim_racing_apps_car_image_url(
        {"car_idx": 12},
        base_url="http://127.0.0.1/SIMRacingApps/",
        now=10.0,
    )

    assert calls[0][0] == "http://127.0.0.1/SIMRacingApps/Data/Car/I12/ImageUrl"
    assert calls[0][1] == sim_racing_apps.REQUEST_TIMEOUT_SECONDS
    assert url.startswith("http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?")


def test_build_car_image_url_returns_empty_when_sim_racing_apps_is_unavailable(monkeypatch):
    def fake_urlopen(url, timeout=0):
        raise OSError("server unavailable")

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()

    assert build_sim_racing_apps_car_image_url({"car_idx": 12}) == ""


def test_build_car_image_url_ignores_error_state(monkeypatch):
    def fake_urlopen(url, timeout=0):
        return Response('{"State":"ERROR","Value":"not available"}')

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()

    assert build_sim_racing_apps_car_image_url({"car_idx": 12}) == ""
