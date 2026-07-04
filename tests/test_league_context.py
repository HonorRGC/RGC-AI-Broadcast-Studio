from production.editorial_producer import EditorialItem
from production.league_context import LeagueContext


def write_drivers_csv(tmp_path):
    csv_path = tmp_path / "drivers.csv"
    csv_path.write_text(
        "\n".join(
            [
                "name,car_number,hometown,state,country,driving_style,sponsor,notes",
                (
                    "Austin Peterson,77,Nashville,TN,USA,aggressive on restarts,"
                    "RGC Motorsports,Usually strong when clean air matters"
                ),
            ]
        ),
        encoding="utf-8",
    )
    return csv_path


def test_league_context_enriches_driver_lookup_by_name(tmp_path):
    context = LeagueContext(write_drivers_csv(tmp_path), enabled=True)

    enriched = context.enrich_driver_lookup(
        {
            4: {
                "name": "Austin Peterson",
                "number": "77",
            }
        }
    )

    assert enriched[4]["hometown"] == "Nashville"
    assert enriched[4]["sponsor"] == "RGC Motorsports"
    assert "aggressive on restarts" in enriched[4]["league_context_summary"]


def test_league_context_can_match_by_car_number(tmp_path):
    context = LeagueContext(write_drivers_csv(tmp_path), enabled=True)

    enriched = context.enrich_driver_lookup(
        {
            4: {
                "name": "Different Sim Name",
                "number": "#77",
            }
        }
    )

    assert enriched[4]["league_profile"]["name"] == "Austin Peterson"


def test_league_context_builds_assignment_notes(tmp_path):
    context = LeagueContext(write_drivers_csv(tmp_path), enabled=True)
    driver_lookup = context.enrich_driver_lookup(
        {
            4: {
                "name": "Austin Peterson",
                "number": "77",
            }
        }
    )
    item = EditorialItem(
        story_type="pass",
        headline="Austin Peterson makes a move",
        summary="Austin Peterson is charging forward.",
        driver_name="Austin Peterson",
        car_number="77",
        participant_car_indices=(4,),
    )

    notes = context.context_for_item(item, driver_lookup)

    assert len(notes) == 1
    assert "Nashville, TN, USA" in notes[0]
    assert "RGC Motorsports" in notes[0]


def test_league_context_stays_off_when_disabled(tmp_path):
    context = LeagueContext(write_drivers_csv(tmp_path), enabled=False)

    driver_lookup = {
        4: {
            "name": "Austin Peterson",
            "number": "77",
        }
    }

    assert not context.is_configured()
    assert context.enrich_driver_lookup(driver_lookup) == driver_lookup
    assert context.context_for_item(
        EditorialItem(
            story_type="pass",
            headline="Austin Peterson makes a move",
            summary="Austin Peterson is charging forward.",
            participant_car_indices=(4,),
        ),
        driver_lookup,
    ) == []
