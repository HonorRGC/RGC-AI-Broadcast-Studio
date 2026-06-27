from broadcaster.telemetry import IRacingTelemetry
from broadcaster.profile_manager import ProfileManager


telemetry = IRacingTelemetry()
profiles = ProfileManager()

if telemetry.startup():
    driver_lookup = telemetry.get_driver_lookup()
    profiles.load_profiles(driver_lookup)

    print("Driver Profiles")
    print("=" * 60)

    for car_idx, profile in profiles.profiles.items():
        print(
            f"CarIdx {car_idx} | "
            f"#{profile.car_number} | "
            f"{profile.name} | "
            f"{profile.car} | "
            f"iRating {profile.irating} | "
            f"{profile.license} | "
            f"{profile.country}"
        )
else:
    print("Not connected to iRacing.")