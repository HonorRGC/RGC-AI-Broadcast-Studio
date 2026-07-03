from broadcaster.events import RaceEvent
from broadcaster.driver_manager import DriverManager
from helpers.position_formatter import PositionFormatter


class RaceBrain:
    def __init__(self):
        self.driver_manager = DriverManager()

    def driver_name(self, car_idx):
        if car_idx == 0:
            return "TJ Lee"
        return f"AI Driver {car_idx}"

    def analyze(self, results, driver_lookup=None):
        events = []

        if driver_lookup is None:
            driver_lookup = {}

        if not results:
            return events

        zero_based_positions = self.results_are_zero_based(results)

        for car in results:
            car_idx = car.get("CarIdx")
            raw_position = car.get("Position")

            if car_idx is None or raw_position is None:
                continue

            position = self.display_position(raw_position, zero_based_positions)

            driver = self.driver_manager.get_driver(car_idx)
            driver_info = driver_lookup.get(car_idx, {})

            driver.name = driver_info.get("name", self.driver_name(car_idx))
            driver.number = driver_info.get("number", "?")

            driver.previous_position = driver.current_position
            driver.current_position = position

            if driver.starting_position == 0:
                driver.starting_position = position

            driver.highest_position = min(driver.highest_position, position)

            if driver.lowest_position == 0:
                driver.lowest_position = position
            else:
                driver.lowest_position = max(driver.lowest_position, position)

            driver.laps_completed = car.get("LapsComplete", car.get("Lap", 0))
            driver.fastest_lap = car.get("FastestTime", 9999.0)
            driver.last_lap = car.get("LastTime", 0.0)
            driver.incidents = car.get("Incidents", 0)

            if driver.previous_position != 0 and position < driver.previous_position:
                positions_gained = driver.previous_position - position
                driver.passes_made += positions_gained

                event = RaceEvent(
                    event_type="PASS",
                    driver_name=driver.name,
                    car_idx=car_idx,
                    car_number=driver.number,
                    old_position=driver.previous_position,
                    new_position=position,
                    starting_position=driver.starting_position,
                    positions_gained_from_start=driver.starting_position - position,
                    passes_made=driver.passes_made,
                    passes_lost=driver.passes_lost,
                    story=self.build_pass_story(driver, positions_gained),
                    lap=driver.laps_completed,
                    importance=self.calculate_importance(
                        driver.previous_position,
                        position,
                        positions_gained,
                    ),
                    message=self.build_pass_story(driver, positions_gained),
                )

                events.append(event)

            elif driver.previous_position != 0 and position > driver.previous_position:
                driver.passes_lost += position - driver.previous_position

        return events

    def seed_starting_positions(self, results, driver_lookup=None):
        driver_lookup = driver_lookup or {}
        zero_based_positions = self.results_are_zero_based(results or [])
        for car in results or []:
            car_idx = car.get("CarIdx")
            raw_position = car.get("Position")
            if car_idx is None or raw_position is None:
                continue
            position = self.display_position(raw_position, zero_based_positions)
            driver = self.driver_manager.get_driver(car_idx)
            driver_info = driver_lookup.get(car_idx, {})
            driver.name = driver_info.get("name", self.driver_name(car_idx))
            driver.number = driver_info.get("number", "?")
            if driver.starting_position == 0:
                driver.starting_position = position
                driver.current_position = position
                driver.previous_position = position

    def results_are_zero_based(self, results):
        positions = []

        for car in results:
            position = car.get("Position")
            if position is not None:
                positions.append(position)

        return 0 in positions

    def display_position(self, raw_position, zero_based_positions):
        try:
            position = int(raw_position)
        except Exception:
            return raw_position

        if zero_based_positions:
            return position + 1

        return position

    def build_pass_story(self, driver, positions_gained):
        starting_position = PositionFormatter.ordinal(driver.starting_position)
        previous_position = PositionFormatter.ordinal(driver.previous_position)
        current_position = PositionFormatter.ordinal(driver.current_position)
        net_change_wording = self.net_position_wording(driver)

        if driver.current_position == 1:
            return (
                f"{driver.name} has taken the race lead after starting "
                f"{starting_position}."
            )

        if driver.current_position <= 5:
            return (
                f"{driver.name} has moved into the top five. "
                f"The {driver.number} started {starting_position} and is now running "
                f"{current_position}, {net_change_wording}."
            )

        if driver.current_position <= 10:
            return (
                f"{driver.name} has gained a spot inside the top ten. "
                f"The {driver.number} moves from {previous_position} to "
                f"{current_position} after starting {starting_position}, "
                f"{net_change_wording}."
            )

        return (
            f"{driver.name} gains {self.position_count(positions_gained)}, moving "
            f"from {previous_position} to {current_position}. The {driver.number} "
            f"started {starting_position} and is {net_change_wording}."
        )

    def net_position_wording(self, driver):
        net_gain = driver.starting_position - driver.current_position
        if net_gain > 0:
            return f"a net gain of {self.position_count(net_gain)}"
        if net_gain == 0:
            return "back in the position where it started"
        return f"{self.position_count(abs(net_gain))} behind its starting spot"

    def position_count(self, count):
        try:
            count = int(count)
        except (TypeError, ValueError):
            return f"{count} positions"
        if count == 1:
            return "one position"
        return f"{count} positions"

    def calculate_importance(self, old_position, new_position, positions_gained=1):
        if new_position == 1:
            return 10

        if new_position <= 5:
            return 8

        if new_position <= 10:
            return 6

        if positions_gained >= 3:
            return 5

        return 4
