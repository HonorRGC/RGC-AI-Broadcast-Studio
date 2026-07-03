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
        minimum_hold_seconds=8.0,
        clock=None,
    ):
        if mode not in self.MODES:
            raise ValueError(f"Unknown camera mode: {mode}")
        self.mode = mode
        self.preferred_group = str(preferred_group or "TV1")
        self.minimum_hold_seconds = float(minimum_hold_seconds)
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        self.current_car_idx = None
        self.last_switch_at = None

    def follow(self, item, telemetry):
        if self.mode == "off":
            return CameraDecision("ignored", "Camera direction is off.")

        car_idx = getattr(item, "camera_target_car_idx", None)
        if car_idx is None:
            return CameraDecision("ignored", "The story has no camera target.")

        if car_idx == self.current_car_idx:
            return CameraDecision("held", "The target car is already on camera.", car_idx=car_idx)

        now = self.clock()
        if (
            self.last_switch_at is not None
            and now - self.last_switch_at < self.minimum_hold_seconds
        ):
            return CameraDecision("held", "The minimum camera hold is still active.", car_idx=car_idx)

        driver_lookup = telemetry.get_driver_lookup()
        driver = driver_lookup.get(car_idx, {})
        car_number = str(driver.get("number", "") or "")
        if not car_number or car_number == "?":
            return CameraDecision("failed", "The target car number is unavailable.", car_idx=car_idx)

        group = self.resolve_camera_group(telemetry.get_camera_groups())
        if group is None:
            return CameraDecision(
                "failed",
                f"Camera group {self.preferred_group!r} was not found.",
                car_idx=car_idx,
                car_number=car_number,
            )

        group_number = self.safe_int(group.get("GroupNum"))
        group_name = str(group.get("GroupName") or self.preferred_group)
        if group_number is None:
            return CameraDecision(
                "failed",
                "The selected camera group has no valid number.",
                car_idx=car_idx,
                car_number=car_number,
                group_name=group_name,
            )

        if self.mode == "observe":
            return CameraDecision(
                "suggested",
                "Observe-only camera target.",
                car_idx=car_idx,
                car_number=car_number,
                group_number=group_number,
                group_name=group_name,
            )

        switch = getattr(telemetry, "switch_camera_to_car", None)
        if switch is None or not switch(car_number, group_number, 0):
            return CameraDecision(
                "failed",
                "iRacing did not accept the camera command.",
                car_idx=car_idx,
                car_number=car_number,
                group_number=group_number,
                group_name=group_name,
            )

        self.current_car_idx = car_idx
        self.last_switch_at = now
        return CameraDecision(
            "switched",
            "Camera switched.",
            car_idx=car_idx,
            car_number=car_number,
            group_number=group_number,
            group_name=group_name,
        )

    def resolve_camera_group(self, groups):
        wanted = self.preferred_group.casefold()
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
        return partial[0] if partial else None

    @staticmethod
    def safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
