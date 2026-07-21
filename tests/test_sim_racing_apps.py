from production import sim_racing_apps
from production.sim_racing_apps import (
    build_sim_racing_apps_car_image_url,
    build_sim_racing_apps_car_render_info,
)


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
            '{"State":"NORMAL","Value":{"ImageUrl":{"State":"NORMAL","Value":"iRacing/pk_car.png?carPath=stockcars2%5Ccamaro2019&carCustPaint=car_num_90223.tga"}}}'
        )

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()

    url = build_sim_racing_apps_car_image_url(
        {"car_idx": 12},
        base_url="http://127.0.0.1/SIMRacingApps/",
        now=10.0,
    )

    assert calls[0][0] == "http://127.0.0.1/SIMRacingApps/Data/Car/I12"
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


def test_build_car_render_info_includes_number_style(monkeypatch):
    def fake_urlopen(url, timeout=0):
        return Response(
            """
            {
              "State":"NORMAL",
              "Value":{
                "ImageUrl":{"State":"NORMAL","Value":"iRacing/pk_car.png?car=34"},
                "ColorNumber":{"State":"NORMAL","Value":16777215},
                "ColorNumberBackground":{"State":"NORMAL","Value":0},
                "ColorNumberOutline":{"State":"NORMAL","Value":7829367},
                "NumberFont":{"State":"NORMAL","Value":"Arial"},
                "NumberSlant":{"State":"NORMAL","Value":"slant"}
              }
            }
            """
        )

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()

    info = build_sim_racing_apps_car_render_info({"car_idx": 34}, now=10.0)

    assert info["image_url"] == "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=34"
    assert info["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
        "outline": "#777777",
        "font_family": "Arial",
        "font_style": "italic",
    }
