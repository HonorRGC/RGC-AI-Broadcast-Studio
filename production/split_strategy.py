class SplitStrategyReporter:
    """Compare observed green stops across a wide window, without guessing fuel."""

    def __init__(self):
        self.announced = set()
        self.last_lap = 0

    def update(self, states, current_lap, total_laps, under_caution=False):
        if current_lap < self.last_lap:
            self.announced.clear()
        self.last_lap = current_lap
        if total_laps <= 0 or current_lap < total_laps * .4:
            return ""
        green_stops = [state for state in states if state.last_pit_lap >= total_laps * .35 and state.green_flag_pit_stop_count > 0 and not state.last_pit_under_caution and not state.on_pit_road and float(getattr(state, "last_pit_stop_seconds", 0) or 0) < 25]
        if not green_stops:
            return ""
        early = min(green_stops, key=lambda state: state.last_pit_lap)
        late = max(green_stops, key=lambda state: state.last_pit_lap)
        spread = late.last_pit_lap - early.last_pit_lap
        remaining = max(0, total_laps - current_lap)
        if under_caution and spread >= 10 and remaining > 0:
            key = ("caution", early.last_pit_lap, late.last_pit_lap)
            message = f"The caution interrupts two different strategies: {early.driver_name} stopped on lap {early.last_pit_lap}, while {late.driver_name} waited until lap {late.last_pit_lap}. With {remaining} laps remaining, the later stoppers have less green-flag time left to turn any fresher-tire advantage into track position. Their eventual restart position and whether they pit again will matter."
        elif not under_caution and spread >= 10:
            key = ("split", early.last_pit_lap)
            message = f"The pit strategies are spread out: {early.driver_name} stopped on lap {early.last_pit_lap}, while {late.driver_name} extended the run to lap {late.last_pit_lap}. That is {spread} laps between their stops. The earlier stop had more laps to work; the later stop leaves a shorter run to the finish. Watch how their track position develops."
        elif not under_caution and total_laps * .4 <= early.last_pit_lap <= total_laps * .6 and any(state.last_pit_lap == 0 and not state.on_pit_road for state in states):
            key = ("midpoint",)
            message = f"{early.driver_name} has stopped near the halfway point, on lap {early.last_pit_lap}. Other drivers are extending their opening stint. Those are different approaches to dividing this race, and we will watch how the later stops change their track position."
        else:
            return ""
        if key in self.announced:
            return ""
        self.announced.add(key)
        return message
