import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from replay.replay_telemetry import ReplayTelemetry
from production.race_intelligence import RaceIntelligence


REPLAY_STEP_DELAY = 0.05
PRINT_EVERY_SNAPSHOTS = 25


def format_driver_summary(summary):
    return (
        f"#{summary.car_number} {summary.driver_name} | "
        f"Start {summary.starting_position} → Now {summary.current_position} | "
        f"+{summary.positions_gained} / -{summary.positions_lost} | "
        f"Tags: {', '.join(summary.tags) if summary.tags else 'none'}"
    )


def format_momentum(profile):
    return (
        f"#{profile.car_number} {profile.driver_name} | "
        f"Position {profile.current_position} | "
        f"Momentum {profile.momentum_score:.1f} | "
        f"Trend {profile.trend} | "
        f"Status {profile.status} | "
        f"Recent Change {profile.recent_position_change}"
    )


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("python tools/race_intelligence_inspector.py recordings/your_recording_file.jsonl")
        return

    recording_file = sys.argv[1]

    telemetry = ReplayTelemetry(recording_file)
    intelligence = RaceIntelligence()

    if not telemetry.startup():
        print("Could not load replay.")
        return

    print("=" * 70)
    print("RGC AI Broadcast Studio - Race Intelligence Inspector")
    print("=" * 70)
    print(f"Recording : {recording_file}")
    print(f"Snapshots : {telemetry.snapshot_count()}")
    print("=" * 70)

    snapshot_number = 0

    while telemetry.is_connected():
        snapshot_number += 1

        results = telemetry.get_results()
        driver_lookup = telemetry.get_driver_lookup()
        current_lap = telemetry.get_lap()
        total_laps = telemetry.get_total_laps()
        session_flags = telemetry.get_session_flags()
        pit_road_status = telemetry.get_car_idx_on_pit_road()

        intelligence.update(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            total_laps=total_laps,
            session_flags=session_flags,
            pit_road_status=pit_road_status,
        )

        if snapshot_number % PRINT_EVERY_SNAPSHOTS == 0:
            race_state = intelligence.get_race_state()

            print()
            print("-" * 70)
            print(f"Snapshot {snapshot_number}/{telemetry.snapshot_count()} | Lap {current_lap}/{total_laps}")
            print("-" * 70)

            print("RACE STATE")
            print(
                f"Moment: {race_state.moment.value} | "
                f"Remaining: {race_state.laps_remaining} | "
                f"Cautions: {race_state.caution_count} | "
                f"Restarts: {race_state.restart_count} | "
                f"Green Run: {race_state.green_lap_count} | "
                f"Overtime: {race_state.is_overtime}"
            )

            print()
            top_story = intelligence.top_story()

            if top_story:
                print("TOP STORY")
                print(f"{top_story.headline}")
                print(f"{top_story.summary}")
                print(
                    f"Type: {top_story.story_type} | "
                    f"Importance: {top_story.importance} | "
                    f"Lifecycle: {top_story.lifecycle.value} | "
                    f"Speaker: {top_story.speaker_preference}"
                )
            else:
                print("TOP STORY")
                print("None yet.")

            print()
            best_battle = intelligence.get_best_battle()

            if best_battle:
                print("BEST BATTLE")
                print(best_battle.headline)
                print(best_battle.summary)
                print(
                    f"Type: {best_battle.story_type} | "
                    f"Importance: {best_battle.importance} | "
                    f"Gap: {best_battle.gap:.2f}"
                )
            else:
                print("BEST BATTLE")
                print("None.")

            print()
            print("HOTTEST DRIVERS")
            for profile in intelligence.get_hottest_drivers(limit=5):
                print(format_momentum(profile))

            print()
            print("BIGGEST MOVERS")
            for summary in intelligence.get_biggest_movers(limit=5):
                print(format_driver_summary(summary))

            print()
            print("FADING DRIVERS")
            for summary in intelligence.get_fading_drivers(limit=5):
                print(format_driver_summary(summary))

            print()
            print("ACTIVE STORIES")
            active_stories = intelligence.get_active_stories()

            if not active_stories:
                print("None")
            else:
                for story in active_stories[:5]:
                    print(
                        f"- {story.headline} "
                        f"[{story.lifecycle.value}, seen {story.times_seen}, discussed {story.times_discussed}]"
                    )

        telemetry.next_snapshot()
        time.sleep(REPLAY_STEP_DELAY)

    print()
    print("=" * 70)
    print("Race intelligence inspection complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()