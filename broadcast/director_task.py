from dataclasses import dataclass


@dataclass
class DirectorTask:

    name: str

    completed: bool = False

    priority: int = 5