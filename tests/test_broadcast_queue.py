import time

from broadcast.broadcast_queue import BroadcastQueue


def test_protected_high_priority_item_preempts_opening_chatter():
    queue = BroadcastQueue()
    queue.add("Starting lineup", priority=10, category="opening_lineup")
    queue.add(
        "Green flag!",
        priority=12,
        category="race_control",
        protected=True,
    )

    assert queue.next_item(now=time.time()).message == "Green flag!"


def test_queue_deduplicates_pending_items():
    queue = BroadcastQueue()
    queue.add("Same story", dedupe_key="story:1")
    queue.add("Same story with new wording", dedupe_key="story:1")

    assert len(queue.items) == 1


def test_expired_commentary_never_airs():
    queue = BroadcastQueue()
    queue.add("Old news", expires_after=5)
    queue.items[0].created_at = 10

    assert queue.next_item(now=20) is None


def test_race_control_clear_resets_busy_timer_for_immediate_interrupt():
    queue = BroadcastQueue()
    queue.busy_until = 999
    queue.add("Normal story", category="race_story")

    queue.clear_for_race_control()
    queue.add(
        "Trouble on the speedway.",
        category="race_control",
        protected=True,
        priority=12,
    )

    item = queue.next_item(now=time.time())

    assert item.message == "Trouble on the speedway."


def test_race_control_clear_can_preserve_current_voice_line():
    queue = BroadcastQueue()
    now = time.time()
    queue.busy_until = now + 30
    queue.add("Normal story", category="race_story")

    queue.clear_for_race_control(reset_busy=False)
    queue.add(
        "White flag. One lap to go.",
        category="race_control",
        protected=True,
        priority=13,
    )

    assert queue.next_item(now=now) is None
    assert queue.busy_until == now + 30


def test_one_driver_lineup_items_have_a_shorter_air_gap():
    queue = BroadcastQueue()
    queue.add(
        "Starting twelfth, the 12 of Example Driver.",
        category="opening_field_rundown_12",
    )

    queue.next_item(now=100.0)

    assert queue.busy_until < 105.0


def test_silent_feature_reserves_its_runtime_without_commentary():
    queue = BroadcastQueue()
    queue.add(
        "",
        category="crank_it_up",
        silent=True,
        feature_duration_seconds=50.0,
        dedupe_key="crank_it_up:test",
    )
    now = 100.0
    queue.items[0].created_at = now

    item = queue.next_item(now=now)

    assert item.silent is True
    assert item.message == ""
    assert queue.busy_until == now + 52.5


def test_spoken_feature_reserves_its_runtime():
    queue = BroadcastQueue()
    queue.add(
        "Top ten rundown for one driver.",
        category="long_green_field_rundown_1",
        feature_duration_seconds=20.0,
        dedupe_key="long_green_field_rundown_1",
    )
    now = 100.0
    queue.items[0].created_at = now

    item = queue.next_item(now=now)

    assert item.silent is False
    assert queue.busy_until == now + 21.0


def test_booth_follow_up_gets_tight_handoff_after_race_story():
    queue = BroadcastQueue()
    queue.add(
        "The leader has a strong run off the corner and opens the gap slightly.",
        priority=9,
        category="race_story",
        dedupe_key="story:lead",
    )
    queue.add(
        "Yeah, that clean exit matters here.",
        priority=8,
        category="race_story_follow_up",
        speaker="jeff",
        dedupe_key="follow:lead",
    )
    now = time.time()

    item = queue.next_item(now=now)

    assert item.dedupe_key == "story:lead"
    assert queue.busy_until < now + 5.0


def test_short_lap_calls_do_not_reserve_long_broadcast_window():
    queue = BroadcastQueue()
    queue.add(
        "White flag. One lap to go.",
        priority=13,
        category="race_control",
        protected=True,
        dedupe_key="race_control:white_flag",
    )
    now = time.time()

    item = queue.next_item(now=now)

    assert item.dedupe_key == "race_control:white_flag"
    assert queue.busy_until < now + 4.0
