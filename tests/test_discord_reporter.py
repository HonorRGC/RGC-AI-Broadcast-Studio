import json
from types import SimpleNamespace

from production.discord_reporter import DiscordRaceReporter


class FakeResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_discord_race_report_builds_payload_with_top_ten_and_movers():
    reporter = DiscordRaceReporter(
        enabled=True,
        webhook_url="https://discord.example/webhook",
        event_title="Autism Awareness 100",
        series_name="WFO Trucks",
        use_openai=False,
    )
    results = [
        {"CarIdx": 1, "Position": 0, "StartingPosition": 5, "LapsLed": 10},
        {"CarIdx": 2, "Position": 1, "StartingPosition": 1},
        {"CarIdx": 3, "Position": 2, "StartingPosition": 10},
    ]
    drivers = {
        1: {"name": "Winner Driver", "number": "34"},
        2: {"name": "Pole Driver", "number": "2"},
        3: {"name": "Mover Driver", "number": "88"},
    }

    payload = reporter.build_payload(
        results,
        drivers,
        track_info={"track_name": "Homestead Miami Speedway"},
        total_laps=100,
        race_state=SimpleNamespace(green_lap_count=88, caution_laps=12, caution_count=3),
    )

    embed = payload["embeds"][0]
    assert "WFO Trucks - Autism Awareness 100" in embed["title"]
    assert "Winner Driver takes the win" in embed["description"]
    assert "1st - #34 Winner Driver" in embed["fields"][0]["value"]
    assert "#88 Mover Driver: +8 spots" in embed["fields"][1]["value"]
    assert "Scheduled distance: 100 laps" in embed["fields"][2]["value"]
    assert "Green-flag laps" not in embed["fields"][2]["value"]
    assert "Caution laps tracked: 12" in embed["fields"][2]["value"]


def test_discord_race_report_uses_true_green_laps_only():
    reporter = DiscordRaceReporter(enabled=True, webhook_url="https://discord.example/webhook")
    results = [{"CarIdx": 1, "Position": 0}]
    drivers = {1: {"name": "Winner Driver", "number": "34"}}

    payload = reporter.build_payload(
        results,
        drivers,
        total_laps=36,
        race_state=SimpleNamespace(green_lap_count=1, caution_count=4),
    )

    stats = payload["embeds"][0]["fields"][-1]["value"]
    assert "Green-flag laps" not in stats
    assert "Cautions tracked: 4" in stats

    payload = reporter.build_payload(
        results,
        drivers,
        total_laps=36,
        race_state=SimpleNamespace(green_laps=28, green_lap_count=1, caution_count=4),
    )

    stats = payload["embeds"][0]["fields"][-1]["value"]
    assert "Green-flag laps: 28" in stats


def test_discord_race_report_posts_only_once():
    requests = []

    def opener(request, timeout=0):
        requests.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    reporter = DiscordRaceReporter(
        enabled=True,
        webhook_url="https://discord.example/webhook",
        use_openai=False,
        opener=opener,
    )

    first = reporter.post_once(
        results=[{"CarIdx": 1, "Position": 0}],
        driver_lookup={1: {"name": "Winner Driver", "number": "34"}},
    )
    second = reporter.post_once(
        results=[{"CarIdx": 1, "Position": 0}],
        driver_lookup={1: {"name": "Winner Driver", "number": "34"}},
    )

    assert first == (True, "Discord race report posted.")
    assert second == (False, "Discord race report already posted.")
    assert len(requests) == 1
