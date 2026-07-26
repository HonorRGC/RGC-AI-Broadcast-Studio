import json
from types import SimpleNamespace

from production.discord_reporter import DiscordRaceReporter


class FakeResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_discord_race_report_builds_payload_with_top_ten_and_movers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    schedule = tmp_path / "race_schedule.csv"
    schedule.write_text(
        "track_name,schedule_id,notes\n"
        "Homestead Miami Speedway,356761,Race 1\n",
        encoding="utf-8",
    )
    reporter = DiscordRaceReporter(
        enabled=True,
        webhook_url="https://discord.example/webhook",
        event_title="Autism Awareness 100",
        series_name="WFO Trucks",
        use_openai=False,
        sim_racer_hub_source="https://www.simracerhub.com",
        sim_racer_hub_season_id="29247",
        race_schedule_csv=str(schedule),
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
    assert "Race results" in embed["fields"][3]["value"]
    assert "schedule_id=356761" in embed["fields"][3]["value"]
    assert "Championship standings" in embed["fields"][3]["value"]


def test_discord_race_report_auto_uses_sim_racer_hub_schedule_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    schedule = tmp_path / "league" / "race_schedule.csv"
    schedule.parent.mkdir()
    schedule.write_text(
        "track_name,schedule_id,notes\n"
        "Michigan International Speedway,356761,WFO race 1\n",
        encoding="utf-8",
    )
    reporter = DiscordRaceReporter(
        enabled=True,
        webhook_url="https://discord.example/webhook",
        use_openai=False,
        sim_racer_hub_source="https://simracerhub.com",
        race_schedule_csv="league/race_schedule.csv",
    )

    payload = reporter.build_payload(
        [{"CarIdx": 1, "Position": 0}],
        {1: {"name": "Winner Driver", "number": "34"}},
        track_info={"track_name": "Michigan International Speedway"},
    )

    links = payload["embeds"][0]["fields"][-1]["value"]
    assert "Race results" in links
    assert "schedule_id=356761" in links


def test_discord_race_report_auto_builds_championship_link(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    schedule = tmp_path / "league" / "race_schedule.csv"
    schedule.parent.mkdir()
    schedule.write_text(
        "track_name,schedule_id,notes\n"
        "Daytona International Speedway,356762,Jul 29 2026\n",
        encoding="utf-8",
    )
    reporter = DiscordRaceReporter(
        enabled=True,
        webhook_url="https://discord.example/webhook",
        use_openai=False,
        sim_racer_hub_source="https://www.simracerhub.com",
        sim_racer_hub_season_id="29247",
        race_schedule_csv="league/race_schedule.csv",
    )

    payload = reporter.build_payload(
        [{"CarIdx": 1, "Position": 0}],
        {1: {"name": "Winner Driver", "number": "34"}},
        track_info={"track_name": "Daytona International Speedway"},
    )

    links = payload["embeds"][0]["fields"][-1]["value"]
    assert "Race results" in links
    assert "scoring/season_race.php?schedule_id=356762" in links
    assert "Championship standings" in links
    assert "season_standings.php?season_id=29247&schedule_id=356762" in links


def test_discord_race_report_uses_standings_source_for_auto_championship(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    schedule = tmp_path / "race_schedule.csv"
    schedule.write_text(
        "track_name,schedule_id,notes\n"
        "Daytona,356762,Jul 29 2026\n",
        encoding="utf-8",
    )
    reporter = DiscordRaceReporter(
        enabled=True,
        webhook_url="https://discord.example/webhook",
        use_openai=False,
        sim_racer_hub_source="https://www.simracerhub.com/season_standings.php?season_id=29079&schedule_id=364601",
        race_schedule_csv=str(schedule),
    )

    payload = reporter.build_payload(
        [{"CarIdx": 1, "Position": 0}],
        {1: {"name": "Winner Driver", "number": "34"}},
        track_info={"track_name": "Daytona International Speedway"},
    )

    links = payload["embeds"][0]["fields"][-1]["value"]
    assert "https://www.simracerhub.com/scoring/season_race.php?schedule_id=356762" in links
    assert "https://www.simracerhub.com/season_standings.php?season_id=29079&schedule_id=356762" in links

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
