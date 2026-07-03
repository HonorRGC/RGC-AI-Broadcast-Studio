from dataclasses import dataclass
import time


@dataclass(frozen=True)
class ReplayDecision:
    status: str
    reason: str
    car_idx: int | None = None
    angle_group: str = ""
    angle_number: int = 0
    total_angles: int = 0


class ReplayDirector:
    MODES = ("off", "observe", "auto")

    def __init__(
        self,
        mode="off",
        angle_groups=("TV1", "TV2"),
        pre_roll_seconds=5.0,
        angle_seconds=8.0,
        clock=None,
    ):
        if mode not in self.MODES:
            raise ValueError(f"Unknown replay mode: {mode}")
        self.mode = mode
        self.angle_groups = tuple(angle_groups) or ("TV1",)
        self.pre_roll_seconds = float(pre_roll_seconds)
        self.angle_seconds = float(angle_seconds)
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        self.active = False
        self.car_idx = None
        self.session_num = 0
        self.replay_start_time = 0.0
        self.active_groups = ()
        self.angle_index = 0
        self.angle_started_at = None
        self.camera_engaged = False
        self.played_story_ids = set()

    def handle_item(self, item, telemetry, camera_director):
        if self.is_live_interrupt(item):
            if self.active:
                return self.finish(telemetry, camera_director, interrupted=True)
            return ReplayDecision("ignored", "No replay is active.")

        if self.mode == "off" or getattr(item, "category", "") != "incident":
            return ReplayDecision("ignored", "This item does not request a replay.")

        story_id = str(getattr(item, "dedupe_key", "") or "")
        if self.active or story_id in self.played_story_ids:
            return ReplayDecision("ignored", "The incident replay is already handled.")

        session_time = getattr(item, "replay_session_time", None)
        session_num = getattr(item, "replay_session_num", None)
        car_idx = getattr(item, "camera_target_car_idx", None)
        if session_time is None or session_num is None or car_idx is None:
            return ReplayDecision("ignored", "The incident has no replay marker.")

        groups = (
            self.angle_groups
            if getattr(item, "replay_multi_angle", False)
            else self.angle_groups[:1]
        )
        self.car_idx = car_idx
        self.session_num = int(session_num)
        self.replay_start_time = max(0.0, float(session_time) - self.pre_roll_seconds)
        self.active_groups = groups
        self.angle_index = 0

        if not self.seek_to_incident(telemetry):
            return ReplayDecision(
                "failed",
                "iRacing did not accept the incident replay seek.",
            )

        if self.mode == "auto":
            camera_director.begin_replay()
            self.camera_engaged = True
            camera_decision = camera_director.focus_replay(
                self.car_idx,
                self.active_groups[0],
                telemetry,
            )
            if camera_decision.status == "failed":
                self.restore_live_after_failure(telemetry, camera_director)
                return ReplayDecision("failed", camera_decision.reason)

        self.active = True
        self.angle_started_at = self.clock()
        self.played_story_ids.add(story_id)
        return ReplayDecision(
            "started",
            "Incident replay started.",
            car_idx=self.car_idx,
            angle_group=self.active_groups[0],
            angle_number=1,
            total_angles=len(self.active_groups),
        )

    def update(self, telemetry, camera_director):
        if not self.active:
            return ReplayDecision("ignored", "No replay is active.")

        if self.telemetry_requires_live_return(telemetry):
            return self.finish(telemetry, camera_director, interrupted=True)

        now = self.clock()
        if now - self.angle_started_at < self.angle_seconds:
            return ReplayDecision("held", "The current replay angle is still playing.")

        next_index = self.angle_index + 1
        if next_index >= len(self.active_groups):
            return self.finish(telemetry, camera_director)

        self.angle_index = next_index
        if not self.seek_to_incident(telemetry):
            return self.finish(telemetry, camera_director, failed=True)

        group_name = self.active_groups[self.angle_index]
        if self.mode == "auto":
            camera_decision = camera_director.focus_replay(
                self.car_idx,
                group_name,
                telemetry,
            )
            if camera_decision.status == "failed":
                return self.finish(telemetry, camera_director, failed=True)

        self.angle_started_at = now
        return ReplayDecision(
            "angle",
            "Replay switched to the next angle.",
            car_idx=self.car_idx,
            angle_group=group_name,
            angle_number=self.angle_index + 1,
            total_angles=len(self.active_groups),
        )

    def finish(self, telemetry, camera_director, interrupted=False, failed=False):
        returned = self.mode == "observe" or telemetry.return_to_live()
        if self.camera_engaged:
            camera_director.end_replay(telemetry)
            self.camera_engaged = False
        self.active = False
        self.angle_started_at = None

        if failed or not returned:
            return ReplayDecision(
                "failed",
                "Replay ended, but return-to-live needs another attempt.",
            )
        if interrupted:
            return ReplayDecision("live", "Replay interrupted by live race control.")
        return ReplayDecision("live", "Incident replay completed and returned live.")

    def seek_to_incident(self, telemetry):
        if self.mode == "observe":
            return True
        return telemetry.seek_replay_session_time(
            self.session_num,
            self.replay_start_time,
        )

    def restore_live_after_failure(self, telemetry, camera_director):
        if self.mode == "auto":
            telemetry.return_to_live()
        if self.camera_engaged:
            camera_director.end_replay(telemetry)
            self.camera_engaged = False

    @staticmethod
    def is_live_interrupt(item):
        key = str(getattr(item, "dedupe_key", "") or "")
        return key.startswith("race_control:green") or key == "race_control:checkered"

    def telemetry_requires_live_return(self, telemetry):
        state_reader = getattr(telemetry, "get_session_state", None)
        session_state = state_reader() if state_reader else 0
        if session_state in (5, 6):
            return True

        flags_reader = getattr(telemetry, "get_session_flags", None)
        session_flags = flags_reader() if flags_reader else 0
        if int(session_flags or 0) & 0x00000001:
            return True
        return len(self.active_groups) > 1 and bool(
            int(session_flags or 0) & 0x00000004
        )
