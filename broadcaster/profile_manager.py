from broadcaster.driver_profile import DriverProfile


class ProfileManager:
    def __init__(self):
        self.profiles = {}

    def load_profiles(self, driver_lookup):
        for car_idx, info in driver_lookup.items():
            profile = DriverProfile()

            profile.name = info.get("name", "")
            profile.car_number = info.get("number", "")
            profile.team = info.get("team", "")
            profile.car = info.get("car", "")
            profile.irating = info.get("irating", 0)
            profile.license = info.get("license", "")
            profile.club = info.get("club", "")
            profile.division = info.get("division", "")
            profile.country = info.get("country", "")

            self.profiles[car_idx] = profile

    def get_profile(self, car_idx):
        return self.profiles.get(car_idx)