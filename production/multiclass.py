from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassPosition:
    car_idx: int
    class_id: str
    class_name: str
    class_position: int
    class_size: int
    overall_position: int


@dataclass(frozen=True)
class ClassStanding:
    class_id: str
    class_name: str
    size: int
    leader_car_idx: int | None = None
    leader_name: str = ""
    leader_number: str = ""
    leader_overall_position: int = 0


@dataclass(frozen=True)
class MulticlassContext:
    active: bool = False
    classes: tuple[ClassStanding, ...] = ()
    positions: dict[int, ClassPosition] = field(default_factory=dict)

    def to_prompt_lines(self):
        if not self.active:
            return []
        lines = [
            "Multiclass Race: YES",
            (
                "Multiclass Rule: distinguish overall position from in-class "
                "position. A pass may be more important in class than overall."
            ),
        ]
        for standing in self.classes[:6]:
            leader = ""
            if standing.leader_name:
                leader = (
                    f"; leader #{standing.leader_number} {standing.leader_name} "
                    f"overall P{standing.leader_overall_position}"
                )
            lines.append(
                f"- {standing.class_name}: {standing.size} cars{leader}"
            )
        return lines


def build_multiclass_context(results, driver_lookup):
    valid_results = [
        dict(car)
        for car in results or []
        if car.get("CarIdx") is not None
    ]
    if not valid_results:
        return MulticlassContext()

    ordered = sorted(
        valid_results,
        key=lambda car: normalized_position(car, valid_results) or 999,
    )
    grouped = {}
    order = []
    for car in ordered:
        car_idx = car.get("CarIdx")
        driver = (driver_lookup or {}).get(car_idx, {})
        class_id = class_identifier(driver)
        if not class_id:
            continue
        class_name = class_display_name(driver, class_id)
        if class_id not in grouped:
            grouped[class_id] = {
                "class_id": class_id,
                "class_name": class_name,
                "cars": [],
            }
            order.append(class_id)
        grouped[class_id]["cars"].append(car)

    if len(grouped) <= 1:
        return MulticlassContext()

    positions = {}
    standings = []
    for class_id in order:
        group = grouped[class_id]
        cars = group["cars"]
        class_size = len(cars)
        leader = cars[0] if cars else {}
        leader_idx = leader.get("CarIdx")
        leader_driver = (driver_lookup or {}).get(leader_idx, {})
        class_name = group["class_name"]
        for index, car in enumerate(cars, start=1):
            car_idx = car.get("CarIdx")
            positions[car_idx] = ClassPosition(
                car_idx=car_idx,
                class_id=class_id,
                class_name=class_name,
                class_position=explicit_class_position(car) or index,
                class_size=class_size,
                overall_position=normalized_position(car, valid_results),
            )
        standings.append(
            ClassStanding(
                class_id=class_id,
                class_name=class_name,
                size=class_size,
                leader_car_idx=leader_idx,
                leader_name=str(leader_driver.get("name") or f"Car {leader_idx}"),
                leader_number=str(leader_driver.get("number") or "?"),
                leader_overall_position=normalized_position(leader, valid_results),
            )
        )

    return MulticlassContext(active=True, classes=tuple(standings), positions=positions)


def class_identifier(driver):
    for key in (
        "car_class_id",
        "CarClassID",
        "class_id",
        "ClassID",
        "car_class_name",
        "car_class_short_name",
        "class_name",
    ):
        value = str((driver or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def class_display_name(driver, class_id=""):
    for key in (
        "car_class_short_name",
        "car_class_name",
        "CarClassShortName",
        "CarClassName",
        "class_name",
        "ClassName",
        "car_screen_name_short",
        "car_screen_name",
    ):
        value = str((driver or {}).get(key) or "").strip()
        if value:
            return value
    return f"Class {class_id}" if class_id else ""


def explicit_class_position(car):
    for key in (
        "ClassPosition",
        "ClassPos",
        "CarClassPosition",
        "ClassRank",
    ):
        value = safe_int((car or {}).get(key), 0)
        if value > 0:
            return value
    return 0


def normalized_position(car, results):
    zero_based = any(safe_int(row.get("Position"), 999) == 0 for row in results or [])
    raw_position = safe_int((car or {}).get("Position"), 0)
    return raw_position + 1 if zero_based and raw_position >= 0 else raw_position


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
