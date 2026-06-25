from broadcaster.events import RaceEvent
from broadcaster.driver_manager import DriverManager
from broadcaster.story_engine import StoryEngine


class RaceBrain:
    def __init__(self):
        self.driver_manager = DriverManager()
        self.story_engine = StoryEngine()

    def driver_name(self, car_idx):
        if car_idx == 0:
            return "TJ Lee"
        return f"AI Driver {car_idx}"

    def analyze(self, results):
        events = []

        for car in results:
            car_idx = car.get("CarIdx")
            position = car.get("Position")

            if car_idx is None or position is None:
                continue

            driver = self.driver_manager.get_driver(car_idx)

            driver.name = self.driver_name(car_idx)
            driver.previous_position = driver.current_position
            driver.current_position = position

            if driver.starting_position == 0:
                driver.starting_position = position

            driver.highest_position = min(driver.highest_position, position)

            if driver.lowest_position == 0:
                driver.lowest_position = position
            else:
                driver.lowest_position = max(driver.lowest_position, position)

            driver.laps_completed = car.get("LapsComplete", 0)
            driver.fastest_lap = car.get("FastestTime", 9999.0)
            driver.last_lap = car.get("LastTime", 0.0)
            driver.incidents = car.get("Incidents", 0)

            self.story_engine.update_story(driver)

            if driver.previous_position != 0 and position < driver.previous_position:
                driver.passes_made += driver.previous_position - position

                event = RaceEvent(
                    event_type="PASS",
                    driver_name=driver.name,
                    old_position=driver.previous_position,
                    new_position=position,
                    importance=self.calculate_importance(driver.previous_position, position),
                    message=(
                        f"{driver.name} moved from P{driver.previous_position} "
                        f"to P{position}. "
                        f"Started P{driver.starting_position}. "
                        f"{driver.story}."
                    )
                )

                events.append(event)

            elif driver.previous_position != 0 and position > driver.previous_position:
                driver.passes_lost += position - driver.previous_position

        return events

    def calculate_importance(self, old_position, new_position):
        if new_position == 1:
            return 10
        if new_position <= 5:
            return 8
        if new_position <= 10:
            return 6
        return 4