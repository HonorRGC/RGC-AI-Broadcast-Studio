"""Race-scoped, producer-selected caution camera targets shared by replay workflows."""
import hashlib
import json
from pathlib import Path


class CautionAssignments:
    def __init__(self, job, root=None):
        root = Path(root or Path(__file__).resolve().parents[1])
        self.identity = {key: job.get(key) for key in ("track", "session_num", "subsession_id")}
        if not self.identity["subsession_id"]:
            self.identity["capture"] = str(Path(job["source"]).resolve())
        key = hashlib.sha256(json.dumps(self.identity, sort_keys=True).encode()).hexdigest()[:24]
        self.path = root / "recordings" / "caution-plans" / (key + ".json")
        self.cautions = list(job.get("cautions", []))
        self.drivers = list(job.get("drivers", []))
        self.assignments = {}
        self.message = "Choose a review driver for each caution. Automatic detection is used when blank."
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("identity") == self.identity and isinstance(data.get("assignments"), dict):
                    self.assignments = data["assignments"]
            except (OSError, ValueError, TypeError):
                self.message = "Saved choices could not be read. Automatic detection is active; select drivers to save new choices."

    def applies_to_source(self, source):
        if getattr(source, "recorded_broadcast", False):
            return True
        weekend = getattr(source, "get_weekend_info", lambda: {})() or {}
        return (str(weekend.get("SimMode", "")).lower() == "replay" and
                bool(self.identity["subsession_id"]) and
                str(weekend.get("SubSessionID")) == str(self.identity["subsession_id"]))

    def assign(self, caution_id, car_idx):
        caution_id = str(caution_id)
        if caution_id not in {c["id"] for c in self.cautions}:
            raise ValueError("Unknown caution for this race.")
        if car_idx in (None, ""):
            self.assignments.pop(caution_id, None)
        else:
            idx = int(car_idx)
            if idx not in {int(d["car_idx"]) for d in self.drivers}:
                raise ValueError("Choose a driver from this race.")
            self.assignments[caution_id] = idx
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"identity": self.identity, "assignments": self.assignments,
                                    "cautions": self.cautions, "drivers": self.drivers}, indent=2), encoding="utf-8")
        temp.replace(self.path)
        self.message = "Saved. Camera choices apply immediately; prepare highlights again to update prepared commentary."

    def target(self, caution_id):
        idx = self.assignments.get(str(caution_id))
        return idx if idx in {d["car_idx"] for d in self.drivers} else None

    def for_time(self, session_num, at):
        if int(session_num) != int(self.identity["session_num"]):
            return None
        matches = [c for c in self.cautions if abs(float(c["time"]) - float(at)) <= 3]
        if not matches:
            return None
        caution = min(matches, key=lambda c: abs(c["time"] - at))
        idx = self.target(caution["id"])
        return (caution, idx) if idx is not None else None

    def state(self):
        return {"cautions": self.cautions, "drivers": self.drivers,
                "assignments": dict(self.assignments), "message": self.message}


def handle_assignment(server, command, payload):
    if command != "caution_driver_assign":
        return False
    plan = getattr(server, "caution_assignments", None)
    if plan:
        try:
            plan.assign(payload.get("caution_id"), payload.get("car_idx"))
        except (ValueError, TypeError, OSError) as error:
            plan.message = str(error)
    return True


def attach_replay_plan(source, server):
    """Attach full-capture plans or an existing saved plan for a native replay."""
    if not server:
        return
    from production.highlights import build_plan
    if getattr(source, "snapshots", None) and getattr(source, "path", None):
        job = build_plan(source.snapshots, source.path)
        server.caution_assignments = CautionAssignments(job)
        source.caution_assignments = server.caution_assignments
        return
    weekend = getattr(source, "get_weekend_info", lambda: {})() or {}
    # Explicit saved replay mode only: live spectating must retain automatic detection.
    if str(weekend.get("SimMode", "")).lower() != "replay" or not weekend.get("SubSessionID"):
        return
    folder = Path(__file__).resolve().parents[1] / "recordings" / "caution-plans"
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        identity = data.get("identity", {})
        if str(identity.get("subsession_id")) != str(weekend["SubSessionID"]):
            continue
        job = dict(identity, source="", cautions=data.get("cautions", []), drivers=data.get("drivers", []))
        server.caution_assignments = CautionAssignments(job)
        source.caution_assignments = server.caution_assignments
        return
