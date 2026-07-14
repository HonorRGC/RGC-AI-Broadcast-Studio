from production.editorial_producer import EditorialItem
from production.league_context import LeagueContext


def write_drivers_csv(tmp_path):
    csv_path = tmp_path / "drivers.csv"
    csv_path.write_text(
        "\n".join(
            [
                "name,car_number,hometown,state,country,driving_style,sponsor,notes,car_image",
                (
                    "Austin Peterson,77,Nashville,TN,USA,aggressive on restarts,"
                    "RGC Motorsports,Usually strong when clean air matters,cars/austin.png"
                ),
            ]
        ),
        encoding="utf-8",
    )
    return csv_path


def write_stats_csv(tmp_path):
    csv_path = tmp_path / "stats.csv"
    csv_path.write_text(
        "\n".join(
            [
                (
                    "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,"
                    "avg_finish,last_finish,points_position,points_to_next,"
                    "track_starts,track_wins,best_track_finish,notes"
                ),
                (
                    "Austin Peterson,77,season,24,4,14,21,3,5.8,2,1,0,5,2,1,"
                    "Defending points leader"
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
    assert enriched[4]["car_image"] == "cars/austin.png"
    assert "aggressive on restarts" in enriched[4]["league_context_summary"]


def test_league_context_enriches_driver_lookup_with_stats(tmp_path):
    context = LeagueContext(
        write_drivers_csv(tmp_path),
        stats_csv_path=write_stats_csv(tmp_path),
        enabled=True,
    )

    enriched = context.enrich_driver_lookup(
        {
            4: {
                "name": "Austin Peterson",
                "number": "77",
            }
        }
    )

    assert enriched[4]["league_stats"]["wins"] == "4"
    assert "points: 1st" in enriched[4]["league_stats_summary"]
    assert "last race finish: 2nd" in enriched[4]["league_stats_summary"]
    assert "track wins: 2" in enriched[4]["league_stats_summary"]


def test_league_context_can_run_with_stats_only(tmp_path):
    missing_drivers = tmp_path / "missing_drivers.csv"
    context = LeagueContext(
        missing_drivers,
        stats_csv_path=write_stats_csv(tmp_path),
        enabled=True,
    )

    enriched = context.enrich_driver_lookup(
        {
            4: {
                "name": "Different Sim Name",
                "number": "#77",
            }
        }
    )

    assert context.is_configured()
    assert enriched[4]["league_stats"]["wins"] == "4"
    assert "points: 1st" in enriched[4]["league_stats_summary"]


def test_league_context_labels_career_stats_when_imported_all_seasons(tmp_path):
    csv_path = tmp_path / "career_stats.csv"
    csv_path.write_text(
        "\n".join(
            [
                "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,avg_finish,last_finish,points_position,points_to_next,track_starts,track_wins,best_track_finish,notes",
                "Austin Peterson,77,career,182,4,14,21,3,8.1,12,,,,,,Career import",
            ]
        ),
        encoding="utf-8",
    )
    context = LeagueContext(tmp_path / "missing.csv", stats_csv_path=csv_path, enabled=True)

    enriched = context.enrich_driver_lookup({4: {"name": "Austin Peterson", "number": "77"}})

    assert "career wins: 4" in enriched[4]["league_stats_summary"]
    assert "season wins" not in enriched[4]["league_stats_summary"]


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
    context = LeagueContext(
        write_drivers_csv(tmp_path),
        stats_csv_path=write_stats_csv(tmp_path),
        enabled=True,
    )
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

    assert len(notes) == 2
    assert "Nashville, TN, USA" in notes[0]
    assert "RGC Motorsports" in notes[0]
    assert any("season wins: 4" in note for note in notes)
    assert any("points: 1st" in note for note in notes)


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
