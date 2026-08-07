from enum import Enum

from config import (
    POST_RACE_INTERVIEWS_ENABLED,
    SPONSOR_READ_CAUSE,
    USE_SPONSOR_READS,
)
from helpers.position_formatter import PositionFormatter


class RacePhase(Enum):
    UNKNOWN = "UNKNOWN"
    FORMATION = "FORMATION"
    GREEN = "GREEN"
    CAUTION = "CAUTION"
    ONE_TO_GREEN = "ONE_TO_GREEN"
    CHECKERED = "CHECKERED"


class RaceDirector:
    CHECKERED_FLAG = 0x00000001
    WHITE_FLAG = 0x00000002
    GREEN_FLAG = 0x00000004
    YELLOW_FLAG = 0x00000008
    YELLOW_WAVING = 0x00000100
    ONE_LAP_TO_GREEN = 0x00000200
    CAUTION = 0x00004000
    CAUTION_WAVING = 0x00008000
    START_READY = 0x20000000
    START_SET = 0x40000000
    START_GO = 0x80000000
    SESSION_STATE_CHECKERED = 5
    SESSION_STATE_COOL_DOWN = 6
    POST_RACE_MIN_STABILIZATION_TICKS = 12
    POST_RACE_STABLE_ORDER_TICKS = 6
    POST_RACE_STABLE_ORDER_CARS = 20

    def __init__(
        self,
        post_race_interviews_enabled=POST_RACE_INTERVIEWS_ENABLED,
    ):
        self.post_race_interviews_enabled = bool(post_race_interviews_enabled)
        self.reset()

    def reset(self):
        self.phase = RacePhase.UNKNOWN
        self.previous_phase = RacePhase.UNKNOWN
        self.phase_changed = False
        self.race_started = False

        self.formation_announced = False
        self.yellow_announced = False
        self.one_to_green_announced = False

        self.ten_to_go_announced = False
        self.five_to_go_announced = False
        self.two_to_go_announced = False
        self.white_flag_announced = False
        self.final_lap_calls_announced = set()
        self.checkered_announced = False
        self.post_race_results_queued = False
        self.checkered_stabilization_ticks = 0
        self.finish_order_signature = ()
        self.finish_order_stable_ticks = 0
        self.finish_confirmed_by_session_state = False
        self.progress_milestones_announced = set()
        self.progress_sponsor_cause = (
            (SPONSOR_READ_CAUSE or "Autism Awareness").strip()
            if USE_SPONSOR_READS
            else ""
        )
        self.last_results = []
        self.last_driver_lookup = {}
        self.admin_caution_pending = False

    def mark_admin_caution_pending(self):
        self.admin_caution_pending = True

    def update(self, telemetry, results, driver_lookup, scheduler):
        self.phase_changed = False
        session_flags = telemetry.get_session_flags()
        state_reader = getattr(telemetry, "get_session_state", None)
        session_state = state_reader() if state_reader else 0
        self.finish_confirmed_by_session_state = self.safe_int(session_state) in (
            self.SESSION_STATE_CHECKERED,
            self.SESSION_STATE_COOL_DOWN,
        )
        total_laps = telemetry.get_total_laps()
        current_lap = self.get_best_race_lap(telemetry.get_lap(), results)
        track_info = telemetry.get_track_info()

        if results:
            self.last_results = list(results)
        if driver_lookup:
            self.last_driver_lookup = dict(driver_lookup)

        effective_results = results or self.last_results
        effective_driver_lookup = driver_lookup or self.last_driver_lookup

        new_phase = self.detect_phase(
            session_flags,
            effective_results,
            current_lap,
            total_laps,
            session_state=session_state,
        )

        if new_phase != RacePhase.CHECKERED:
            self.handle_lap_calls(current_lap, total_laps, scheduler, session_flags)

        if new_phase != self.phase:
            self.phase_changed = True
            self.previous_phase = self.phase
            self.phase = new_phase
            self.handle_phase_change(
                effective_results,
                effective_driver_lookup,
                scheduler,
                track_info,
            )

        if new_phase == RacePhase.GREEN:
            self.race_started = True

        if self.phase == RacePhase.CHECKERED:
            self.handle_post_race_results(
                effective_results,
                effective_driver_lookup,
                scheduler,
                track_info,
                current_lap=current_lap,
                total_laps=total_laps,
            )

    def detect_phase(
        self,
        session_flags,
        results,
        current_lap,
        total_laps,
        session_state=0,
    ):
        if self.safe_int(session_state) in (
            self.SESSION_STATE_CHECKERED,
            self.SESSION_STATE_COOL_DOWN,
        ):
            return RacePhase.CHECKERED

        if self.has_flag(session_flags, self.CHECKERED_FLAG):
            return RacePhase.CHECKERED

        if total_laps > 0 and current_lap >= total_laps:
            return RacePhase.CHECKERED

        if self.has_flag(session_flags, self.ONE_LAP_TO_GREEN):
            return RacePhase.ONE_TO_GREEN

        if self.has_flag(session_flags, self.CAUTION) or self.has_flag(session_flags, self.CAUTION_WAVING):
            return RacePhase.CAUTION

        if self.has_flag(session_flags, self.YELLOW_FLAG) or self.has_flag(session_flags, self.YELLOW_WAVING):
            return RacePhase.CAUTION

        if self.has_flag(session_flags, self.GREEN_FLAG) or self.has_flag(session_flags, self.START_GO):
            return RacePhase.GREEN

        if current_lap > 0:
            return RacePhase.GREEN

        if self.race_started:
            return RacePhase.GREEN

        if self.has_flag(session_flags, self.START_READY) or self.has_flag(session_flags, self.START_SET):
            return RacePhase.FORMATION

        if results:
            return RacePhase.FORMATION

        return RacePhase.UNKNOWN

    def handle_phase_change(self, results, driver_lookup, scheduler, track_info):
        if self.phase == RacePhase.FORMATION:
            self.handle_formation(scheduler)

        elif self.phase == RacePhase.GREEN:
            self.handle_green_flag(scheduler, track_info)

        elif self.phase == RacePhase.CAUTION:
            self.handle_caution(scheduler, track_info)

        elif self.phase == RacePhase.ONE_TO_GREEN:
            self.handle_one_to_green(results, driver_lookup, scheduler, track_info)

        elif self.phase == RacePhase.CHECKERED:
            self.handle_checkered(results, driver_lookup, scheduler, track_info)

    def handle_formation(self, scheduler):
        if self.formation_announced:
            return

        scheduler.add(
            "The field is rolling away for the parade laps as the drivers get ready for the start.",
            priority=10,
            category="race_control",
            protected=False,
            speaker="lead",
            expires_after=45,
            dedupe_key="race_control:formation",
        )
        self.formation_announced = True

    def handle_green_flag(self, scheduler, track_info):
        sponsor_pending = getattr(scheduler, "has_pending_category", lambda _category: False)(
            "sponsor_read"
        )
        sponsor_on_air = getattr(scheduler, "is_busy_with_category", lambda _category: False)(
            "sponsor_read"
        )
        scheduler.clear_for_race_control(
            preserve_categories=("sponsor_read",),
            reset_busy=not sponsor_on_air,
        )
        track_name = self.get_track_name(track_info)

        if self.race_started and self.previous_phase in [RacePhase.CAUTION, RacePhase.ONE_TO_GREEN]:
            message = f"Green flag is back in the air! We are racing again at {track_name}!"
        else:
            message = f"Green flag is in the air! We are racing at {track_name}!"

        scheduler.add(
            message,
            priority=7 if sponsor_pending else 12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=30,
            dedupe_key=f"race_control:green:{self.previous_phase.value}",
        )

        self.yellow_announced = False
        self.one_to_green_announced = False

    def handle_caution(self, scheduler, track_info):
        if self.yellow_announced:
            return

        track_name = self.get_track_name(track_info)

        if not self.race_started:
            # League admins often extend the initial pace laps before the green.
            # iRacing can expose that as a yellow/caution flag even though there
            # is no incident. Do not clear the welcome, track info, sponsor read,
            # or starting lineup for that pre-race control state.
            scheduler.add(
                (
                    f"Race control is adding another pace lap before the start here at {track_name}. "
                    "That gives the field time to get lined up and serve any pre-race penalties before we go green."
                ),
                priority=7,
                category="race_control",
                protected=False,
                speaker="lead",
                expires_after=35,
                dedupe_key="race_control:pre_start_extension",
                camera_focus_incident=False,
            )
            self.yellow_announced = True
            self.one_to_green_announced = False
            self.admin_caution_pending = False
            return

        scheduler.clear_for_race_control()

        extended_yellow = self.race_started and self.previous_phase == RacePhase.ONE_TO_GREEN
        if extended_yellow:
            message = (
                f"The yellow is being extended one more lap here at {track_name}. "
                "Race control is giving the field another lap to get lined up for the restart."
            )
            dedupe_key = "race_control:caution_extended"
            camera_focus_incident = False
        elif self.admin_caution_pending:
            message = (
                f"Race control has put out the caution here at {track_name}. "
                "The field will slow and get gathered back up."
            )
            dedupe_key = "race_control:admin_caution"
            camera_focus_incident = False
        else:
            message = f"Trouble on the speedway - caution is out here at {track_name}."
            dedupe_key = "race_control:caution"
            camera_focus_incident = True

        scheduler.add(
            message,
            priority=12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=30,
            dedupe_key=dedupe_key,
            camera_focus_incident=camera_focus_incident,
            camera_incident_group="Far Chase",
        )

        self.yellow_announced = True
        self.one_to_green_announced = False
        self.admin_caution_pending = False

    def handle_one_to_green(self, results, driver_lookup, scheduler, track_info):
        if self.one_to_green_announced:
            return

        track_name = self.get_track_name(track_info)

        if self.race_started:
            scheduler.clear_for_race_control(
                preserve_categories=("caution_pit_summary", "sponsor_read"),
                reset_busy=False,
            )
            message = (
                f"One lap to green here at {track_name}. "
                "The field is doubling up for the restart."
            )
            dedupe_key = "race_control:one_to_green:restart"
            priority = 11
            protected = True
        else:
            message = (
                f"One pace lap remains before the green flag here at {track_name}. "
                "The pace car lights are off, and the start is coming up soon."
            )
            dedupe_key = "race_control:one_to_green:initial"
            priority = 8
            protected = False

        scheduler.add(
            message,
            priority=priority,
            category="race_control",
            protected=protected,
            speaker="lead",
            expires_after=45,
            dedupe_key=dedupe_key,
        )

        self.one_to_green_announced = True

    def handle_checkered(self, results, driver_lookup, scheduler, track_info):
        scheduler.clear_for_race_control()

        if self.checkered_announced:
            return

        winner_car_idx = self.get_winner_car_idx(results)
        track_name = self.get_track_name(track_info)

        message = (
            f"Checkered flag is out at {track_name}. "
            "The leader is coming to the stripe."
        )

        scheduler.add(
            message,
            priority=12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=60,
            dedupe_key="race_control:checkered",
            camera_sequence_steps=(
                (winner_car_idx, "TV Mixed", 0),
            )
            if winner_car_idx is not None
            else (),
        )

        self.checkered_announced = True
        self.checkered_stabilization_ticks = 0
        self.finish_order_signature = ()
        self.finish_order_stable_ticks = 0

    def handle_post_race_results(
        self,
        results,
        driver_lookup,
        scheduler,
        track_info,
        current_lap=0,
        total_laps=0,
    ):
        if not self.checkered_announced or self.post_race_results_queued:
            return

        if not self.finish_distance_complete(results, total_laps, current_lap):
            return

        if not self.finish_top_group_complete(results, total_laps):
            return

        self.checkered_stabilization_ticks += 1
        if self.checkered_stabilization_ticks < self.POST_RACE_MIN_STABILIZATION_TICKS:
            return

        if not self.finish_order_is_stable(
            results,
            required_ticks=self.POST_RACE_STABLE_ORDER_TICKS,
            max_cars=self.POST_RACE_STABLE_ORDER_CARS,
        ):
            return

        track_name = self.get_track_name(track_info)

        scheduler.add(
            self.build_winner_story(results, driver_lookup, track_name),
            priority=10,
            category="post_race_story",
            protected=True,
            speaker="lead",
            delay_seconds=1.0,
            expires_after=180,
            dedupe_key="post_race:winner_story",
        )

        scheduler.add(
            self.build_finish_rundown(results, driver_lookup, max_cars=None),
            priority=9,
            category="post_race",
            protected=True,
            speaker="lead",
            delay_seconds=8.0,
            expires_after=180,
            dedupe_key="post_race:finish_rundown",
        )

        scheduler.add(
            self.build_post_race_recap(results, driver_lookup, track_name),
            priority=8,
            category="post_race_recap",
            protected=True,
            speaker="lead",
            delay_seconds=18.0,
            expires_after=240,
            dedupe_key="post_race:recap",
        )

        if self.post_race_interviews_enabled:
            scheduler.add(
                self.build_interview_handoff(results, driver_lookup),
                priority=7,
                category="post_race_interviews",
                protected=True,
                speaker="lead",
                delay_seconds=32.0,
                expires_after=240,
                dedupe_key="post_race:interview_handoff",
            )
        else:
            scheduler.add(
                self.build_signoff(track_name),
                priority=7,
                category="post_race_signoff",
                protected=True,
                speaker="lead",
                delay_seconds=32.0,
                expires_after=240,
                dedupe_key="post_race:signoff",
            )

        self.post_race_results_queued = True

    def finish_distance_complete(self, results, total_laps=0, current_lap=0):
        if self.finish_confirmed_by_session_state:
            return True

        total_laps = self.safe_int(total_laps)
        if total_laps <= 0:
            return True

        observed_lap = self.safe_int(current_lap)
        ordered = self.sort_results(results or [])
        if ordered:
            leader = ordered[0]
            for key in ("Lap", "LapsComplete"):
                observed_lap = max(observed_lap, self.safe_int(leader.get(key)))

        return observed_lap >= total_laps

    def finish_top_group_complete(self, results, total_laps=0, max_cars=10):
        if self.finish_confirmed_by_session_state:
            return True

        total_laps = self.safe_int(total_laps)
        if total_laps <= 0:
            return True

        ordered = self.sort_results(results or [])[:max_cars]
        if not ordered:
            return False

        # Older replay/test snapshots may not include lap-complete fields.
        # In that case, fall back to the stabilization/signature gate.
        has_lap_data = any(
            ("Lap" in car or "LapsComplete" in car)
            for car in ordered
        )
        if not has_lap_data:
            return True

        for car in ordered:
            laps = max(
                self.safe_int(car.get("Lap", 0)),
                self.safe_int(car.get("LapsComplete", 0)),
            )
            laps_behind = max(
                [
                    self.safe_int(car.get(key), -1)
                    for key in ("LapsBehind", "ClassLapsBehind")
                    if key in car
                ]
                or [-1]
            )
            if laps >= total_laps:
                continue
            if laps_behind > 0 and laps >= total_laps - laps_behind:
                continue
            return False
        return True

    def finish_order_is_stable(self, results, required_ticks=3, max_cars=10):
        ordered = self.sort_results(results or [])[:max_cars]
        signature = tuple(car.get("CarIdx") for car in ordered)
        if len(signature) < 1:
            self.finish_order_signature = ()
            self.finish_order_stable_ticks = 0
            return False
        if signature == self.finish_order_signature:
            self.finish_order_stable_ticks += 1
        else:
            self.finish_order_signature = signature
            self.finish_order_stable_ticks = 1
        return self.finish_order_stable_ticks >= required_ticks

    def handle_lap_calls(self, current_lap, total_laps, scheduler, session_flags=0):
        if not self.race_started or total_laps <= 0 or current_lap <= 0:
            return

        laps_to_go = max(total_laps - current_lap, 0)

        self.handle_progress_milestone(
            current_lap,
            total_laps,
            laps_to_go,
            scheduler,
        )

        if (
            total_laps > 10
            and 5 < laps_to_go <= 10
            and not self.ten_to_go_announced
        ):
            scheduler.clear_for_race_control(
                preserve_categories=("caution_pit_summary", "sponsor_read")
            )
            scheduler.add(
                "Ten laps to go. The closing stage of this race is underway.",
                priority=12,
                category="race_control",
                protected=True,
                speaker="lead",
                expires_after=15,
                dedupe_key="race_control:ten_to_go",
            )
            self.ten_to_go_announced = True

        if total_laps > 5 and laps_to_go in (5, 2):
            self.handle_final_lap_countdown(laps_to_go, scheduler)

        white_flag_is_out = self.has_flag(session_flags, self.WHITE_FLAG)
        if (
            (white_flag_is_out or 0 < laps_to_go <= 1)
            and not self.white_flag_announced
        ):
            scheduler.clear_for_race_control(reset_busy=False)
            scheduler.add(
                "White flag. One lap to go.",
                priority=13,
                category="race_control",
                protected=True,
                speaker="lead",
                expires_after=10,
                dedupe_key="race_control:white_flag",
            )
            self.white_flag_announced = True

    def handle_final_lap_countdown(self, laps_to_go, scheduler):
        if laps_to_go in self.final_lap_calls_announced:
            return

        messages = {
            5: "Five laps to go. The pressure is about to ramp up.",
            2: "Two laps to go.",
        }
        message = messages.get(laps_to_go)
        if not message:
            return

        scheduler.clear_for_race_control(
            preserve_categories=("caution_pit_summary", "sponsor_read"),
            reset_busy=False,
        )
        scheduler.add(
            message,
            priority=12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=15,
            dedupe_key=f"race_control:{self.final_lap_key(laps_to_go)}_to_go",
        )
        self.final_lap_calls_announced.add(laps_to_go)
        if laps_to_go == 5:
            self.five_to_go_announced = True
        if laps_to_go == 2:
            self.two_to_go_announced = True

    def final_lap_key(self, laps_to_go):
        words = {
            5: "five",
            2: "two",
        }
        return words.get(laps_to_go, str(laps_to_go))

    def handle_progress_milestone(
        self,
        current_lap,
        total_laps,
        laps_to_go,
        scheduler,
    ):
        if total_laps < 20:
            return

        milestones = [
            ("quarter", max(1, round(total_laps * 0.25))),
            ("halfway", max(1, round(total_laps * 0.50))),
            ("three_quarter", max(1, round(total_laps * 0.75))),
        ]
        reached = [item for item in milestones if current_lap >= item[1]]
        if not reached:
            return

        latest_name, _ = reached[-1]
        if latest_name in self.progress_milestones_announced:
            return
        if laps_to_go <= 10:
            return

        messages = {
            "quarter": (
                f"{laps_to_go} laps remain. We are one quarter of the way "
                "through this race."
            ),
            "halfway": (
                f"Halfway at the stripe. {laps_to_go} laps remain in this race."
            ),
            "three_quarter": (
                f"{laps_to_go} laps to go as we enter the final quarter of the race."
            ),
        }
        message = self.with_progress_sponsor(messages[latest_name])
        scheduler.add(
            message,
            priority=9,
            category="race_progress",
            protected=True,
            speaker="lead",
            expires_after=45,
            dedupe_key=f"race_progress:{latest_name}",
        )
        self.progress_milestones_announced.add(latest_name)

    def with_progress_sponsor(self, message):
        if not self.progress_sponsor_cause:
            return message
        return (
            f"{message} This race update is presented in support of "
            f"{self.progress_sponsor_cause}."
        )

    def get_track_name(self, track_info):
        if not track_info:
            return "the speedway"
        return track_info.get("track_name", "the speedway") or "the speedway"

    def get_winner(self, results, driver_lookup):
        car_idx = self.get_winner_car_idx(results)
        if car_idx is None:
            return ""

        driver_info = driver_lookup.get(car_idx, {})
        number = driver_info.get("number", "?")
        name = driver_info.get("name", f"Car {car_idx}")

        return f"the {number} of {name}"

    def get_winner_car_idx(self, results):
        ordered = self.sort_results(results or [])
        if not ordered:
            return None
        return ordered[0].get("CarIdx")

    def build_finish_rundown(self, results, driver_lookup, max_cars=10):
        if not results:
            return "Official finishing results are not available yet."

        lines = ["Here is how they finished."]

        zero_based_positions = self.results_are_zero_based(results)
        ordered = self.sort_results(results)
        if max_cars is not None:
            ordered = ordered[:max_cars]
        for car in ordered:
            lines.append(
                self.format_driver_position(
                    car,
                    driver_lookup,
                    zero_based_positions=zero_based_positions,
                )
            )

        return " ".join(lines)

    def build_winner_story(self, results, driver_lookup, track_name):
        ordered = self.sort_results(results or [])
        if not ordered:
            return (
                f"The race is complete at {track_name}. We will let timing "
                "and scoring settle before we run through the finishing order."
            )

        winner = ordered[0]
        car_idx = winner.get("CarIdx")
        driver_info = driver_lookup.get(car_idx, {})
        name = driver_info.get("name", f"Car {car_idx}")
        number = driver_info.get("number", "?")
        start = self.best_starting_position(winner)
        laps_led = self.best_laps_led(winner)

        story_parts = [
            f"{name} wins at {track_name} in the number {number}.",
        ]
        if start > 0 and start != 1:
            story_parts.append(
                f"That was a climb from {PositionFormatter.ordinal(start)} on the grid."
            )
        elif start == 1:
            story_parts.append("The pole sitter converted track position into the race win.")
        if laps_led > 0:
            lap_word = "lap" if laps_led == 1 else "laps"
            story_parts.append(
                f"The winning run included {laps_led} {lap_word} led."
            )
        story_parts.append(
            "We will let the rest of the field get across the line, then we will run through the top ten."
        )
        return " ".join(story_parts)

    def build_post_race_recap(self, results, driver_lookup, track_name):
        ordered = self.sort_results(results or [])
        if not ordered:
            return (
                f"Final recap from {track_name}: timing and scoring did not provide "
                "enough finishing data for a full race summary."
            )

        winner = ordered[0]
        winner_text = self.driver_label(winner, driver_lookup)
        parts = [f"Final race recap from {track_name}: {winner_text} gets the win."]

        most_led = self.most_laps_led_result(ordered)
        if most_led:
            car, laps_led = most_led
            lap_word = "lap" if laps_led == 1 else "laps"
            parts.append(
                f"The most laps led belonged to {self.driver_label(car, driver_lookup)}, "
                f"who paced the field for {laps_led} {lap_word}."
            )

        biggest_mover = self.biggest_mover_result(ordered)
        if biggest_mover:
            car, gained = biggest_mover
            spot_word = "spot" if gained == 1 else "spots"
            parts.append(
                f"The biggest mover was {self.driver_label(car, driver_lookup)}, "
                f"up {gained} {spot_word} from the starting grid."
            )

        fastest = self.fastest_lap_result(ordered)
        if fastest:
            car, lap_time = fastest
            parts.append(
                f"Fastest lap went to {self.driver_label(car, driver_lookup)} "
                f"at {self.format_lap_time(lap_time)}."
            )

        lead_lap = self.lead_lap_finishers_text(ordered)
        if lead_lap:
            parts.append(lead_lap)

        parts.append(
            "That gives us the story of the night after the finish order has settled."
        )
        return " ".join(parts)

    def build_signoff(self, track_name):
        return (
            f"That will do it tonight from {track_name}. "
            "For Jeff and Sarah, I am Mike with RGC AI Broadcast. "
            "Thank you for watching, and we will see you next time."
        )

    def build_interview_handoff(self, results, driver_lookup):
        podium = self.podium_names(results, driver_lookup)
        if len(podium) >= 3:
            return (
                "Do not go anywhere. The top three are headed to post-race interviews. "
                f"We will hear from {podium[2]} first, then {podium[1]}, "
                f"and finally tonight's winner, {podium[0]}. "
                "Race control will take it from here with the drivers."
            )
        return (
            "Do not go anywhere. Post-race interviews are coming up next, "
            "and race control will take it from here with the drivers."
        )

    def podium_names(self, results, driver_lookup):
        names = []
        for car in self.sort_results(results or [])[:3]:
            car_idx = car.get("CarIdx")
            driver_info = driver_lookup.get(car_idx, {})
            names.append(driver_info.get("name", f"Car {car_idx}"))
        return names

    def best_starting_position(self, car):
        return max(
            self.safe_int(car.get("StartingPosition", 0)),
            self.safe_int(car.get("StartPosition", 0)),
            self.safe_int(car.get("GridPosition", 0)),
        )

    def driver_label(self, car, driver_lookup):
        car_idx = car.get("CarIdx")
        driver_info = driver_lookup.get(car_idx, {})
        number = driver_info.get("number", "?")
        name = driver_info.get("name", f"Car {car_idx}")
        return f"the {number} of {name}"

    def most_laps_led_result(self, ordered_results):
        best_car = None
        best_laps = 0
        for car in ordered_results:
            laps_led = self.best_laps_led(car)
            if laps_led > best_laps:
                best_laps = laps_led
                best_car = car
        if best_car is None or best_laps <= 0:
            return None
        return best_car, best_laps

    def biggest_mover_result(self, ordered_results):
        best_car = None
        best_gain = 0
        zero_based_positions = self.results_are_zero_based(ordered_results)
        for car in ordered_results:
            start = self.best_starting_position(car)
            finish = self.get_display_position(car, zero_based_positions)
            if start <= 0 or finish <= 0:
                continue
            gain = start - finish
            if gain > best_gain:
                best_gain = gain
                best_car = car
        if best_car is None or best_gain <= 0:
            return None
        return best_car, best_gain

    def fastest_lap_result(self, ordered_results):
        best_car = None
        best_time = 0.0
        for car in ordered_results:
            lap_time = self.best_fastest_lap_time(car)
            if lap_time <= 0:
                continue
            if best_time <= 0 or lap_time < best_time:
                best_time = lap_time
                best_car = car
        if best_car is None or best_time <= 0:
            return None
        return best_car, best_time

    def best_fastest_lap_time(self, car):
        for key in (
            "FastestTime",
            "FastestLapTime",
            "BestLapTime",
            "fastest_lap_time",
        ):
            value = car.get(key)
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return 0.0

    def format_lap_time(self, lap_time):
        try:
            value = float(lap_time)
        except (TypeError, ValueError):
            return str(lap_time)
        minutes = int(value // 60)
        seconds = value - (minutes * 60)
        if minutes > 0:
            return f"{minutes}:{seconds:06.3f}"
        return f"{seconds:.3f} seconds"

    def lead_lap_finishers_text(self, ordered_results):
        if not ordered_results:
            return ""
        starters = len([car for car in ordered_results if car.get("CarIdx") is not None])
        if starters <= 0:
            return ""

        laps_behind_available = any(
            key in car
            for car in ordered_results
            for key in ("LapsBehind", "ClassLapsBehind")
        )
        if laps_behind_available:
            lead_lap_finishers = 0
            for car in ordered_results:
                laps_behind_values = [
                    self.safe_int(car.get(key), 0)
                    for key in ("LapsBehind", "ClassLapsBehind")
                    if key in car
                ]
                if laps_behind_values and max(laps_behind_values) == 0:
                    lead_lap_finishers += 1
        else:
            leader_laps = max(
                self.safe_int(ordered_results[0].get("LapsComplete", 0), 0),
                self.safe_int(ordered_results[0].get("Lap", 0), 0),
            )
            if leader_laps <= 0:
                return ""
            lead_lap_finishers = 0
            for car in ordered_results:
                car_laps = max(
                    self.safe_int(car.get("LapsComplete", 0), 0),
                    self.safe_int(car.get("Lap", 0), 0),
                )
                if car_laps >= leader_laps:
                    lead_lap_finishers += 1

        return (
            f"{lead_lap_finishers} of the {starters} starters finished on the lead lap."
        )

    def best_laps_led(self, car):
        return max(
            self.safe_int(car.get("LapsLed", 0)),
            self.safe_int(car.get("LedLaps", 0)),
            self.safe_int(car.get("LeaderLaps", 0)),
        )

    def format_driver_position(self, car, driver_lookup, zero_based_positions=False):
        car_idx = car.get("CarIdx")
        position = self.get_display_position(car, zero_based_positions)

        driver_info = driver_lookup.get(car_idx, {})
        name = driver_info.get("name", f"Car {car_idx}")
        number = driver_info.get("number", "?")

        return f"{PositionFormatter.ordinal(position)}, the {number} of {name}."

    def sort_results(self, results):
        zero_based_positions = self.results_are_zero_based(results)

        return sorted(
            results,
            key=lambda car: self.display_position(
                car.get("Position", 999),
                zero_based_positions,
            ),
        )

    def get_display_position(self, car, zero_based_positions=False):
        raw_position = car.get("Position", 999)
        try:
            position = int(raw_position)
        except Exception:
            return raw_position
        return position + 1 if zero_based_positions else position

    def get_best_race_lap(self, telemetry_lap, results):
        laps = []

        try:
            laps.append(int(telemetry_lap))
        except Exception:
            pass

        for car in results or []:
            for key in ["Lap", "LapsComplete"]:
                value = car.get(key)
                try:
                    laps.append(int(value))
                except Exception:
                    pass

        return max(laps) if laps else 0

    def results_are_zero_based(self, results):
        return any(car.get("Position") == 0 for car in results)

    def display_position(self, raw_position, zero_based_positions):
        try:
            position = int(raw_position)
        except Exception:
            return raw_position

        if zero_based_positions:
            return position + 1

        return position

    def has_flag(self, session_flags, flag):
        try:
            return int(session_flags) & flag != 0
        except Exception:
            return False

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
