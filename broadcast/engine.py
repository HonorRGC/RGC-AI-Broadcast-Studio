from broadcast.broadcast_queue import BroadcastQueue
from broadcaster.race_brain import RaceBrain
from broadcaster.race_director import RaceDirector, RacePhase
from production.commentary_cleaner import CommentaryCleaner
from production.action_detector import ActionDetector
from production.editorial_producer import EditorialDecisionType, EditorialProducer
from production.incident_detector import IncidentDetector
from production.openai_director import OpenAIDirector
from production.opening_director import OpeningDirector
from production.pit_strategy_detector import PitStrategyDetector
from production.race_intelligence import RaceIntelligence
from production.session_tracker import SessionTracker


class BroadcastEngine:
    """Single orchestration path shared by live and replay telemetry sources."""

    INCIDENT_DETECTION_AFTER_LAP = 2

    def __init__(self, openai_director=None):
        self.openai_director = openai_director or OpenAIDirector()
        self.commentary_cleaner = CommentaryCleaner()
        self.reset()

    def reset(self):
        self.session_tracker = SessionTracker()
        self._reset_race_session()

    def _reset_race_session(self):
        self.race_brain = RaceBrain()
        self.race_director = RaceDirector()
        self.race_intelligence = RaceIntelligence()
        self.action_detector = ActionDetector()
        self.editorial_producer = EditorialProducer()
        self.pit_strategy_detector = PitStrategyDetector()
        self.incident_detector = IncidentDetector()
        self.opening_director = OpeningDirector()
        self.broadcast_queue = BroadcastQueue()

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
        driver_lookup = telemetry.get_driver_lookup()
        current_lap = telemetry.get_lap()
        total_laps = telemetry.get_total_laps()
        session_flags = telemetry.get_session_flags()
        pit_road_status = telemetry.get_car_idx_on_pit_road()

        race_knowledge = self.race_intelligence.update(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            total_laps=total_laps,
            session_flags=session_flags,
            pit_road_status=pit_road_status,
        )
        race_state = self.race_intelligence.get_race_state()

        grid_reader = getattr(telemetry, "get_starting_grid", None)
        starting_grid = grid_reader() if grid_reader else results
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

        if self.race_director.race_started:
            self._collect_pit_stories(
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
            )

        if self.race_director.phase == RacePhase.GREEN:
            self.editorial_producer.submit_race_knowledge(race_knowledge)
            self._collect_action_stories(
                telemetry,
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
            )
            self._collect_pass_stories(results, driver_lookup)
            self._collect_incidents(
                telemetry,
                results,
                driver_lookup,
                pit_road_status,
                current_lap,
            )
            self._queue_editorial_decision(race_state, race_knowledge)

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
                protected=False,
                speaker=segment.speaker,
                expires_after=180,
                dedupe_key=segment.category,
            )

    def _collect_pass_stories(self, results, driver_lookup):
        for event in self.race_brain.analyze(results, driver_lookup):
            if event.importance < 6:
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
            )

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
        for event in self.pit_strategy_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
            pit_road_status=pit_road_status,
            current_lap=current_lap,
            under_caution=under_caution,
        ):
            self.editorial_producer.submit_pit_event(event)

    def _collect_incidents(
        self,
        telemetry,
        results,
        driver_lookup,
        pit_road_status,
        current_lap,
    ):
        if current_lap < self.INCIDENT_DETECTION_AFTER_LAP:
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
        )
        if not events:
            return

        self.broadcast_queue.clear_for_race_control()
        for event in events:
            self.broadcast_queue.add(
                self.commentary_cleaner.clean(event.message),
                priority=event.importance,
                category="incident",
                protected=True,
                speaker="lead",
                expires_after=25,
                dedupe_key=f"incident:{event.car_idx}:{event.trouble_type}",
            )

    def _queue_editorial_decision(self, race_state, race_knowledge):
        decision = self.editorial_producer.choose_next_item(race_state=race_state)
        if decision.decision_type != EditorialDecisionType.AIR_NOW or not decision.item:
            return

        item = decision.item
        fallback = self.commentary_cleaner.clean(item.summary)
        commentary = self.openai_director.generate_commentary(
            speaker=item.speaker,
            assignment=item,
            race_state=race_state,
            race_knowledge=race_knowledge,
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
