=== RGC League Manager ===
Contributors: realisticgamingcrew
Tags: sim racing, league, standings, results, schedule
Requires at least: 6.2
Requires PHP: 7.4
Stable tag: 0.3.0
License: GPLv2 or later

Publishes RGC AI Broadcast Studio league schedules, race results, standings, and driver statistics.

== Installation ==
1. Upload the rgc-league-manager folder or its ZIP through Plugins > Add New > Upload Plugin.
2. Activate RGC League Manager.
3. Open Tools > RGC League Manager for the REST endpoint and connection instructions.
4. Add [rgc_league_manager league="your-league-slug"] to a page.

== Security ==
The sync endpoint requires a logged-in WordPress account with manage_options permission. Use a dedicated account, a WordPress Application Password, and HTTPS. Never place the password in a public page or JavaScript.

== Changelog ==
= 0.3.0 =
* Stores post-race manual point adjustments and review reasons.

= 0.2.1 =
* Forces a full-page breakout when WordPress themes constrain shortcode width.

= 0.2.0 =
* Adds wide full-page layouts without horizontal table scrolling.
* Adds richer schedules and race-result statistics including laps led.

= 0.1.0 =
* Initial schedule, results, standings, drivers, REST sync, and shortcode release.
