import time

from broadcast.broadcast_queue import BroadcastQueue
from broadcaster.race_brain import RaceBrain
from broadcaster.race_director import RaceDirector, RacePhase
from config import STAGE_END_LAPS
from production.commentary_cleaner import CommentaryCleaner
from production.caution_pit_reporter import CautionPitReporter
from production.action_detector import ActionDetector
from production.broadcast_story_producer import BroadcastStoryProducer
from production.booth_followup_director import BoothFollowupDirector
from production.booth_conversation_director import BoothConversationDirector
from production.editorial_producer import EditorialDecisionType, EditorialProducer
from production.field_rundown_director import FieldRundownDirector
from production.fastest_lap_tracker import FastestLapTracker
from production.formation_detector import FormationDetector
from production.incident_detector import IncidentDetector
from production.league_context import LeagueContext
from production.openai_director import OpenAIDirector
from production.opening_director import OpeningDirector
from production.penalty_detector import PenaltyDetector
from production.pit_strategy_detector import PitStrategyDetector
from production.racecraft_director import RacecraftDirector
from production.race_insight_director import RaceInsightDirector
from production.race_intelligence import RaceIntelligence
from production.session_tracker import SessionTracker
from production.sponsor_reads import SponsorReadDirector
from production.storyline_director import StorylineDirector


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
        self.racecraft_director = RacecraftDirector()
        self.storyline_director = StorylineDirector()
        self.action_detector = ActionDetector()
        self.formation_detector = FormationDetector()
        self.editorial_producer = EditorialProducer()
        self.broadcast_story_producer = BroadcastStoryProducer()
        self.booth_followup_director = BoothFollowupDirector()
        self.booth_conversation_director = BoothConversationDirector()
        self.penalty_detector = PenaltyDetector()
        self.pit_strategy_detector = PitStrategyDetector()
        self.caution_pit_reporter = CautionPitReporter()
        self.incident_detector = IncidentDetector()
        self.incident_detector.debug = self.incident_debug
        self.field_rundown_director = FieldRundownDirector()
        self.fastest_lap_tracker = FastestLapTracker()
        self.opening_director = OpeningDirector()
        self.sponsor_read_director = SponsorReadDirector()
        self.broadcast_queue = BroadcastQueue()
        self.caution_marker_replay_count = 0
        self.caution_top_ten_reset_queued = False
        self.caution_top_ten_order_signature = ()
        self.caution_top_ten_stable_ticks = 0
        self.final_laps_battle_queued = False
        self.caution_lucky_dog_queued = False
        self.late_caution_note_queued = False
        self.green_pit_cycle_announced = False
        self.green_pit_cycle_last_update_lap = 0
        self.green_pit_cycle_update_count = 0
        self.crank_it_up_sent_this_green_run = False
        self.booth_conversation_active_until = 0.0
        self.last_leader_story_lap = 0
        self.current_leader_car_idx = None
        self.current_leader_started_lap = 0
        self.last_leader_gap = None
        self.leader_laps_led = {}
        self.last_leader_lap_counted = None
        self.race_ticks_seen = 0
        self.joined_mid_race = False
        self.mid_race_join_note_queued = False
        self.restart_launch_story_queued = False
        self.caution_started_session_num = None
        self.caution_started_session_time = None
        self.stage_end_laps = tuple(sorted(set(int(lap) for lap in STAGE_END_LAPS if int(lap) > 0)))
        self.stages_announced = set()

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
        self._detect_mid_race_start(
            current_lap=current_lap,
            total_laps=total_laps,
            session_flags=session_flags,
            results=results,
            telemetry=telemetry,
        )
        self.race_ticks_seen += 1
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
        if not self.joined_mid_race:
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
        self._handle_green_phase_change()
        self._handle_caution_phase_change(
            telemetry,
            current_lap=current_lap,
            results=results,
            driver_lookup=driver_lookup,
        )
        self._queue_mid_race_join_note(current_lap, total_laps, telemetry.get_track_info())

        if self.race_director.phase == RacePhase.CAUTION:
            self._queue_late_caution_note(current_lap, total_laps)

        if (
            self.race_director.race_started
            and self.race_director.phase != RacePhase.CHECKERED
        ):
            self._collect_pit_stories(
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
                session_time=getattr(telemetry, "get_session_time", lambda: 0.0)(),
                lap_dist_pct=getattr(telemetry, "get_car_idx_lap_dist_pct", lambda: [])(),
                track_info=telemetry.get_track_info(),
            )
            self._collect_incidents(
                telemetry,
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
                race_state.green_lap_count,
                total_laps=total_laps,
            )
            self._collect_penalty_stories(
                telemetry,
                results,
                driver_lookup,
                current_lap,
            )

        if self.race_director.phase == RacePhase.GREEN:
            self.caution_lucky_dog_queued = False
            self.late_caution_note_queued = False
            self._update_leader_laps_led(
                story_results,
                current_lap,
            )
            closing_feature_blocked = self.closing_lap_feature_blocked(
                current_lap,
                total_laps,
            )
            if closing_feature_blocked:
                self.field_rundown_director.cancel_active()
                self.clear_closing_lap_features()

            mandatory_rundown_due = self.field_rundown_director.is_due_or_active(
                current_lap,
                total_laps,
                race_state.green_lap_count,
            ) if not closing_feature_blocked else False
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

            queued_quarter_rundown = False
            if not closing_feature_blocked:
                queued_quarter_rundown = self._queue_mandatory_field_rundown(
                    results,
                    driver_lookup,
                    current_lap,
                    total_laps,
                    race_state.green_lap_count,
                )
            if queued_quarter_rundown:
                return self.broadcast_queue.next_item()
            queued_stage_end = self._queue_stage_end_if_due(
                results,
                driver_lookup,
                current_lap,
                caution=False,
            )
            if queued_stage_end:
                return self.broadcast_queue.next_item()
            queued_final_battle = self._queue_final_laps_battle(
                story_results,
                driver_lookup,
                current_lap,
                total_laps,
            )
            if queued_final_battle:
                return self.broadcast_queue.next_item()
            queued_restart_launch = self._queue_restart_launch_story(
                story_results,
                driver_lookup,
                race_state.green_lap_count,
            )
            if queued_restart_launch and not self.has_pending_race_control():
                return self.broadcast_queue.next_item()
            queued_crank_it_up = self._queue_crank_it_up(
                story_results,
                race_state.green_lap_count,
                race_state.laps_remaining,
            )
            if queued_crank_it_up:
                return self.broadcast_queue.next_item()
            queued_insight = self._queue_long_green_insight(
                race_state,
                current_lap,
            )
            if queued_insight:
                return self.broadcast_queue.next_item()
            queued_booth_conversation = self._queue_booth_conversation(
                story_results,
                driver_lookup,
                telemetry.get_track_info(),
                race_state,
                current_lap,
                total_laps,
            )
            if queued_booth_conversation:
                return self.broadcast_queue.next_item()
            if self.booth_conversation_is_active():
                return self.broadcast_queue.next_item()
            self.editorial_producer.submit_race_knowledge(race_knowledge)
            self._queue_fastest_lap_story(
                story_results,
                driver_lookup,
                current_lap,
            )
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
            self._collect_formation_stories(
                telemetry,
                story_results,
                driver_lookup,
                pit_road_status,
                current_lap,
            )
            self._collect_racecraft_stories(
                telemetry,
                story_results,
                driver_lookup,
                current_lap,
                total_laps,
                race_state,
            )
            self._collect_storyline_stories(
                current_lap,
                race_state,
            )
            self._collect_pass_stories(story_results, driver_lookup)
            self._queue_editorial_decision(
                race_state,
                race_knowledge,
                driver_lookup,
            )
            queued_stat_filler = self._queue_race_stat_filler(
                story_results,
                driver_lookup,
                race_state,
                current_lap,
            )
            if queued_stat_filler:
                return self.broadcast_queue.next_item()
        else:
            self.field_rundown_director.cancel_active()
            if self.race_director.phase in (RacePhase.CAUTION, RacePhase.ONE_TO_GREEN):
                self.crank_it_up_sent_this_green_run = False
                self.restart_launch_story_queued = False

        return self.broadcast_queue.next_item()

    def _handle_green_phase_change(self):
        if not (
            self.race_director.phase_changed
            and self.race_director.phase == RacePhase.GREEN
        ):
            return

        # Any pass/battle items collected before the restart can sound stale
        # as soon as the field takes the green. Keep only the live race-control
        # call and let fresh telemetry build the next story.
        self.editorial_producer.clear()
        self.restart_launch_story_queued = False

    def _handle_caution_phase_change(
        self,
        telemetry,
        current_lap=0,
        results=None,
        driver_lookup=None,
    ):
        if not (
            self.race_director.phase_changed
            and self.race_director.phase == RacePhase.CAUTION
        ):
            return

        session_num_reader = getattr(telemetry, "get_current_session_num", None)
        session_time_reader = getattr(telemetry, "get_session_time", None)
        self.caution_started_session_num = (
            session_num_reader() if session_num_reader else None
        )
        self.caution_started_session_time = (
            session_time_reader() if session_time_reader else None
        )
        self._queue_stage_end_if_due(
            results or [],
            driver_lookup or {},
            current_lap,
            caution=True,
        )

    def _detect_mid_race_start(
        self,
        current_lap,
        total_laps,
        session_flags,
        results,
        telemetry,
    ):
        if self.race_ticks_seen > 0 or self.joined_mid_race:
            return
        if self.race_director.race_started or self.race_director.phase != RacePhase.UNKNOWN:
            return
        if current_lap <= 1:
            return

        state_reader = getattr(telemetry, "get_session_state", None)
        session_state = state_reader() if state_reader else 0
        phase = self.race_director.detect_phase(
            session_flags,
            results,
            current_lap,
            total_laps,
            session_state=session_state,
        )
        if phase == RacePhase.CHECKERED:
            return

        self.joined_mid_race = True
        self.race_brain.disable_starting_position_context()

        if phase == RacePhase.GREEN:
            self.race_director.phase = RacePhase.GREEN
            self.race_director.previous_phase = RacePhase.GREEN
            self.race_director.race_started = True

    def _queue_mid_race_join_note(self, current_lap, total_laps, track_info):
        if not self.joined_mid_race or self.mid_race_join_note_queued:
            return

        track_name = (track_info or {}).get("track_name") or "the speedway"
        if total_laps > 0:
            lap_text = f"lap {current_lap} of {total_laps}"
        else:
            lap_text = f"lap {current_lap}"

        self.broadcast_queue.add(
            (
                f"We join this race already in progress at {track_name}, "
                f"currently on {lap_text}. We'll settle in with the leaders, "
                "watch the battles developing, and bring you the key stories "
                "from here."
            ),
            priority=11,
            category="mid_race_join",
            protected=True,
            speaker="lead",
            expires_after=45,
            dedupe_key="race_control:mid_race_join",
        )
        self.mid_race_join_note_queued = True

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
            priority=8,
            category="sponsor_read",
            protected=True,
            speaker="lead",
            delay_seconds=10.0,
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

    def _queue_restart_launch_story(self, results, driver_lookup, green_lap_count):
        if self.restart_launch_story_queued:
            return False
        if green_lap_count > 4:
            return False
        if not results:
            return False
        if self.has_pending_non_restart_story():
            return False

        ordered = self.sorted_running_order(results)
        if len(ordered) < 2:
            return False

        leader = ordered[0]
        second = ordered[1]
        leader_idx = leader.get("CarIdx")
        second_idx = second.get("CarIdx")
        if leader_idx is None:
            return False

        gap = self.safe_float(second.get("Time", second.get("Gap", 0)))
        driver = driver_lookup.get(leader_idx, {})
        name = driver.get("name", f"Car {leader_idx}")
        number = driver.get("number", "?")

        if gap <= 0.15:
            second_driver = driver_lookup.get(second_idx, {})
            second_name = second_driver.get("name", "second place")
            second_number = second_driver.get("number", "?")
            message = (
                f"That is a tight launch at the front. {name} in the number {number} "
                f"has the lead for now, but the {second_number} of {second_name} "
                "is still right there with them."
            )
        elif gap < 0.60:
            message = (
                f"Good start for the {number} of {name}. They have pulled out "
                "a couple of car lengths as the field gets back up to speed."
            )
        else:
            message = (
                f"Clean restart for the {number} of {name}. They have already built "
                f"about {gap:.1f} seconds over second place."
            )

        self.broadcast_queue.add(
            message,
            priority=9,
            category="restart_launch",
            protected=False,
            speaker="lead",
            delay_seconds=2.5,
            expires_after=18,
            dedupe_key=f"restart_launch:{leader_idx}:{self.race_director.previous_phase.value}",
            camera_target_car_idx=leader_idx,
            participant_car_indices=tuple(
                idx for idx in (leader_idx, second_idx) if idx is not None
            ),
        )
        self.restart_launch_story_queued = True
        return True

    def _queue_fastest_lap_story(self, results, driver_lookup, current_lap):
        event = self.fastest_lap_tracker.analyze(
            results,
            driver_lookup,
            current_lap,
        )
        if not event:
            return False
        self.broadcast_queue.add(
            event.message,
            priority=7,
            category="fastest_lap",
            protected=False,
            speaker="lead",
            expires_after=40,
            dedupe_key=f"fastest_lap:{event.car_idx}:{event.lap_time:.3f}",
            camera_target_car_idx=event.car_idx,
            participant_car_indices=(event.car_idx,),
        )
        return True

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

    def _collect_formation_stories(
        self,
        telemetry,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
    ):
        events = self.formation_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
            lap_dist_pct_status=telemetry.get_car_idx_lap_dist_pct(),
            pit_road_status=pit_road_status,
            current_lap=current_lap,
        )
        for event in events:
            primary = driver_lookup.get(event.primary_car_idx, {})
            self.editorial_producer.submit_story(
                story_type=event.story_type,
                headline=event.headline,
                summary=event.summary,
                priority=event.importance,
                source="formation_detector",
                driver_name=primary.get("name", ""),
                car_number=primary.get("number", ""),
                speaker="jeff",
                camera_target_car_idx=event.primary_car_idx,
                participant_car_indices=event.participant_car_indices,
            )

    def _collect_racecraft_stories(
        self,
        telemetry,
        results,
        driver_lookup,
        current_lap,
        total_laps,
        race_state,
    ):
        events = self.racecraft_director.analyze(
            results=results,
            driver_lookup=driver_lookup,
            track_info=telemetry.get_track_info(),
            race_state=race_state,
            current_lap=current_lap,
            total_laps=total_laps,
            lap_dist_pct_status=telemetry.get_car_idx_lap_dist_pct(),
            pit_states=self.pit_strategy_detector.driver_states,
        )
        for event in events:
            self.editorial_producer.submit_story(
                story_type=event.story_type,
                headline=event.headline,
                summary=event.summary,
                priority=event.priority,
                source="racecraft_director",
                driver_name=event.driver_name,
                car_number=event.car_number,
                speaker=event.speaker,
                camera_target_car_idx=event.camera_target_car_idx,
                participant_car_indices=event.participant_car_indices,
            )

    def _collect_storyline_stories(self, current_lap, race_state):
        events = self.storyline_director.analyze(
            self.race_intelligence.driver_memory,
            race_state=race_state,
            current_lap=current_lap,
        )
        for event in events:
            self.editorial_producer.submit_story(
                story_type=event.story_type,
                headline=event.headline,
                summary=event.summary,
                priority=event.priority,
                source="storyline_director",
                driver_name=event.driver_name,
                car_number=event.car_number,
                speaker=event.speaker,
                camera_target_car_idx=event.camera_target_car_idx,
                participant_car_indices=event.participant_car_indices,
            )

    def _collect_pit_stories(
        self,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
        session_time=0.0,
        lap_dist_pct=None,
        track_info=None,
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
            session_time=session_time,
            lap_dist_pct=lap_dist_pct,
        )
        if under_caution:
            self.caution_pit_reporter.update(
                under_caution=True,
                results=results,
                driver_lookup=driver_lookup,
                pit_road_status=pit_road_status,
            )
            if self.race_director.phase == RacePhase.ONE_TO_GREEN:
                report = self.caution_pit_reporter.build_majority_report(
                    self.pit_strategy_detector.driver_states
                )
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
                small_report = self.caution_pit_reporter.build_small_group_report(
                    self.pit_strategy_detector.driver_states
                )
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
                    pit_road_status,
                    track_info,
                )
                self._queue_caution_race_insight()
            else:
                self.caution_top_ten_reset_queued = False
                self.caution_top_ten_order_signature = ()
                self.caution_top_ten_stable_ticks = 0
            return

        self.caution_pit_reporter.update(
            under_caution=False,
            results=results,
            driver_lookup=driver_lookup,
            pit_road_status=pit_road_status,
        )
        for event in events:
            self.editorial_producer.submit_pit_event(event)
        self._queue_green_pit_cycle_update(
            events,
            results,
            driver_lookup,
            pit_road_status,
            current_lap,
        )

    def _queue_green_pit_cycle_update(
        self,
        events,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
    ):
        if current_lap <= 1 or not results:
            return False
        if self.race_director.phase != RacePhase.GREEN:
            return False
        race_state = self.race_intelligence.get_race_state()
        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 999), 999)
        if 0 < laps_remaining <= 5:
            return False
        if (
            self.green_pit_cycle_update_count >= 3
            or current_lap - self.green_pit_cycle_last_update_lap < 4
        ):
            return False

        on_pit_road = [
            car for car in results or []
            if self.is_on_pit_road(car.get("CarIdx"), pit_road_status)
        ]
        recent_states = [
            state
            for state in self.pit_strategy_detector.driver_states.values()
            if getattr(state, "last_pit_lap", 0) > 0
            and current_lap - int(getattr(state, "last_pit_lap", 0) or 0) <= 5
        ]
        new_green_entries = [
            event for event in events or []
            if getattr(event, "event_type", "") == "PIT_STOP"
            and not getattr(event, "under_caution", False)
        ]

        if not self.green_pit_cycle_announced:
            if len(on_pit_road) < 2 and len(new_green_entries) < 2:
                return False
            message = (
                "Green flag pit stops are starting. Sarah will be watching who "
                "short-pits, who stays out, and how the tire age starts to split "
                "the field."
            )
        else:
            if len(recent_states) < 2:
                return False
            pitted_count = len({
                getattr(state, "car_idx", None)
                for state in recent_states
                if getattr(state, "car_idx", None) is not None
            })
            message = (
                f"Green flag pit cycle update: {pitted_count} cars have made stops "
                "in the last few laps. The drivers who came early will have older "
                "tires as this cycle keeps working through."
            )

        self.broadcast_queue.add(
            message,
            priority=8,
            category="green_pit_cycle_update",
            protected=False,
            speaker="sarah",
            expires_after=40,
            dedupe_key=f"green_pit_cycle_update:{current_lap}",
        )
        self.green_pit_cycle_announced = True
        self.green_pit_cycle_last_update_lap = current_lap
        self.green_pit_cycle_update_count += 1
        return True

    def _collect_penalty_stories(self, telemetry, results, driver_lookup, current_lap):
        events = self.penalty_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            car_idx_session_flags=getattr(
                telemetry,
                "get_car_idx_session_flags",
                lambda: [],
            )(),
            penalty_reasons=getattr(
                telemetry,
                "get_car_idx_penalty_reasons",
                lambda: [],
            )(),
        )
        defer_penalties = self.should_defer_penalty_stories()
        penalty_delay_seconds = 35.0 if defer_penalties else 0.0
        for event in events:
            self.broadcast_queue.add(
                event.message,
                priority=event.priority,
                category="penalty",
                protected=(event.event_type == "meatball" and not defer_penalties),
                speaker="lead" if event.event_type == "meatball" else "sarah",
                delay_seconds=penalty_delay_seconds,
                expires_after=45,
                dedupe_key=f"penalty:{event.event_type}:{event.car_idx}",
                camera_target_car_idx=event.car_idx,
                participant_car_indices=(event.car_idx,),
            )

    def should_defer_penalty_stories(self):
        if self.race_director.phase in (RacePhase.CAUTION, RacePhase.ONE_TO_GREEN):
            return True
        return any(item.category == "incident" for item in self.broadcast_queue.items)

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

    def _queue_booth_conversation(
        self,
        results,
        driver_lookup,
        track_info,
        race_state,
        current_lap,
        total_laps,
    ):
        if self.broadcast_queue.items or not self.broadcast_queue.can_speak():
            return False
        if self.booth_conversation_is_active():
            return False

        lines = self.booth_conversation_director.build(
            results=results,
            driver_lookup=driver_lookup,
            track_info=track_info,
            race_state=race_state,
            current_lap=current_lap,
            total_laps=total_laps,
        )
        if not lines:
            return False

        self.clear_pending_for_booth_conversation()
        total_feature_seconds = 0.0
        for index, line in enumerate(lines):
            message = self.commentary_cleaner.clean(line.message)
            total_feature_seconds += self.broadcast_queue.estimate_speech_seconds(
                message,
                "booth_conversation",
            )
            self.broadcast_queue.add(
                message,
                priority=9,
                category="booth_conversation",
                protected=False,
                speaker=line.speaker,
                delay_seconds=line.delay_seconds,
                expires_after=50,
                dedupe_key=f"booth_conversation:{current_lap}:{index}",
                camera_target_car_idx=line.camera_target_car_idx,
                participant_car_indices=line.participant_car_indices,
                camera_return_home_after_sequence=(index == len(lines) - 1),
            )
        self.booth_conversation_active_until = (
            time.time() + total_feature_seconds + 8.0
        )
        return True

    def booth_conversation_is_active(self):
        if self.broadcast_queue.has_pending_booth_conversation():
            return True
        return time.time() < self.booth_conversation_active_until

    def clear_pending_for_booth_conversation(self):
        preserved_categories = {
            "race_control",
            "incident",
            "stage_end",
            "penalty",
        }
        self.broadcast_queue.items = [
            item
            for item in self.broadcast_queue.items
            if item.category in preserved_categories
        ]

    def _queue_race_stat_filler(self, results, driver_lookup, race_state, current_lap):
        if self.broadcast_queue.items or not self.broadcast_queue.can_speak():
            return False
        insight = self.race_insight_director.race_stat_filler(
            results,
            driver_lookup,
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
            expires_after=35,
            dedupe_key=insight.category,
            camera_target_car_idx=insight.camera_target_car_idx,
            participant_car_indices=insight.participant_car_indices,
        )
        return True

    def closing_lap_feature_blocked(self, current_lap, total_laps):
        total_laps = self.safe_int(total_laps)
        current_lap = self.safe_int(current_lap)
        if total_laps <= 0 or current_lap <= 0:
            return False
        return max(total_laps - current_lap, 0) < 10

    def clear_closing_lap_features(self):
        blocked_prefixes = (
            "quarter_field_rundown",
            "three_quarter_field_rundown",
            "long_green_field_rundown",
        )
        blocked_categories = {
            "crank_it_up_intro",
            "crank_it_up",
        }
        self.broadcast_queue.items = [
            item for item in self.broadcast_queue.items
            if item.category not in blocked_categories
            and not str(item.category).startswith(blocked_prefixes)
        ]

    def _queue_crank_it_up(self, results, green_lap_count, laps_remaining=None):
        if self.crank_it_up_sent_this_green_run:
            return False
        if green_lap_count < 10:
            return False
        laps_remaining = self.safe_int(laps_remaining) if laps_remaining is not None else 0
        if 0 < laps_remaining < 10:
            return False
        if self.broadcast_queue.items or not self.broadcast_queue.can_speak():
            return False

        steps = self.build_crank_it_up_camera_steps(results)
        if not steps:
            return False

        self.crank_it_up_sent_this_green_run = True
        self.broadcast_queue.add(
            "It is time to Crank It Up. Crank It Up is presented by RGC Motorsports.",
            priority=10,
            category="crank_it_up_intro",
            protected=True,
            speaker="lead",
            expires_after=30,
            dedupe_key=f"crank_it_up:intro:{green_lap_count}",
        )
        self.broadcast_queue.add(
            "Crank It Up",
            priority=9,
            category="crank_it_up",
            protected=True,
            speaker="lead",
            expires_after=90,
            dedupe_key=f"crank_it_up:{green_lap_count}",
            camera_sequence_steps=steps,
            camera_return_home_after_sequence=True,
            silent=True,
            feature_duration_seconds=50.0,
        )
        return True

    def build_crank_it_up_camera_steps(self, results):
        ordered = self.sorted_running_order(results)
        if not ordered:
            return ()
        steps = []
        for car in ordered[:4]:
            car_idx = car.get("CarIdx")
            if car_idx is not None:
                steps.append((car_idx, "Crank Fixed", 0))
        return tuple(steps)

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

    def _queue_caution_top_ten_reset(
        self,
        results,
        driver_lookup,
        current_lap,
        pit_road_status=None,
        track_info=None,
    ):
        if self.caution_top_ten_reset_queued:
            return
        if self.is_short_track(track_info):
            self.caution_top_ten_order_signature = ()
            self.caution_top_ten_stable_ticks = 0
            return
        if self.top_ten_has_pit_road_cars(results, pit_road_status):
            self.caution_top_ten_order_signature = ()
            self.caution_top_ten_stable_ticks = 0
            return
        if not self.caution_top_ten_order_is_stable(results):
            return
        message = self.build_caution_top_ten_reset(results, driver_lookup)
        if not message:
            return
        ordered = self.sorted_running_order(results)[:10]
        top_ten_car_indices = tuple(
            car.get("CarIdx") for car in ordered if car.get("CarIdx") is not None
        )
        self.caution_top_ten_reset_queued = True
        self.broadcast_queue.add(
            message,
            priority=8,
            category="caution_top_ten_reset",
            protected=True,
            speaker="jeff",
            delay_seconds=1.5,
            expires_after=30,
            dedupe_key=f"caution_top_ten_reset:{current_lap}",
            participant_car_indices=top_ten_car_indices,
        )

    def caution_top_ten_order_is_stable(self, results, required_ticks=6):
        ordered = self.sorted_running_order(results)[:10]
        signature = tuple(car.get("CarIdx") for car in ordered)
        if len(signature) < 3:
            self.caution_top_ten_order_signature = ()
            self.caution_top_ten_stable_ticks = 0
            return False
        if signature == self.caution_top_ten_order_signature:
            self.caution_top_ten_stable_ticks += 1
        else:
            self.caution_top_ten_order_signature = signature
            self.caution_top_ten_stable_ticks = 1
        return self.caution_top_ten_stable_ticks >= required_ticks

    def is_short_track(self, track_info):
        if not track_info:
            return False
        track_type = str(track_info.get("track_type", "") or "").lower()
        track_name = str(track_info.get("track_name", "") or "").lower()
        length = self.track_length_miles(track_info.get("track_length"))
        if length is not None and length <= 1.0 and "road" not in track_type:
            return True
        return any(
            name in track_name
            for name in (
                "martinsville",
                "bristol",
                "richmond",
                "north wilkesboro",
                "south boston",
                "stafford",
                "irwindale",
                "langley",
            )
        )

    def track_length_miles(self, value):
        if not value:
            return None
        text = str(value).strip().lower()
        try:
            number = float(text.split()[0])
        except (TypeError, ValueError, IndexError):
            return None
        if "km" in text:
            return number * 0.621371
        return number

    def top_ten_has_pit_road_cars(self, results, pit_road_status):
        if not pit_road_status:
            return False
        ordered = self.sorted_running_order(results)[:10]
        for car in ordered:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue
            try:
                if bool(pit_road_status[int(car_idx)]):
                    return True
            except Exception:
                continue
        return False

    def _queue_lucky_dog_note(self, results, driver_lookup, current_lap):
        if self.caution_lucky_dog_queued:
            return
        lucky = self.find_lucky_dog_candidate(results)
        if not lucky:
            return
        car_idx, laps_down = lucky
        driver = driver_lookup.get(car_idx, {})
        name = driver.get("name", f"Car {car_idx}")
        number = driver.get("number", "?")
        lap_word = "lap" if laps_down == 1 else "laps"
        self.caution_lucky_dog_queued = True
        self.broadcast_queue.add(
            (
                f"Free pass watch as they double up: the lucky dog should be "
                f"the {number} of {name}, scored {laps_down} {lap_word} down."
            ),
            priority=8,
            category="lucky_dog",
            protected=True,
            speaker="lead",
            delay_seconds=4.0,
            expires_after=60,
            dedupe_key=f"lucky_dog:{current_lap}",
            camera_target_car_idx=car_idx,
            participant_car_indices=(car_idx,),
        )

    def find_lucky_dog_candidate(self, results):
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        if len(valid) < 2:
            return None
        leader_laps = max(
            self.safe_int(car.get("LapsComplete", car.get("Lap", 0)))
            for car in valid
        )
        if leader_laps <= 0:
            return None
        ordered = self.sorted_running_order(valid)
        for car in ordered:
            laps = self.safe_int(car.get("LapsComplete", car.get("Lap", 0)))
            laps_down = leader_laps - laps
            if laps_down > 0:
                return car.get("CarIdx"), laps_down
        return None

    def _queue_late_caution_note(self, current_lap, total_laps):
        if self.late_caution_note_queued or total_laps <= 0 or current_lap <= 0:
            return
        laps_to_go = max(total_laps - current_lap, 0)
        if laps_to_go > 2:
            return
        self.late_caution_note_queued = True
        self.broadcast_queue.add(
            (
                "With this caution coming so late, we could be looking at a "
                "green-white-checkered finish."
            ),
            priority=10,
            category="late_caution_note",
            protected=True,
            speaker="lead",
            delay_seconds=2.0,
            expires_after=60,
            dedupe_key=f"late_caution_note:{current_lap}",
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

    def _queue_stage_end_if_due(self, results, driver_lookup, current_lap, caution=False):
        stage_number, stage_lap = self.stage_due(current_lap)
        if not stage_number:
            return False

        message = self.build_stage_end_message(
            stage_number,
            stage_lap,
            results,
            driver_lookup,
            caution=caution,
        )
        if not message:
            return False

        self.stages_announced.add(stage_number)
        if caution:
            self.rewrite_pending_caution_as_stage_break(stage_number, stage_lap)
            delay = 2.0
            priority = 11
        else:
            delay = 0.0
            priority = 12

        self.broadcast_queue.add(
            message,
            priority=priority,
            category="stage_end",
            protected=True,
            speaker="lead",
            delay_seconds=delay,
            expires_after=90,
            dedupe_key=f"stage_end:{stage_number}:{stage_lap}",
        )
        return True

    def stage_due(self, current_lap):
        current_lap = self.safe_int(current_lap, 0)
        if current_lap <= 0:
            return (0, 0)

        for index, stage_lap in enumerate(self.stage_end_laps, start=1):
            if index in self.stages_announced:
                continue
            if current_lap >= stage_lap:
                return (index, stage_lap)
        return (0, 0)

    def build_stage_end_message(
        self,
        stage_number,
        stage_lap,
        results,
        driver_lookup,
        caution=False,
    ):
        ordered = self.sorted_running_order(results)[:10]
        if not ordered:
            return ""

        winner = self.driver_label(ordered[0], driver_lookup)
        top_ten = [
            f"{self.position_word(index)}, {self.driver_label(car, driver_lookup)}"
            for index, car in enumerate(ordered, start=1)
        ]
        caution_phrase = (
            " The caution is for the scheduled stage break."
            if caution
            else " The race stays green, but those stage points are now locked in."
        )
        return (
            f"Stage {stage_number} is complete at lap {stage_lap}. "
            f"{winner} wins the stage.{caution_phrase} "
            f"The stage points top ten: {'; '.join(top_ten)}."
        )

    def driver_label(self, car, driver_lookup):
        car_idx = car.get("CarIdx")
        driver = driver_lookup.get(car_idx, {})
        number = driver.get("number", "?")
        name = driver.get("name", f"Car {car_idx}")
        return f"the {number} of {name}"

    def rewrite_pending_caution_as_stage_break(self, stage_number, stage_lap):
        for item in self.broadcast_queue.items:
            if item.dedupe_key != "race_control:caution":
                continue
            item.message = (
                f"Caution is out for the end of Stage {stage_number} at lap {stage_lap}. "
                "That is a scheduled stage break, and the field will reset under yellow."
            )
            return True
        return False

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
                camera_return_home_after_sequence=getattr(
                    segment,
                    "camera_return_home_after_sequence",
                    False,
                ),
                feature_duration_seconds=getattr(
                    segment,
                    "feature_duration_seconds",
                    0.0,
                ),
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
        if self.joined_mid_race:
            return [dict(car) for car in results or []]

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
        total_laps=0,
    ):
        caution_just_started = (
            self.race_director.phase == RacePhase.CAUTION
            and self.race_director.phase_changed
            and self.race_director.previous_phase not in (
                RacePhase.CAUTION,
                RacePhase.ONE_TO_GREEN,
            )
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
            session_time=getattr(telemetry, "get_session_time", lambda: 0.0)(),
            suppress_soft_events=self.should_suppress_soft_incidents(),
        )
        if caution_just_started:
            events = [
                event
                for event in events
                if getattr(event, "trouble_type", "") != "possible trouble"
            ]
        if (
            self.race_director.phase in (RacePhase.CAUTION, RacePhase.ONE_TO_GREEN)
            and not caution_just_started
        ):
            events = [
                event for event in events
                if getattr(event, "trouble_type", "") != "pack wreck"
            ]
        if not events and caution_just_started:
            fallback = (
                self.incident_detector.build_big_wreck_fallback(current_lap)
                or self.incident_detector.build_caution_fallback(current_lap)
            )
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
        caution_replay_session_num = (
            self.caution_started_session_num
            if self.caution_started_session_num is not None
            else session_num
        )
        caution_replay_session_time = (
            self.caution_started_session_time
            if self.caution_started_session_time is not None
            else session_time
        )
        for event in events:
            is_pack_wreck = event.trouble_type == "pack wreck"
            audio_only_final_lap_pack_wreck = (
                is_pack_wreck
                and self.is_final_lap_window(current_lap, total_laps)
                and not caution_just_started
            )
            if (
                is_pack_wreck
                and not caution_just_started
                and not self.is_final_lap_window(current_lap, total_laps)
            ):
                continue
            replay_eligible = (
                (not is_pack_wreck and event.incident_delta >= 2)
                or (not is_pack_wreck and event.trouble_type == "caution candidate")
                or (is_pack_wreck and caution_just_started)
            )
            candidate_replay_time = getattr(event, "replay_session_time", None)
            candidate_confidence = str(
                getattr(event, "replay_confidence", "") or ""
            ).lower()
            high_confidence_candidate = (
                event.trouble_type == "caution candidate"
                and candidate_confidence == "high"
                and candidate_replay_time is not None
            )
            use_incident_marker_replay = (
                caution_just_started
                and replay_eligible
            )
            replay_message = self.incident_broadcast_message(
                event,
                current_lap=current_lap,
                total_laps=total_laps,
                use_incident_marker_replay=use_incident_marker_replay,
                high_confidence_candidate=high_confidence_candidate,
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
                    None
                    if use_incident_marker_replay or audio_only_final_lap_pack_wreck
                    else event.car_idx
                ),
                participant_car_indices=(
                    ()
                    if use_incident_marker_replay or audio_only_final_lap_pack_wreck
                    else (event.car_idx,)
                ),
                camera_focus_incident=(
                    event.trouble_type == "pack wreck"
                    and not audio_only_final_lap_pack_wreck
                ),
                camera_incident_group="Far Chase",
                replay_session_num=(
                    caution_replay_session_num
                    if use_incident_marker_replay
                    else session_num if replay_eligible else None
                ),
                replay_session_time=(
                    caution_replay_session_time
                    if use_incident_marker_replay
                    else (
                        candidate_replay_time
                        if high_confidence_candidate
                        else session_time if replay_eligible else None
                    )
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

    def incident_broadcast_message(
        self,
        event,
        current_lap,
        total_laps=0,
        use_incident_marker_replay=False,
        high_confidence_candidate=False,
    ):
        if use_incident_marker_replay or high_confidence_candidate:
            return "We are going to see if we can find the cause of this caution."

        if event.trouble_type != "pack wreck":
            return event.message

        if self.is_final_lap_window(current_lap, total_laps):
            return (
                "Big trouble in the pack on the final lap. Multiple cars are "
                "involved, and the rest of the field still has to race back to "
                "the checkered flag."
            )

        return (
            "Big trouble in the pack. Several cars are suddenly showing trouble, "
            "and this could change the whole shape of the race if the caution "
            "does not come out."
        )

    def is_final_lap_window(self, current_lap, total_laps):
        current_lap = self.safe_int(current_lap)
        total_laps = self.safe_int(total_laps)
        if total_laps <= 0:
            return False
        return current_lap >= max(0, total_laps - 1)

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
        session_time_reader = getattr(telemetry, "get_session_time", None)
        session_num = session_num_reader() if session_num_reader else 0
        session_time = session_time_reader() if session_time_reader else 0.0
        if self.caution_started_session_num is not None:
            session_num = self.caution_started_session_num
        if self.caution_started_session_time is not None:
            session_time = self.caution_started_session_time
        self.caution_marker_replay_count += 1
        self.broadcast_queue.add(
            "We are going to see if we can find the cause of this caution.",
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
            replay_session_time=session_time,
            replay_incident_delta=0,
            replay_multi_angle=True,
            replay_use_incident_marker=True,
            replay_marker_pre_roll_frames=self.restart_caution_marker_pre_roll_frames(
                green_lap_count
            ),
        )

    def restart_caution_marker_pre_roll_frames(self, green_lap_count):
        return 25 * 60

    def has_pending_non_restart_story(self):
        for item in self.broadcast_queue.items:
            if item.category == "race_control":
                continue
            if item.category == "restart_launch":
                continue
            return True
        return False

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
        self.broadcast_story_producer.frame(
            item,
            race_state=race_state,
            race_knowledge=race_knowledge,
        )
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
        self._queue_booth_follow_up(item, race_state)

    def _queue_booth_follow_up(self, item, race_state):
        follow_up = self.booth_followup_director.follow_up_for(
            item,
            race_state=race_state,
        )
        if not follow_up:
            return

        self.broadcast_queue.add(
            self.commentary_cleaner.clean(follow_up),
            priority=max(1, self.safe_int(getattr(item, "priority", 5)) - 1),
            category="race_story_follow_up",
            protected=False,
            speaker="jeff",
            delay_seconds=0.1,
            expires_after=35,
            dedupe_key=f"booth_follow_up:{self.editorial_producer.build_story_id(item)}",
            camera_target_car_idx=None,
            participant_car_indices=(),
        )
