# Live overlay timing

The leaderboard cycles every eight seconds between `TO LEADER` (estimated gap
to the leader) and `TO NEXT` (estimated interval to the car immediately ahead
in the displayed standings). One larger timing value is shown per driver, and
each leaderboard style labels the active mode.
Driver cards always show both `To Leader` and `To Next` together, independently
of this cycle. Featuring a driver initializes its live telemetry immediately
so repeated race calls do not briefly reset RPM and gear to zero.
During practice and qualifying these are signed on-track relatives to the
best-lap ranking; they are not differences between the drivers' best lap times.
Best lap times remain available in the driver data and driver card.

The calculation reads live lap-distance percentages every overlay update.
Track progress is unwrapped across start/finish without waiting for the scored
completed-lap count to update. For a trailing car, recent position history
provides the time when the leading car passed its current location. Linear
interpolation between samples estimates that crossing time. Before sufficient
history exists, the calculation projects track separation using a recent lap
time, or SDK estimated time when available. These values are estimates, not
official timing-line measurements.

The conceptual research reference was SIMRacingApps' public
[Session.getDiffCars and getDiffCarsRelative implementation](https://github.com/SIMRacingApps/SIMRacingAppsServer/blob/master/src/com/SIMRacingApps/Session.java).
Our implementation is independently written; no SIMRacingApps source is bundled.

Race gaps preserve whole-lap separation. Missing, invalid, pit-road, and
off-world telemetry is suppressed, and existing scored timing remains a
fallback. History resets on session changes, backwards replay seeks, and large
position discontinuities. The intervals follow overall displayed position,
not a separate class-relative order.

Live broadcasts use an independent telemetry worker at approximately 10 Hz.
The browser also polls at 10 Hz, so commentary generation does not pause the
overlay. Recorded telemetry retains its existing playback scheduling.

Verification covers continuously changing values with unchanged scored times,
separate gap/interval values, interpolated crossings, start/finish wrapping,
lap deficits, missing data, pit road, session resets, and worker shutdown.
An actual iRacing/Racelab comparison is still required to assess accuracy in a
live session; an MP4 alone cannot provide the raw telemetry needed for that.
