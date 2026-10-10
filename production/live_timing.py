"""Continuous timing from live track position, independent of scored gaps.

When available, measure when the leading car passed the trailing car's current
location. Until that history exists, project the separation using a lap time.
These are live estimates, not official timing-line results.
"""

import math
from collections import deque


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


class LiveTimingTracker:
    def __init__(self):
        self.samples = {}
        self.last_time = None
        self.session = None

    def update(self, *, now, session, results, positions, estimated_times=None,
               race=True, surfaces=None, pit_road=None, completed_laps=None):
        now = number(now)
        if now is None:
            self.samples.clear()
            self.last_time = None
            return {}
        if session != self.session or (self.last_time is not None and now < self.last_time):
            self.samples.clear()
        self.session = session
        self.last_time = now
        cars = {}
        for car in results:
            idx = car.get("CarIdx")
            pct = number(positions.get(idx))
            if (pct is None or not 0 <= pct < 1
                    or (surfaces or {}).get(idx) == -1
                    or (pit_road or {}).get(idx) or car.get("OnPitRoad")):
                self.samples.pop(idx, None)
                continue
            history = self.samples.setdefault(idx, deque(maxlen=2400))
            laps = number(car.get("LapsComplete", car.get("Lap", 0))) or 0
            live_laps = number((completed_laps or {}).get(idx))
            if live_laps is not None and live_laps >= 0:
                laps = live_laps
            else:
                live_laps = None
            progress = laps + pct
            if history:
                t, previous = history[-1]
                delta = pct - previous % 1
                if delta < -0.5:
                    delta += 1
                if now - t > 5 or delta < -0.02 or delta > 0.5:
                    history.clear()  # tow, teleport, or missing telemetry
                elif live_laps is None:
                    progress = previous + max(delta, 0)
                if history and (progress < previous - .02 or progress > previous + .5):
                    history.clear()
            if not history or now > history[-1][0]:
                history.append((now, progress))
            while history and now - history[0][0] > 180:
                history.popleft()
            period = next((v for key in ("LastTime", "FastestTime", "BestTime")
                           if (v := number(car.get(key))) is not None and 5 < v < 1000), None)
            if period is None and pct > 0.1:
                estimate = number((estimated_times or {}).get(idx))
                projected = estimate / pct if estimate is not None else 0
                if 5 < projected < 1000:
                    period = projected
            cars[idx] = (progress, period)
        for idx in set(self.samples) - set(cars):
            del self.samples[idx]
        output = {}
        ordered = [car["CarIdx"] for car in sorted(results, key=lambda c: c.get("Position", 999))]
        if not ordered:
            return output
        leader = ordered[0]
        for offset, idx in enumerate(ordered):
            if idx not in cars:
                continue
            output[idx] = {
                "gap": self.between(leader, idx, cars, now, race),
                "interval": self.between(ordered[offset - 1], idx, cars, now, race) if offset else 0.0,
            }
        return output

    def between(self, front, behind, cars, now, race):
        if front == behind:
            return 0.0
        if front not in cars or behind not in cars:
            return None
        front_progress, front_period = cars[front]
        behind_progress, behind_period = cars[behind]
        distance = front_progress - behind_progress
        if race and distance >= 1:
            return f"-{int(distance)} lap" + ("s" if int(distance) != 1 else "")
        if not race:
            distance = (distance + 0.5) % 1 - 0.5
        if race and distance < -0.02:
            return None  # scoring order has not caught up with an overtake
        distance = max(distance, 0) if race else distance
        target = front_progress - distance
        history = self.samples[front]
        if distance >= 0:
            for (t0, p0), (t1, p1) in zip(history, list(history)[1:]):
                if p0 <= target <= p1 and p1 > p0:
                    crossed = t0 + (target - p0) / (p1 - p0) * (t1 - t0)
                    return max(0, now - crossed)
        period = front_period or behind_period
        return distance * period if period else None
