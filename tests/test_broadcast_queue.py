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
