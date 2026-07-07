from broadcast.broadcast_queue import BroadcastQueue
from broadcaster.race_brain import RaceBrain
from broadcaster.race_director import RaceDirector, RacePhase
from production.commentary_cleaner import CommentaryCleaner
from production.caution_pit_reporter import CautionPitReporter
from production.action_detector import ActionDetector
from production.editorial_producer import EditorialDecisionType, EditorialProducer
from production.field_rundown_director import FieldRundownDirector
from production.incident_detector import IncidentDetector
from production.league_context import LeagueContext
from production.openai_director import OpenAIDirector
from production.opening_director import OpeningDirector
from production.pit_strategy_detector import PitStrategyDetector
from production.race_insight_director import RaceInsightDirector
from production.race_intelligence import RaceIntelligence
from production.session_tracker import SessionTracker
from production.sponsor_reads import SponsorReadDirector


class BroadcastEngine:
    """Single orchestration path shared by live and replay telemetry sources."""

    INCIDENT_DETECTION_AFTER_LAP = 2

    def __init__(self, openai_director=None, incident_debug=False):
        self.openai_director = openai_director or OpenAIDirector()
        self.commentary_cleaner = CommentaryCleaner()
        self.league_context = LeagueContext()
        self.incident_debug = bool(incident_debug)
        self.reset()

    def reset(self):
        self.session_tracker = SessionTracker()
        self._reset_race_session()

    def _reset_race_session(self):
        self.race_brain = RaceBrain()
        self.race_director = RaceDirector()
        self.race_intelligence = RaceIntelligence()
        self.race_insight_director = RaceInsightDirector()
        self.action_detector = ActionDetector()
        self.editorial_producer = EditorialProducer()
        self.pit_strategy_detector = PitStrategyDetector()
        self.caution_pit_reporter = CautionPitReporter()
        self.incident_detector = IncidentDetector()
        self.incident_detector.debug = self.incident_debug
        self.field_rundown_director = FieldRundownDirector()
        self.opening_director = OpeningDirector()
        self.sponsor_read_director = SponsorReadDirector()
        self.broadcast_queue = BroadcastQueue()
        self.caution_marker_replay_count = 0
        self.caution_top_ten_reset_queued = False
        self.final_laps_battle_queued = False
        self.last_leader_story_lap = 0
        self.current_leader_car_idx = None
        self.current_leader_started_lap = 0
        self.last_leader_gap = None
        self.leader_laps_led = {}
        self.last_leader_lap_counted = None

    def tick(self, telemetry):
        session_type_reader = getattr(telemetry, "get_session_type", None)
        session_type = session_type_reader() if session_type_reader else "Race"
        transition = self.session_tracker.update(session_type)

        if transition.changed:
            print(f"iRacing session detected: {transition.current.value}")

        if not self.session_tracker.is_race():
            return None

        if transition.entered_race:
            self._reset_race_session()

        results = telemetry.get_results()
        driver_lookup = self.league_context.enrich_driver_lookup(
            telemetry.get_driver_lookup()
        )
        total_laps = telemetry.get_total_laps()
        current_lap = self.best_race_lap(telemetry.get_lap(), results)
        session_flags = telemetry.get_session_flags()
        pit_road_status = telemetry.get_car_idx_on_pit_road()
        track_surface_status = telemetry.get_car_idx_track_surface()
        story_results = self.active_race_results(
            results,
            pit_road_status=pit_road_status,
            track_surface_status=track_surface_status,
        )

        race_knowledge = self.race_intelligence.update(
            results=story_results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            total_laps=total_laps,
            session_flags=session_flags,
            pit_road_status=pit_road_status,
        )
        race_state = self.race_intelligence.get_race_state()

        grid_reader = getattr(telemetry, "get_starting_grid", None)
        starting_grid = grid_reader() if grid_reader else results
        self.race_brain.seed_starting_positions(
            starting_grid or results,
            driver_lookup,
        )
        self._queue_opening(
            telemetry,
            starting_grid or results,
            driver_lookup,
            current_lap,
        )

        self.race_director.update(
            telemetry=telemetry,
            results=results,
            driver_lookup=driver_lookup,
            scheduler=self.broadcast_queue,
        )

        if (
            self.race_director.race_started
            and self.race_director.phase != RacePhase.CHECKERED
        ):
            self._collect_pit_stories(
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
            )
            self._collect_incidents(
                telemetry,
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
                race_state.green_lap_count,
            )

        if self.race_director.phase == RacePhase.GREEN:
            self._update_leader_laps_led(
                story_results,
                current_lap,
            )
            mandatory_rundown_due = self.field_rundown_director.is_due_or_active(
                current_lap,
                total_laps,
                race_state.green_lap_count,
            )
            if mandatory_rundown_due:
                if self.has_pending_race_control():
                    return self.broadcast_queue.next_item()
                queued_field_rundown = self._queue_mandatory_field_rundown(
                    results,
                    driver_lookup,
                    current_lap,
                    total_laps,
                    race_state.green_lap_count,
                )
                if queued_field_rundown:
                    return self.broadcast_queue.next_item()
                return None

            queued_quarter_rundown = self._queue_mandatory_field_rundown(
                results,
                driver_lookup,
                current_lap,
                total_laps,
                race_state.green_lap_count,
            )
            if queued_quarter_rundown:
                return self.broadcast_queue.next_item()
            queued_final_battle = self._queue_final_laps_battle(
                story_results,
                driver_lookup,
                current_lap,
                total_laps,
            )
            if queued_final_battle:
                return self.broadcast_queue.next_item()
            queued_insight = self._queue_long_green_insight(
                race_state,
                current_lap,
            )
            if queued_insight:
                return self.broadcast_queue.next_item()
            self.editorial_producer.submit_race_knowledge(race_knowledge)
            self._queue_leader_story(
                story_results,
                driver_lookup,
                current_lap,
                total_laps,
            )
            self._collect_action_stories(
                telemetry,
                story_results,
                driver_lookup,
                pit_road_status,
                current_lap,
            )
            self._collect_pass_stories(story_results, driver_lookup)
            self._queue_editorial_decision(
                race_state,
                race_knowledge,
                driver_lookup,
            )
        else:
            self.field_rundown_director.cancel_active()

        return self.broadcast_queue.next_item()

    def _queue_opening(self, telemetry, results, driver_lookup, current_lap):
        if (
            self.opening_director.is_complete()
            or self.race_director.race_started
            or current_lap > 1
        ):
            return

        for segment in self.opening_director.update(
            telemetry=telemetry,
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
        ):
            self.broadcast_queue.add(
                segment.message,
                priority=segment.priority,
                category=segment.category,
                protected=True,
                speaker=segment.speaker,
                delay_seconds=getattr(segment, "delay_seconds", 0.0),
                expires_after=180,
                dedupe_key=segment.category,
                camera_sequence=segment.camera_sequence,
                camera_sequence_steps=getattr(segment, "camera_sequence_steps", ()),
                camera_return_home_after_sequence=getattr(
                    segment,
                    "camera_return_home_after_sequence",
                    False,
                ),
            )

        if self.opening_director.is_complete():
            self._queue_opening_sponsor_read()

    def _queue_opening_sponsor_read(self):
        message = self.sponsor_read_director.opening_read()
        if not message:
            return
        self.broadcast_queue.add(
            message,
            priority=9,
            category="sponsor_read",
            protected=True,
            speaker="lead",
            expires_after=180,
            dedupe_key="sponsor_read:opening",
        )

    def _collect_pass_stories(self, results, driver_lookup):
        for event in self.race_brain.analyze(results, driver_lookup):
            if event.importance < 8:
                continue

            if event.new_position == 1:
                story_type = "lead_change"
            elif event.new_position <= 5:
                story_type = "top_five_pass"
            else:
                story_type = "pass"

            self.editorial_producer.submit_story(
                story_type=story_type,
                headline=event.message,
                summary=event.message,
                priority=event.importance,
                source="race_brain",
                driver_name=event.driver_name,
                car_number=event.car_number,
                speaker="lead",
                camera_target_car_idx=event.car_idx,
                participant_car_indices=tuple(
                    car_idx for car_idx in (event.car_idx,) if car_idx is not None
                ),
            )

    def _queue_leader_story(self, results, driver_lookup, current_lap, total_laps):
        if current_lap < 3 or not results:
            return
        if self.last_leader_story_lap and current_lap - self.last_leader_story_lap < 5:
            return
        if self.broadcast_queue.items:
            return

        ordered = self.sorted_running_order(results)
        if not ordered:
            return

        leader = ordered[0]
        leader_idx = leader.get("CarIdx")
        if leader_idx is None:
            return

        if leader_idx != self.current_leader_car_idx:
            self.current_leader_car_idx = leader_idx
            self.current_leader_started_lap = current_lap
            self.last_leader_gap = None

        laps_led_total = max(1, self.leader_laps_led.get(leader_idx, 1))
        lap_word = "lap" if laps_led_total == 1 else "laps"
        second = ordered[1] if len(ordered) > 1 else None
        gap = self.safe_float(second.get("Time")) if second else 0.0
        gap_text = self.leader_gap_phrase(gap)
        trend = self.leader_gap_trend(gap)

        driver = driver_lookup.get(leader_idx, {})
        name = driver.get("name", f"Car {leader_idx}")
        number = driver.get("number", "?")
        message = (
            f"{name} in the number {number} has led {laps_led_total} "
            f"{lap_word} tonight. {gap_text}{trend}"
        )
        self.broadcast_queue.add(
            message,
            priority=8,
            category="race_story",
            protected=False,
            speaker="jeff",
            expires_after=35,
            dedupe_key=f"leader_story:{leader_idx}:{current_lap // 5}",
            camera_target_car_idx=leader_idx,
            participant_car_indices=(leader_idx,),
        )
        self.last_leader_story_lap = current_lap
        self.last_leader_gap = gap if gap > 0 else self.last_leader_gap

    def _update_leader_laps_led(self, results, current_lap):
        if current_lap <= 0 or self.last_leader_lap_counted == current_lap:
            return
        ordered = self.sorted_running_order(results)
        if not ordered:
            return
        leader_idx = ordered[0].get("CarIdx")
        if leader_idx is None:
            return
        self.leader_laps_led[leader_idx] = self.leader_laps_led.get(leader_idx, 0) + 1
        self.last_leader_lap_counted = current_lap

    def _queue_final_laps_battle(self, results, driver_lookup, current_lap, total_laps):
        if self.final_laps_battle_queued:
            return False
        if total_laps <= 0 or current_lap <= 0:
            return False
        laps_to_go = total_laps - current_lap
        if laps_to_go < 0 or laps_to_go > 3:
            return False
        if self.broadcast_queue.items:
            return False

        battle = self.closest_top_five_battle(results)
        if not battle:
            return False

        front, chasing, gap = battle
        front_idx = front.get("CarIdx")
        chasing_idx = chasing.get("CarIdx")
        front_driver = driver_lookup.get(front_idx, {})
        chasing_driver = driver_lookup.get(chasing_idx, {})
        front_name = front_driver.get("name", f"Car {front_idx}")
        chasing_name = chasing_driver.get("name", f"Car {chasing_idx}")
        front_number = front_driver.get("number", "?")
        chasing_number = chasing_driver.get("number", "?")
        position = self.safe_int(chasing.get("Position"), 0)
        if any(self.safe_int(car.get("Position"), 999) == 0 for car in results or []):
            position += 1
        message = (
            f"Inside the final three laps, the closest battle in the top five is "
            f"for {self.ordinal_position(position)}. {chasing_name} in the number "
            f"{chasing_number} is only {gap:.1f} seconds behind {front_name} "
            f"in the number {front_number}."
        )
        self.broadcast_queue.add(
            message,
            priority=11,
            category="final_laps_battle",
            protected=True,
            speaker="jeff",
            expires_after=12,
            dedupe_key=f"final_laps_battle:{current_lap}",
            camera_target_car_idx=chasing_idx,
            participant_car_indices=tuple(
                car_idx for car_idx in (front_idx, chasing_idx) if car_idx is not None
            ),
        )
        self.final_laps_battle_queued = True
        return True

    def closest_top_five_battle(self, results):
        ordered = self.sorted_running_order(results)[:5]
        if len(ordered) < 2:
            return None

        best = None
        for index in range(1, len(ordered)):
            front = ordered[index - 1]
            chasing = ordered[index]
            gap = self.gap_between_adjacent(front, chasing)
            if gap <= 0:
                continue
            if best is None or gap < best[2]:
                best = (front, chasing, gap)
        return best

    def gap_between_adjacent(self, front, chasing):
        chasing_gap = self.safe_float(chasing.get("Time", chasing.get("Gap", 0)))
        front_gap = self.safe_float(front.get("Time", front.get("Gap", 0)))
        if chasing_gap > 0:
            return max(0.0, chasing_gap - max(front_gap, 0.0))
        return 0.0

    def ordinal_position(self, position):
        suffix = "th"
        if position % 100 not in (11, 12, 13):
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")
        return f"{position}{suffix}"

    def sorted_running_order(self, results):
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in valid)
        return sorted(
            valid,
            key=lambda car: self.safe_int(car.get("Position"), 999)
            + (1 if zero_based else 0),
        )

    def leader_gap_phrase(self, gap):
        if gap <= 0:
            return "The gap behind the leader is still forming. "
        if gap < 0.5:
            return (
                "It is a tight battle at the front, with second place close "
                "enough to keep the pressure on. "
            )
        if gap < 1.0:
            return f"The advantage is slim at about {gap:.1f} seconds. "
        return f"The leader has built a little breathing room at {gap:.1f} seconds. "

    def leader_gap_trend(self, gap):
        if gap <= 0 or self.last_leader_gap is None:
            return ""
        delta = gap - self.last_leader_gap
        if delta >= 0.3:
            return "That gap is growing."
        if delta <= -0.3:
            return "The chasers are starting to reel that back in."
        return "The margin is holding fairly steady."

    def _collect_action_stories(
        self,
        telemetry,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
    ):
        events = self.action_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
            lap_dist_pct_status=telemetry.get_car_idx_lap_dist_pct(),
            pit_road_status=pit_road_status,
            current_lap=current_lap,
        )
        for event in events:
            primary = driver_lookup.get(event.primary_car_idx, {})
            self.editorial_producer.submit_story(
                story_type=event.event_type,
                headline=event.headline,
                summary=event.summary,
                priority=event.importance,
                source="action_detector",
                driver_name=primary.get("name", ""),
                car_number=primary.get("number", ""),
                speaker="lead",
                camera_target_car_idx=event.camera_target_car_idx,
                participant_car_indices=event.participant_car_indices,
            )

    def _collect_pit_stories(
        self,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
    ):
        under_caution = self.race_director.phase in (
            RacePhase.CAUTION,
            RacePhase.ONE_TO_GREEN,
        )
        events = self.pit_strategy_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
            pit_road_status=pit_road_status,
            current_lap=current_lap,
            under_caution=under_caution,
        )
        if under_caution:
            self.caution_pit_reporter.update(
                under_caution=True,
                results=results,
                driver_lookup=driver_lookup,
                pit_road_status=pit_road_status,
            )
            if self.race_director.phase == RacePhase.ONE_TO_GREEN:
                report = self.caution_pit_reporter.build_majority_report()
                if report:
                    self.broadcast_queue.add(
                        report.message,
                        priority=max(report.importance, 9),
                        category="caution_pit_summary",
                        protected=True,
                        speaker="sarah",
                        expires_after=45,
                        dedupe_key=f"caution_pit_wave:{current_lap}",
                        camera_target_car_idx=None,
                        participant_car_indices=report.car_indices,
                    )
                    self._queue_caution_sponsor_read(current_lap)
                small_report = self.caution_pit_reporter.build_small_group_report()
                if small_report:
                    self.broadcast_queue.add(
                        small_report.message,
                        priority=max(small_report.importance, 9),
                        category="caution_pit_summary",
                        protected=True,
                        speaker="sarah",
                        expires_after=45,
                        dedupe_key=f"caution_pit_small_group:{current_lap}",
                        camera_target_car_idx=None,
                        participant_car_indices=small_report.car_indices,
                    )
                    self._queue_caution_sponsor_read(current_lap)
                self._queue_caution_top_ten_reset(
                    results,
                    driver_lookup,
                    current_lap,
                )
                self._queue_caution_race_insight()
            else:
                self.caution_top_ten_reset_queued = False
            return

        self.caution_pit_reporter.update(
            under_caution=False,
            results=results,
            driver_lookup=driver_lookup,
            pit_road_status=pit_road_status,
        )
        for event in events:
            self.editorial_producer.submit_pit_event(event)

    def _queue_long_green_insight(self, race_state, current_lap):
        if self.broadcast_queue.items:
            return False
        insight = self.race_insight_director.long_green_insight(
            race_state,
            current_lap,
        )
        if not insight:
            return False
        self.broadcast_queue.add(
            insight.message,
            priority=insight.priority,
            category=insight.category,
            protected=False,
            speaker=insight.speaker,
            expires_after=45,
            dedupe_key=insight.category,
        )
        return True

    def _queue_caution_race_insight(self):
        insight = self.race_insight_director.caution_insight(
            self.race_intelligence.get_race_state()
        )
        if not insight:
            return False
        self.broadcast_queue.add(
            insight.message,
            priority=insight.priority,
            category=insight.category,
            protected=False,
            speaker=insight.speaker,
            expires_after=45,
            dedupe_key=insight.category,
        )
        return True

    def _queue_caution_sponsor_read(self, current_lap):
        message = self.sponsor_read_director.caution_read(current_lap)
        if not message:
            return
        self.broadcast_queue.add(
            message,
            priority=7,
            category="sponsor_read",
            protected=False,
            speaker="lead",
            expires_after=90,
            dedupe_key=f"sponsor_read:caution:{current_lap}",
        )

    def _queue_caution_top_ten_reset(self, results, driver_lookup, current_lap):
        if self.caution_top_ten_reset_queued:
            return
        message = self.build_caution_top_ten_reset(results, driver_lookup)
        if not message:
            return
        self.caution_top_ten_reset_queued = True
        self.broadcast_queue.add(
            message,
            priority=8,
            category="caution_top_ten_reset",
            protected=True,
            speaker="jeff",
            delay_seconds=5.0,
            expires_after=45,
            dedupe_key=f"caution_top_ten_reset:{current_lap}",
        )

    def build_caution_top_ten_reset(self, results, driver_lookup):
        ordered = self.sorted_running_order(results)[:10]
        if len(ordered) < 3:
            return ""

        entries = []
        zero_based = any(
            self.safe_int(car.get("Position"), 999) == 0
            for car in ordered
        )
        for car in ordered:
            car_idx = car.get("CarIdx")
            driver = driver_lookup.get(car_idx, {})
            position = self.safe_int(car.get("Position"), len(entries) + 1)
            if zero_based:
                position += 1
            name = driver.get("name", f"Car {car_idx}")
            number = driver.get("number", "?")
            entries.append(f"{self.position_word(position)}, the {number} of {name}")

        return (
            "Before this restart, here is the top ten: "
            f"{'; '.join(entries)}."
        )

    def position_word(self, position):
        words = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth",
            5: "fifth",
            6: "sixth",
            7: "seventh",
            8: "eighth",
            9: "ninth",
            10: "tenth",
        }
        return words.get(self.safe_int(position), self.ordinal_position(position))

    def _queue_mandatory_field_rundown(
        self,
        results,
        driver_lookup,
        current_lap,
        total_laps,
        green_lap_count=0,
    ):
        if not self.broadcast_queue.can_speak():
            return False

        queued = False
        for segment in self.field_rundown_director.update(
            results=self.enrich_results_with_starting_positions(results),
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            total_laps=total_laps,
            under_green=True,
            green_lap_count=green_lap_count,
        ):
            queued = True
            self.clear_pending_noncritical_stories()
            self.broadcast_queue.add(
                segment.message,
                priority=max(segment.priority, 12),
                category=segment.category,
                protected=True,
                speaker=segment.speaker,
                expires_after=300,
                dedupe_key=segment.category,
                camera_sequence=segment.camera_sequence,
                camera_sequence_steps=getattr(segment, "camera_sequence_steps", ()),
            )
        return queued

    def has_pending_race_control(self):
        return any(
            item.category == "race_control"
            for item in self.broadcast_queue.items
        )

    def clear_pending_noncritical_stories(self):
        preserved_categories = {
            "race_control",
            "incident",
            "caution_pit_summary",
            "sponsor_read",
        }
        self.broadcast_queue.items = [
            item
            for item in self.broadcast_queue.items
            if item.category in preserved_categories
        ]

    def enrich_results_with_starting_positions(self, results):
        enriched = []
        for car in results or []:
            car_copy = dict(car)
            car_idx = car_copy.get("CarIdx")
            if car_idx is not None:
                driver = self.race_brain.driver_manager.get_driver(car_idx)
                if driver.starting_position:
                    car_copy["StartingPosition"] = driver.starting_position
            enriched.append(car_copy)
        return enriched

    def _collect_incidents(
        self,
        telemetry,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
        green_lap_count=0,
    ):
        caution_just_started = (
            self.race_director.phase == RacePhase.CAUTION
            and self.race_director.phase_changed
            and self.race_director.previous_phase != RacePhase.CAUTION
        )
        if current_lap < self.INCIDENT_DETECTION_AFTER_LAP:
            if caution_just_started:
                self.queue_incident_marker_replay(
                    results,
                    telemetry,
                    current_lap,
                    green_lap_count,
                    reason=(
                        "caution started before scoring had enough laps "
                        "to build a replay candidate"
                    ),
                )
            return

        events = self.incident_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            track_surface_status=telemetry.get_car_idx_track_surface(),
            track_surface_material_status=telemetry.get_car_idx_track_surface_material(),
            lap_dist_pct_status=telemetry.get_car_idx_lap_dist_pct(),
            est_time_status=telemetry.get_car_idx_est_time(),
            pit_road_status=pit_road_status,
            suppress_soft_events=self.should_suppress_soft_incidents(),
        )
        if not events and caution_just_started:
            fallback = self.incident_detector.build_caution_fallback(current_lap)
            if fallback:
                events = [fallback]
        if not events:
            if caution_just_started:
                self.queue_incident_marker_replay(
                    results,
                    telemetry,
                    current_lap,
                    green_lap_count,
                    reason="caution started but no replay candidate was found",
                )
            return

        if self.race_director.phase not in (
            RacePhase.CAUTION,
            RacePhase.ONE_TO_GREEN,
        ):
            self.broadcast_queue.clear_for_race_control()
        session_num_reader = getattr(telemetry, "get_current_session_num", None)
        session_time_reader = getattr(telemetry, "get_session_time", None)
        session_num = session_num_reader() if session_num_reader else 0
        session_time = session_time_reader() if session_time_reader else 0.0
        for event in events:
            replay_eligible = (
                event.incident_delta >= 2
                or event.trouble_type == "caution candidate"
            )
            use_incident_marker_replay = (
                caution_just_started
                and event.trouble_type == "caution candidate"
                and event.incident_delta <= 0
            )
            replay_message = (
                "We are going to take a look at what brought out this caution."
                if use_incident_marker_replay
                else event.message
            )
            self.broadcast_queue.add(
                self.commentary_cleaner.clean(replay_message),
                priority=event.importance,
                category="incident",
                protected=True,
                speaker="lead",
                expires_after=25,
                dedupe_key=(
                    f"incident:{event.car_idx}:{event.trouble_type}:"
                    f"{event.lap}:{event.total_incidents}"
                ),
                camera_target_car_idx=(
                    None if use_incident_marker_replay else event.car_idx
                ),
                participant_car_indices=(
                    () if use_incident_marker_replay else (event.car_idx,)
                ),
                replay_session_num=session_num if replay_eligible else None,
                replay_session_time=(
                    None
                    if use_incident_marker_replay
                    else session_time if replay_eligible else None
                ),
                replay_incident_delta=event.incident_delta,
                replay_multi_angle=replay_eligible and caution_just_started,
                replay_use_incident_marker=use_incident_marker_replay,
                replay_marker_pre_roll_frames=(
                    self.restart_caution_marker_pre_roll_frames(green_lap_count)
                    if use_incident_marker_replay
                    else None
                ),
            )

    def queue_incident_marker_replay(
        self,
        results,
        telemetry,
        current_lap,
        green_lap_count,
        reason,
    ):
        self.report_incident_debug(reason, results, telemetry)
        session_num_reader = getattr(telemetry, "get_current_session_num", None)
        session_num = session_num_reader() if session_num_reader else 0
        self.caution_marker_replay_count += 1
        self.broadcast_queue.add(
            "We are going to take a look at what may have brought out this caution.",
            priority=10,
            category="incident",
            protected=True,
            speaker="lead",
            expires_after=25,
            dedupe_key=(
                f"incident:marker:caution:{current_lap}:{session_num}:"
                f"{self.caution_marker_replay_count}"
            ),
            replay_session_num=session_num,
            replay_incident_delta=0,
            replay_multi_angle=True,
            replay_use_incident_marker=True,
            replay_marker_pre_roll_frames=self.restart_caution_marker_pre_roll_frames(
                green_lap_count
            ),
        )

    def restart_caution_marker_pre_roll_frames(self, green_lap_count):
        try:
            green_lap_count = int(green_lap_count)
        except Exception:
            green_lap_count = 99
        if green_lap_count <= 2:
            return 40 * 60
        return None

    def should_suppress_soft_incidents(self):
        # Soft telemetry signals such as estimated-time loss, lap-distance loss,
        # surface changes, and position drops are still useful as background
        # caution-candidate evidence, but they are too noisy to air as live
        # incident commentary in official races. Only confirmed incident points
        # and caution-fallback stories should interrupt the broadcast.
        return True

    def report_incident_debug(self, reason, results, telemetry):
        if not self.incident_debug:
            return

        incident_cars = [
            car for car in results or []
            if self.safe_int(car.get("Incidents", 0)) > 0
        ]
        surfaces = telemetry.get_car_idx_track_surface()
        abnormal_surface_count = sum(
            1 for surface in surfaces or []
            if self.incident_detector.is_abnormal_surface(surface)
        )
        counters = "available" if incident_cars else "not changing or unavailable"
        print(
            "INCIDENT DEBUG: "
            f"{reason}; incident counters {counters}; "
            f"abnormal surface cars={abnormal_surface_count}; "
            f"recent candidates={len(self.incident_detector.recent_caution_candidates)}."
        )

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def best_race_lap(self, telemetry_lap, results):
        laps = [self.safe_int(telemetry_lap)]
        for car in results or []:
            laps.append(self.safe_int(car.get("Lap", car.get("LapsComplete", 0))))
            laps.append(self.safe_int(car.get("LapsComplete", car.get("Lap", 0))))
        return max(laps, default=0)

    def active_race_results(self, results, pit_road_status=None, track_surface_status=None):
        if not results:
            return []

        active = []
        for car in results or []:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue
            if self.is_on_pit_road(car_idx, pit_road_status):
                continue
            if not self.is_active_track_surface(car_idx, track_surface_status):
                continue
            active.append(car)
        return active

    def is_on_pit_road(self, car_idx, pit_road_status):
        try:
            return bool(pit_road_status[int(car_idx)])
        except Exception:
            return False

    def is_active_track_surface(self, car_idx, track_surface_status):
        if track_surface_status is None:
            return True
        try:
            surface = track_surface_status[int(car_idx)]
        except Exception:
            return True
        if surface is None:
            return True
        try:
            surface = int(surface)
        except Exception:
            return True

        # iRacing can keep cars in the results list even when they are not
        # actively racing. Values at/below 1 are commonly invalid/not-in-world
        # or off-racing-surface states and are too noisy for pass/battle stories.
        return surface > 1

    def _queue_editorial_decision(self, race_state, race_knowledge, driver_lookup):
        decision = self.editorial_producer.choose_next_item(race_state=race_state)
        if decision.decision_type != EditorialDecisionType.AIR_NOW or not decision.item:
            return

        item = decision.item
        fallback = self.commentary_cleaner.clean(item.summary)
        enriched_knowledge = dict(race_knowledge or {})
        league_driver_context = self.league_context.context_for_item(
            item,
            driver_lookup,
        )
        if league_driver_context:
            enriched_knowledge["league_driver_context"] = league_driver_context
        commentary = self.openai_director.generate_commentary(
            speaker=item.speaker,
            assignment=item,
            race_state=race_state,
            race_knowledge=enriched_knowledge,
            fallback_text=fallback,
        )
        self.broadcast_queue.add(
            self.commentary_cleaner.clean(commentary),
            priority=item.priority,
            category=item.category,
            protected=False,
            speaker=item.speaker,
            expires_after=45,
            dedupe_key=self.editorial_producer.build_story_id(item),
            camera_target_car_idx=item.camera_target_car_idx,
            participant_car_indices=item.participant_car_indices,
        )
