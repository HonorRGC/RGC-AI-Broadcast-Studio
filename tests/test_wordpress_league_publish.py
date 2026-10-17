import json

from tools.wordpress_league_publish import build_payload
from production.wordpress_publisher import WordPressPublishSettings, load_wordpress_settings, save_wordpress_settings
from production.league_manager import LeagueProfile, RaceResult, RaceResultEntry, ScheduleEvent, save_league_profile, save_race_results, save_schedule


def test_wordpress_payload_contains_profile_schedule_and_laps_led(tmp_path):
    save_league_profile(tmp_path / "league.json", LeagueProfile(name="Test League", short_name="TL", season_name="Season 1"))
    save_schedule(tmp_path / "schedule.json", [ScheduleEvent(round_number=1, event_name="Opener", track_name="Daytona", laps=100)])
    save_race_results(tmp_path / "results.json", [RaceResult(1, "Opener", "Daytona", [RaceResultEntry(1, "Winner", "7", laps_led=25, points=40)])])

    payload = build_payload(tmp_path, "test-league", "season-1")

    assert payload["league"]["slug"] == "test-league"
    assert payload["schedule"][0]["track_name"] == "Daytona"
    assert payload["results"][0]["entries"][0]["laps_led"] == 25


def test_wordpress_settings_are_profile_specific(tmp_path):
    path = tmp_path / "league-name" / "wordpress.json"
    save_wordpress_settings(path, WordPressPublishSettings(username="rgc-publisher", auto_publish=True))

    loaded = load_wordpress_settings(path)

    assert loaded.username == "rgc-publisher"
    assert loaded.auto_publish is True
    assert loaded.endpoint.endswith("/wp-json/rgc-league-manager/v1/sync")


def test_wordpress_login_is_shared_but_profile_slugs_stay_separate(tmp_path):
    taco = tmp_path / "Taco" / "wordpress.json"
    whiskey = tmp_path / "Whiskey" / "wordpress.json"
    save_wordpress_settings(
        taco,
        WordPressPublishSettings(
            username="Honor",
            application_password="correct-password",
            league_slug="taco-tuesday",
        ),
    )
    whiskey.parent.mkdir(parents=True)
    whiskey.write_text(
        json.dumps({"username": "Honor", "application_password": "mistyped", "league_slug": "whiskey-wednesday"}),
        encoding="utf-8",
    )

    loaded = load_wordpress_settings(whiskey)

    assert loaded.application_password == "correct-password"
    assert loaded.league_slug == "whiskey-wednesday"
