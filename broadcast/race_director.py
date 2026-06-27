from broadcast.director_phase import DirectorPhase
from broadcast.director_task import DirectorTask


class RaceDirector:
    def __init__(self):
        self.phase = DirectorPhase.PRE_RACE
        self.last_phase = DirectorPhase.PRE_RACE
        self.tasks = []
        self.race_has_started = False
        self.initialized = False
        self.last_total_laps_completed = 0

    def update(self, race_status, results=None):
        if results is None:
            results = []

        previous_phase = self.phase
        new_phase = self.determine_phase(race_status, results)

        if not self.initialized:
            self.phase = new_phase
            self.last_phase = new_phase
            self.initialized = True
            self.race_has_started = self.phase in [
                DirectorPhase.GREEN_FLAG,
                DirectorPhase.CAUTION,
                DirectorPhase.ONE_TO_GREEN,
            ]
            self.tasks = []
            print(f"\nRace Director synced to phase -> {self.describe_phase()}")
            return

        self.last_phase = previous_phase
        self.phase = new_phase

        if self.phase in [
            DirectorPhase.GREEN_FLAG,
            DirectorPhase.CAUTION,
            DirectorPhase.ONE_TO_GREEN,
        ]:
            self.race_has_started = True

        if self.phase_changed():
            self.build_tasks_for_phase()

    def determine_phase(self, race_status, results):
        total_laps_completed = self.total_laps_completed(results)
        laps_are_increasing = total_laps_completed > self.last_total_laps_completed

        self.last_total_laps_completed = max(
            self.last_total_laps_completed,
            total_laps_completed
        )

        if race_status.is_caution:
            return DirectorPhase.CAUTION

        if race_status.is_green:
            return DirectorPhase.GREEN_FLAG

        if laps_are_increasing:
            return DirectorPhase.GREEN_FLAG

        if not self.race_has_started and total_laps_completed > 0:
            return DirectorPhase.GREEN_FLAG

        if self.race_has_started:
            return self.phase

        return DirectorPhase.FORMATION

    def total_laps_completed(self, results):
        total = 0

        for car in results:
            total += car.get("LapsComplete", 0)

        return total

    def phase_changed(self):
        return self.phase != self.last_phase

    def build_tasks_for_phase(self):
        self.tasks = []

        if self.phase == DirectorPhase.CAUTION:
            self.tasks.append(DirectorTask("Announce yellow flag", priority=10))
            self.tasks.append(DirectorTask("Hold normal pass calls", priority=9))
            self.tasks.append(DirectorTask("Prepare caution coverage", priority=8))

        elif self.phase == DirectorPhase.GREEN_FLAG:
            self.tasks.append(DirectorTask("Announce green flag", priority=10))
            self.tasks.append(DirectorTask("Resume normal race coverage", priority=8))

        elif self.phase == DirectorPhase.ONE_TO_GREEN:
            self.tasks.append(DirectorTask("Prepare restart coverage", priority=8))
            self.tasks.append(DirectorTask("Field rundown before green", priority=7))

        elif self.phase == DirectorPhase.FORMATION:
            self.tasks.append(DirectorTask("Prepare pre-race coverage", priority=6))
            self.tasks.append(DirectorTask("Introduce starting grid", priority=7))

    def get_next_task(self):
        for task in self.tasks:
            if not task.completed:
                task.completed = True
                return task

        return None

    def should_allow_pass_calls(self):
        return self.phase == DirectorPhase.GREEN_FLAG

    def should_hold_pass_calls(self):
        return self.phase in [
            DirectorPhase.CAUTION,
            DirectorPhase.ONE_TO_GREEN,
            DirectorPhase.FORMATION,
        ]

    def describe_phase(self):
        return self.phase.value