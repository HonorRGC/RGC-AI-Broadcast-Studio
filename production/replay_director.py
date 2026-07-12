from dataclasses import dataclass
from pathlib import Path
import time

from config import CAUTION_REPLAY_AUDIO


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
        angle_groups=("Far Chase",),
        pre_roll_seconds=15.0,
        incident_marker_pre_roll_frames=1500,
        angle_seconds=12.0,
        replay_audio_path=CAUTION_REPLAY_AUDIO,
        audio_player=None,
        clock=None,
    ):
        if mode not in self.MODES:
            raise ValueError(f"Unknown replay mode: {mode}")
        self.mode = mode
        self.angle_groups = tuple(angle_groups) or ("TV1",)
        self.pre_roll_seconds = float(pre_roll_seconds)
        self.incident_marker_pre_roll_frames = int(incident_marker_pre_roll_frames)
        self.angle_seconds = float(angle_seconds)
        self.replay_audio_path = str(replay_audio_path or "").strip()
        self.audio_player = audio_player
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        self.active = False
        self.car_idx = None
        self.session_num = 0
        self.replay_session_time = 0.0
        self.replay_start_time = 0.0
        self.active_groups = ()
        self.angle_index = 0
        self.angle_started_at = None
        self.camera_engaged = False
        self.use_incident_marker = False
        self.marker_pre_roll_override_frames = None
        self.audio_played_for_story_ids = set()
        self.played_story_ids = set()

    def handle_item(self, item, telemetry, camera_director):
        if self.is_live_interrupt(item):
            self.stop_replay_audio()
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
        use_incident_marker = bool(getattr(item, "replay_use_incident_marker", False))
        if (
            not use_incident_marker
            and (session_time is None or session_num is None or car_idx is None)
        ):
            return ReplayDecision("ignored", "The incident has no replay marker.")

        groups = (
            self.angle_groups
            if getattr(item, "replay_multi_angle", False)
            else self.angle_groups[:1]
        )
        self.car_idx = car_idx
        self.session_num = int(session_num or 0)
        self.replay_session_time = float(session_time or 0.0)
        self.replay_start_time = self.current_replay_start_time()
        self.use_incident_marker = use_incident_marker
        self.marker_pre_roll_override_frames = getattr(
            item,
            "replay_marker_pre_roll_frames",
            None,
        )
        self.active_groups = groups
        self.angle_index = 0

        if not self.seek_to_incident(telemetry):
            return ReplayDecision(
                "failed",
                "iRacing did not accept the incident replay seek.",
            )
        if not self.replay_seek_is_valid(telemetry):
            return ReplayDecision(
                "failed",
                "Incident replay seek stayed at the live edge.",
            )

        if self.mode == "auto":
            camera_director.begin_replay()
            self.camera_engaged = True
            if self.use_incident_marker:
                camera_decision = camera_director.focus_incident_replay(
                    self.active_groups[0],
                    telemetry,
                )
            else:
                camera_decision = camera_director.focus_replay(
                    self.car_idx,
                    self.active_groups[0],
                    telemetry,
                )
            if camera_decision.status == "failed":
                self.restore_live_after_failure(telemetry, camera_director)
                return ReplayDecision("failed", camera_decision.reason)
            if self.use_incident_marker and not self.apply_incident_marker_preroll(
                telemetry
            ):
                self.restore_live_after_failure(telemetry, camera_director)
                return ReplayDecision(
                    "failed",
                    "iRacing did not accept the incident replay pre-roll.",
                )

        self.active = True
        self.angle_started_at = self.clock()
        self.played_story_ids.add(story_id)
        if getattr(item, "replay_multi_angle", False):
            self.play_replay_audio(story_id)
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
        if not self.replay_seek_is_valid(telemetry):
            return self.finish(telemetry, camera_director, failed=True)

        group_name = self.active_groups[self.angle_index]
        if self.mode == "auto":
            if self.use_incident_marker:
                camera_decision = camera_director.focus_incident_replay(
                    group_name,
                    telemetry,
                )
            else:
                camera_decision = camera_director.focus_replay(
                    self.car_idx,
                    group_name,
                    telemetry,
                )
            if camera_decision.status == "failed":
                return self.finish(telemetry, camera_director, failed=True)
            if self.use_incident_marker and not self.apply_incident_marker_preroll(
                telemetry
            ):
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
        returned = self.mode == "observe" or self.return_to_live_until_confirmed(
            telemetry
        )
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

    def return_to_live_until_confirmed(self, telemetry, max_attempts=3):
        return_live = getattr(telemetry, "return_to_live", None)
        if not return_live:
            return False

        sent_any = False
        for _ in range(max(1, int(max_attempts))):
            if not return_live():
                continue
            sent_any = True
            if self.live_return_is_confirmed(telemetry):
                return True

        return sent_any and self.live_return_status_unknown(telemetry)

    def seek_to_incident(self, telemetry):
        if self.mode == "observe":
            return True
        if getattr(self, "use_incident_marker", False):
            if self.angle_index > 0:
                return_live = getattr(telemetry, "return_to_live", None)
                if return_live:
                    return_live()
            marker_seeker = getattr(telemetry, "seek_previous_incident_marker", None)
            if marker_seeker:
                return bool(marker_seeker())
            seeker = getattr(telemetry, "seek_previous_incident", None)
            return bool(seeker and seeker(self.current_incident_marker_pre_roll_frames()))
        return telemetry.seek_replay_session_time(
            self.session_num,
            self.current_replay_start_time(),
        )

    def apply_incident_marker_preroll(self, telemetry):
        rewinder = getattr(telemetry, "rewind_replay_frames", None)
        if not rewinder:
            return True
        return bool(rewinder(self.current_incident_marker_pre_roll_frames()))

    def replay_seek_is_valid(self, telemetry):
        if self.mode != "auto":
            return True
        checker = getattr(telemetry, "is_replay_at_live_edge", None)
        if not checker:
            return True
        at_live_edge = checker()
        if at_live_edge is None:
            return True
        return at_live_edge is False

    def live_return_is_confirmed(self, telemetry):
        if self.mode != "auto":
            return True
        checker = getattr(telemetry, "is_replay_at_live_edge", None)
        if not checker:
            return True
        at_live_edge = checker()
        if at_live_edge is None:
            return True
        return at_live_edge is True

    def live_return_status_unknown(self, telemetry):
        checker = getattr(telemetry, "is_replay_at_live_edge", None)
        if not checker:
            return True
        return checker() is None

    def play_replay_audio(self, story_id):
        if (
            not self.replay_audio_path
            or not self.audio_player
            or story_id in self.audio_played_for_story_ids
        ):
            return
        path = Path(self.replay_audio_path).expanduser()
        if not path.exists():
            return
        try:
            if hasattr(self.audio_player, "play"):
                self.audio_player.play(str(path.resolve()))
            else:
                self.audio_player(str(path.resolve()))
            self.audio_played_for_story_ids.add(story_id)
        except Exception:
            return

    def stop_replay_audio(self):
        stopper = getattr(self.audio_player, "stop", None)
        if not stopper:
            return
        try:
            stopper()
        except Exception:
            return

    def current_replay_start_time(self):
        if getattr(self, "use_incident_marker", False):
            return 0.0
        return max(0.0, self.replay_session_time - self.current_pre_roll_seconds())

    def current_pre_roll_seconds(self):
        return self.pre_roll_seconds

    def current_incident_marker_pre_roll_frames(self):
        if self.marker_pre_roll_override_frames:
            return int(self.marker_pre_roll_override_frames)
        return self.incident_marker_pre_roll_frames

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
        return False
