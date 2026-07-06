from dataclasses import dataclass
import time


@dataclass(frozen=True)
class CameraDecision:
    status: str
    reason: str
    car_idx: int | None = None
    car_number: str = ""
    group_number: int | None = None
    group_name: str = ""


class CameraDirector:
    MODES = ("off", "observe", "auto")

    def __init__(
        self,
        mode="off",
        preferred_group="TV1",
        home_group="TV Mixed",
        minimum_hold_seconds=8.0,
        return_after_seconds=10.0,
        lineup_camera_number=1,
        clock=None,
    ):
        if mode not in self.MODES:
            raise ValueError(f"Unknown camera mode: {mode}")
        self.mode = mode
        self.preferred_group = str(preferred_group or "TV1")
        self.home_group = str(home_group or "TV Mixed")
        self.minimum_hold_seconds = float(minimum_hold_seconds)
        self.return_after_seconds = float(return_after_seconds)
        self.lineup_camera_number = int(lineup_camera_number)
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        self.current_car_idx = None
        self.current_group_number = None
        self.current_role = ""
        self.last_switch_at = None
        self.return_home_at = None
        self.live_edge_initialized = False
        self.last_live_sync_at = None
        self.replay_active = False
        self.clear_sequence()

    def update(self, telemetry):
        if self.mode == "off" or not self.is_race_session(telemetry):
            return CameraDecision("ignored", "Camera direction is inactive.")

        if self.replay_active:
            return CameraDecision("held", "Incident replay controls the camera.")

        now = self.clock()
        live_decision = self.ensure_live_edge(telemetry, now)
        if live_decision is not None:
            return live_decision

        if (
            self.sequence
            and self.next_sequence_at is not None
            and now >= self.next_sequence_at
        ):
            if self.sequence_index < len(self.sequence):
                car_idx, group_name, camera_number = self.sequence[self.sequence_index]
                self.sequence_index += 1
                self.next_sequence_at = now + self.sequence_interval
                return self.focus_car(
                    car_idx,
                    group_name,
                    telemetry,
                    now,
                    role="lineup",
                    force=True,
                    camera_number=camera_number,
                )
            if self.current_role == "lineup":
                self.clear_sequence()
                return CameraDecision(
                    "held",
                    "Lineup camera holds until the next driver or green flag.",
                    car_idx=self.current_car_idx,
                    group_number=self.current_group_number,
                )
            self.clear_sequence()
            return self.focus_home(telemetry, now, force=True)

        if self.return_home_at is not None and now >= self.return_home_at:
            self.return_home_at = None
            return self.focus_home(telemetry, now, force=True)

        if self.current_car_idx is None:
            return self.focus_home(telemetry, now, force=True)

        if self.current_role == "home":
            leader_idx = self.get_leader_car_idx(telemetry)
            if leader_idx is not None and leader_idx != self.current_car_idx:
                return self.focus_home(telemetry, now, force=True)

        return CameraDecision("held", "The current camera shot remains active.")

    def ensure_live_edge(self, telemetry, now):
        if self.mode != "auto":
            return None

        checker = getattr(telemetry, "is_replay_at_live_edge", None)
        at_live_edge = checker() if checker else None
        if at_live_edge is True:
            self.live_edge_initialized = True
            return None

        needs_sync = at_live_edge is False or not self.live_edge_initialized
        if not needs_sync:
            return None
        if (
            self.last_live_sync_at is not None
            and now - self.last_live_sync_at < 2.0
        ):
            return None

        sync = getattr(telemetry, "return_to_live", None)
        if sync is None:
            self.live_edge_initialized = True
            return None

        self.last_live_sync_at = now
        if not sync():
            return CameraDecision("failed", "iRacing did not accept the return-to-live command.")

        self.live_edge_initialized = True
        return CameraDecision("live", "Replay view returned to the live edge.")

    def follow(self, item, telemetry):
        if self.mode == "off":
            return CameraDecision("ignored", "Camera direction is off.")

        now = self.clock()
        if self.replay_active and not self.is_green_flag_item(item):
            return CameraDecision("held", "Incident replay controls the camera.")

        if self.is_green_flag_item(item):
            self.clear_sequence()
            self.return_home_at = None
            return self.focus_home(telemetry, now, force=True)

        sequence = self.build_sequence_steps(item)
        if sequence:
            self.return_home_at = None
            self.sequence = sequence
            self.sequence_index = 1
            self.sequence_interval = self.estimate_sequence_interval(item, sequence)
            self.next_sequence_at = now + self.sequence_interval
            car_idx, group_name, camera_number = sequence[0]
            return self.focus_car(
                car_idx,
                group_name,
                telemetry,
                now,
                role="lineup",
                force=True,
                camera_number=camera_number,
            )

        car_idx = getattr(item, "camera_target_car_idx", None)
        if car_idx is None:
            return CameraDecision("ignored", "The story has no camera target.")

        self.clear_sequence()
        force = (
            self.current_role in ("", "home")
            or getattr(item, "category", "") in ("incident", "caution_pit_summary")
        )
        decision = self.focus_car(
            car_idx,
            self.preferred_group,
            telemetry,
            now,
            role="story",
            force=force,
        )
        if decision.status in ("suggested", "switched") or (
            decision.status == "held" and car_idx == self.current_car_idx
        ):
            self.return_home_at = now + self.return_after_seconds
        return decision

    def begin_replay(self):
        self.replay_active = True
        self.return_home_at = None
        self.clear_sequence()

    def focus_replay(self, car_idx, group_name, telemetry):
        return self.focus_car(
            car_idx,
            group_name,
            telemetry,
            self.clock(),
            role="replay",
            force=True,
        )

    def focus_incident_replay(self, group_name, telemetry):
        now = self.clock()
        group = self.resolve_camera_group(telemetry.get_camera_groups(), group_name)
        if group is None:
            return CameraDecision(
                "failed",
                f"Camera group {group_name!r} was not found.",
            )
        group_number = self.safe_int(group.get("GroupNum"))
        resolved_name = str(group.get("GroupName") or group_name)
        if group_number is None:
            return CameraDecision(
                "failed",
                "The selected camera group has no valid number.",
                group_name=resolved_name,
            )

        status = "suggested"
        if self.mode == "auto":
            switch = getattr(telemetry, "switch_camera_to_incident", None)
            if switch is None or not switch(group_number, 0):
                return CameraDecision(
                    "failed",
                    "iRacing did not accept the incident camera command.",
                    group_number=group_number,
                    group_name=resolved_name,
                )
            status = "switched"

        self.current_car_idx = None
        self.current_group_number = group_number
        self.current_role = "replay"
        self.last_switch_at = now
        return CameraDecision(
            status,
            "Incident camera selected.",
            group_number=group_number,
            group_name=resolved_name,
        )

    def end_replay(self, telemetry):
        self.replay_active = False
        self.live_edge_initialized = True
        self.return_home_at = None
        self.clear_sequence()
        return self.focus_home(telemetry, self.clock(), force=True)

    def focus_home(self, telemetry, now, force=False):
        car_idx = self.get_leader_car_idx(telemetry)
        if car_idx is None:
            return CameraDecision(
                "failed",
                "The leader is unavailable for the home shot.",
            )
        return self.focus_car(
            car_idx,
            self.home_group,
            telemetry,
            now,
            role="home",
            force=force,
        )

    def focus_car(
        self,
        car_idx,
        group_name,
        telemetry,
        now,
        role,
        force=False,
        camera_number=0,
    ):
        if (
            not force
            and self.last_switch_at is not None
            and now - self.last_switch_at < self.minimum_hold_seconds
            and car_idx != self.current_car_idx
        ):
            return CameraDecision("held", "The minimum camera hold is still active.", car_idx=car_idx)

        driver = telemetry.get_driver_lookup().get(car_idx, {})
        car_number = str(driver.get("number", "") or "")
        if not car_number or car_number == "?":
            return CameraDecision("failed", "The target car number is unavailable.", car_idx=car_idx)

        group = self.resolve_camera_group(telemetry.get_camera_groups(), group_name)
        if group is None:
            return CameraDecision(
                "failed",
                f"Camera group {group_name!r} was not found.",
                car_idx=car_idx,
                car_number=car_number,
            )

        group_number = self.safe_int(group.get("GroupNum"))
        resolved_name = str(group.get("GroupName") or group_name)
        if group_number is None:
            return CameraDecision(
                "failed",
                "The selected camera group has no valid number.",
                car_idx=car_idx,
                car_number=car_number,
                group_name=resolved_name,
            )

        if car_idx == self.current_car_idx and group_number == self.current_group_number:
            self.current_role = role
            return CameraDecision(
                "held",
                "The requested shot is already active.",
                car_idx=car_idx,
                car_number=car_number,
                group_number=group_number,
                group_name=resolved_name,
            )

        status = "suggested"
        reason = "Observe-only camera target."
        if self.mode == "auto":
            switch = getattr(telemetry, "switch_camera_to_car", None)
            if switch is None or not switch(car_number, group_number, camera_number):
                return CameraDecision(
                    "failed",
                    "iRacing did not accept the camera command.",
                    car_idx=car_idx,
                    car_number=car_number,
                    group_number=group_number,
                    group_name=resolved_name,
                )
            status = "switched"
            reason = "Camera switched."

        self.current_car_idx = car_idx
        self.current_group_number = group_number
        self.current_role = role
        self.last_switch_at = now
        return CameraDecision(
            status,
            reason,
            car_idx=car_idx,
            car_number=car_number,
            group_number=group_number,
            group_name=resolved_name,
        )

    def get_leader_car_idx(self, telemetry):
        results = telemetry.get_results()
        if not results:
            grid_reader = getattr(telemetry, "get_starting_grid", None)
            results = grid_reader() if grid_reader else []
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        if not valid:
            return None
        leader = min(valid, key=lambda car: self.safe_int(car.get("Position"), 999))
        return leader.get("CarIdx")

    def clear_sequence(self):
        self.sequence = ()
        self.sequence_index = 0
        self.sequence_interval = 0.0
        self.next_sequence_at = None

    def build_sequence_steps(self, item):
        detailed_steps = tuple(getattr(item, "camera_sequence_steps", ()) or ())
        if detailed_steps:
            return tuple(
                self.normalize_sequence_step(step)
                for step in detailed_steps
                if self.normalize_sequence_step(step) is not None
            )

        return tuple(
            (car_idx, self.preferred_group, self.lineup_camera_number)
            for car_idx in tuple(getattr(item, "camera_sequence", ()) or ())
        )

    def normalize_sequence_step(self, step):
        if isinstance(step, dict):
            car_idx = step.get("car_idx")
            group_name = step.get("group_name", self.preferred_group)
            camera_number = step.get("camera_number", self.lineup_camera_number)
            return (car_idx, group_name, camera_number)

        if isinstance(step, (tuple, list)):
            if not step:
                return None
            car_idx = step[0]
            group_name = step[1] if len(step) > 1 else self.preferred_group
            camera_number = step[2] if len(step) > 2 else self.lineup_camera_number
            return (car_idx, group_name, camera_number)

        return (step, self.preferred_group, self.lineup_camera_number)

    def estimate_sequence_interval(self, item, sequence):
        words = len(str(getattr(item, "message", "")).split())
        speech_seconds = max(5.0, min(45.0, words / 2.45))
        return max(3.0, speech_seconds / max(len(sequence), 1))

    def resolve_camera_group(self, groups, group_name=None):
        wanted = str(group_name or self.preferred_group).casefold()
        exact = [
            group
            for group in groups or []
            if str(group.get("GroupName", "")).casefold() == wanted
        ]
        if exact:
            return exact[0]
        partial = [
            group
            for group in groups or []
            if wanted in str(group.get("GroupName", "")).casefold()
        ]
        if partial:
            return partial[0]

        aliases = {
            "focus crashes": ("crash", "incident", "accident", "tv1"),
            "far chase": ("far chase", "rear chase", "chase", "tv1"),
            "rear chase": ("rear chase", "far chase", "chase", "tv1"),
            "cockpit": ("cockpit", "in car", "driver", "tv1"),
            "chopper": ("chopper", "blimp", "aerial", "gyro", "tv3", "tv1"),
            "tv mixed": ("tv mixed", "tv3", "tv 3", "tv1"),
            "tv3": ("tv3", "tv 3", "tv1"),
            "tv2": ("tv2", "tv 2", "tv1"),
        }
        for alias in aliases.get(wanted, ()):
            for group in groups or []:
                name = str(group.get("GroupName", "")).casefold()
                if alias in name:
                    return group

        return None

    @staticmethod
    def is_green_flag_item(item):
        return str(getattr(item, "dedupe_key", "")).startswith("race_control:green")

    @staticmethod
    def is_race_session(telemetry):
        reader = getattr(telemetry, "get_session_type", None)
        if reader is None:
            return True
        return "race" in str(reader()).lower()

    @staticmethod
    def safe_int(value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
