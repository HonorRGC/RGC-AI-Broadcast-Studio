import json

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
        if url.endswith("/ImageUrl"):
            return Response(
                '{"State":"NORMAL","Value":"iRacing/pk_car.png?carPath=stockcars2%5Ccamaro2019&carCustPaint=car_num_90223.tga"}'
            )
        return Response('{"State":"NORMAL","Value":""}')

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()

    url = build_sim_racing_apps_car_image_url(
        {"car_idx": 12},
        base_url="http://127.0.0.1/SIMRacingApps/",
        now=10.0,
    )

    assert calls[0][0] == "http://127.0.0.1/SIMRacingApps/Data/Car/I12/Number"
    assert calls[0][1] == sim_racing_apps.REQUEST_TIMEOUT_SECONDS
    assert any(call[0].endswith("/ImageUrl") for call in calls)
    assert url.startswith("http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?")


def test_build_car_image_url_returns_empty_when_sim_racing_apps_is_unavailable(monkeypatch):
    def fake_urlopen(url, timeout=0):
        raise OSError("server unavailable")

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()
    sim_racing_apps._LAST_GOOD_RENDER_INFO.clear()

    assert build_sim_racing_apps_car_image_url({"car_idx": 12}) == ""


def test_build_car_image_url_ignores_error_state(monkeypatch):
    def fake_urlopen(url, timeout=0):
        return Response('{"State":"ERROR","Value":"not available"}')

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()
    sim_racing_apps._LAST_GOOD_RENDER_INFO.clear()

    assert build_sim_racing_apps_car_image_url({"car_idx": 12}) == ""


def test_build_car_render_info_includes_number_style(monkeypatch):
    values = {
        "Number": "34",
        "DriverName": "T.J. Lee",
        "ImageUrl": "iRacing/pk_car.png?car=34",
        "ColorNumber": 16777215,
        "ColorNumberBackground": 0,
        "ColorNumberOutline": 7829367,
        "NumberFont": "Arial",
        "NumberSlant": "slant",
    }

    def fake_urlopen(url, timeout=0):
        field = url.rsplit("/", 1)[-1]
        state = "OFF" if field in {"ImageUrl", "ColorNumber", "ColorNumberBackground", "ColorNumberOutline", "NumberFont", "NumberSlant"} else "NORMAL"
        return Response(json.dumps({"State": state, "Value": values.get(field, "")}))

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()
    sim_racing_apps._LAST_GOOD_RENDER_INFO.clear()

    info = build_sim_racing_apps_car_render_info(
        {"car_idx": 34, "number": "34", "name": "T.J. Lee"},
        now=10.0,
    )

    assert info["image_url"] == "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=34"
    assert info["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
        "outline": "#777777",
        "font_family": "Arial",
        "font_style": "italic",
    }


def test_build_car_render_info_makes_generic_image_url_car_specific(monkeypatch):
    values = {
        "Number": "34",
        "DriverName": "T.J. Lee",
        "ImageUrl": "iRacing/pk_car.png",
    }

    def fake_urlopen(url, timeout=0):
        field = url.rsplit("/", 1)[-1]
        return Response(json.dumps({"State": "NORMAL", "Value": values.get(field, "")}))

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()

    info = build_sim_racing_apps_car_render_info(
        {"car_idx": 34, "number": "34", "name": "T.J. Lee"},
        now=10.0,
    )

    assert info["image_url"] == "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=I34"


def test_build_car_render_info_scans_roster_when_car_idx_does_not_match(monkeypatch):
    responses = {
        "Data/Session/Cars": {"State": "NORMAL", "Value": 3},
        "Data/Car/I5/Number": {"State": "NORMAL", "Value": "99"},
        "Data/Car/I5/DriverName": {"State": "NORMAL", "Value": "Wrong Driver"},
        "Data/Car/I0/Number": {"State": "NORMAL", "Value": "34"},
        "Data/Car/I0/DriverName": {"State": "NORMAL", "Value": "T.J. Lee"},
        "Data/Car/I0/ImageUrl": {"State": "OFF", "Value": "iRacing/pk_car.png?car=34"},
    }

    def fake_urlopen(url, timeout=0):
        key = url.split("/SIMRacingApps/")[-1]
        return Response(json.dumps(responses.get(key, {"State": "ERROR"})))

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()

    info = build_sim_racing_apps_car_render_info(
        {"car_idx": 5, "number": "34", "name": "T.J. Lee"},
        now=10.0,
    )

    assert info["image_url"] == "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=34"


def test_build_car_render_info_does_not_reuse_mismatched_direct_car(monkeypatch):
    responses = {
        "Data/Session/Cars": {"State": "NORMAL", "Value": 1},
        "Data/Car/I5/Number": {"State": "NORMAL", "Value": "99"},
        "Data/Car/I5/DriverName": {"State": "NORMAL", "Value": "Wrong Driver"},
        "Data/Car/I5/ImageUrl": {"State": "OFF", "Value": "iRacing/pk_car.png?car=99"},
        "Data/Car/I0/Number": {"State": "NORMAL", "Value": "99"},
        "Data/Car/I0/DriverName": {"State": "NORMAL", "Value": "Wrong Driver"},
        "Data/Car/I0/ImageUrl": {"State": "OFF", "Value": "iRacing/pk_car.png?car=99"},
    }

    def fake_urlopen(url, timeout=0):
        key = url.split("/SIMRacingApps/")[-1]
        return Response(json.dumps(responses.get(key, {"State": "ERROR"})))

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()

    info = build_sim_racing_apps_car_render_info(
        {"car_idx": 5, "number": "34", "name": "T.J. Lee"},
        now=10.0,
    )

    assert info == {}


def test_build_car_render_info_keeps_last_good_render_during_hiccup(monkeypatch):
    responses = {
        "Data/Car/I34/Number": {"State": "NORMAL", "Value": "34"},
        "Data/Car/I34/DriverName": {"State": "NORMAL", "Value": "T.J. Lee"},
        "Data/Car/I34/ImageUrl": {"State": "OFF", "Value": "iRacing/pk_car.png?car=34"},
        "Data/Car/I34/ColorNumber": {"State": "NORMAL", "Value": 16777215},
        "Data/Car/I34/ColorNumberBackground": {"State": "NORMAL", "Value": 0},
    }

    def fake_urlopen(url, timeout=0):
        key = url.split("/SIMRacingApps/")[-1]
        return Response(json.dumps(responses.get(key, {"State": "ERROR"})))

    monkeypatch.setattr(sim_racing_apps, "urlopen", fake_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()
    sim_racing_apps._LAST_GOOD_RENDER_INFO.clear()

    first = build_sim_racing_apps_car_render_info(
        {"car_idx": 34, "number": "34", "name": "T.J. Lee"},
        now=10.0,
    )

    def broken_urlopen(url, timeout=0):
        raise OSError("temporary hiccup")

    monkeypatch.setattr(sim_racing_apps, "urlopen", broken_urlopen)
    sim_racing_apps._CACHE.clear()
    sim_racing_apps._ROSTER_CACHE.clear()

    second = build_sim_racing_apps_car_render_info(
        {"car_idx": 34, "number": "34", "name": "T.J. Lee"},
        now=20.0,
    )

    assert first["image_url"] == second["image_url"]
    assert second["number_style"]["color"] == "#ffffff"
