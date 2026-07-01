from dataclasses import dataclass, field
from enum import Enum
import time


class AssignmentStatus(Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class AssignmentTarget(Enum):
    LEAD = "lead"
    JEFF = "jeff"
    SARAH = "sarah"
    OPENAI = "openai"
    CAMERA = "camera"


@dataclass
class Assignment:

    id: str

    target: AssignmentTarget

    headline: str
    summary: str

    priority: int = 5

    created: float = field(default_factory=time.time)

    expires_after: float = 30.0

    status: AssignmentStatus = AssignmentStatus.NEW


class AssignmentEngine:

    def __init__(self):

        self.assignments = {}

    def submit(
        self,
        assignment_id,
        target,
        headline,
        summary,
        priority=5,
        expires_after=30,
    ):

        if assignment_id in self.assignments:
            return

        self.assignments[assignment_id] = Assignment(
            id=assignment_id,
            target=target,
            headline=headline,
            summary=summary,
            priority=priority,
            expires_after=expires_after,
        )

    def next_assignment(self, target):

        self.cleanup()

        candidates = []

        for assignment in self.assignments.values():

            if assignment.status != AssignmentStatus.NEW:
                continue

            if assignment.target != target:
                continue

            candidates.append(assignment)

        if not candidates:
            return None

        candidates.sort(
            key=lambda a: (
                -a.priority,
                a.created,
            )
        )

        assignment = candidates[0]

        assignment.status = AssignmentStatus.ASSIGNED

        return assignment

    def complete(self, assignment):

        assignment.status = AssignmentStatus.COMPLETED

    def cleanup(self):

        now = time.time()

        remove = []

        for key, assignment in self.assignments.items():

            if assignment.status == AssignmentStatus.COMPLETED:
                remove.append(key)
                continue

            if now - assignment.created > assignment.expires_after:
                assignment.status = AssignmentStatus.EXPIRED
                remove.append(key)

        for key in remove:
            del self.assignments[key]

    def pending_count(self):

        return len(
            [
                a
                for a in self.assignments.values()
                if a.status == AssignmentStatus.NEW
            ]
        )

    def debug(self):

        print()

        print("=" * 60)
        print("ASSIGNMENT ENGINE")
        print("=" * 60)

        for assignment in sorted(
            self.assignments.values(),
            key=lambda x: -x.priority,
        ):

            print(
                f"{assignment.target.value.upper():8} "
                f"{assignment.priority:2} "
                f"{assignment.status.value:10} "
                f"{assignment.headline}"
            )