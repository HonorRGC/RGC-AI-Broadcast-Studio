# Changelog

## Unreleased

## Version 1.0.1 - Early Access Build Refresh

### Added
- Flo-style leaderboard track label and improved green/yellow race-state presentation
- Road-course and multiclass readiness hooks for v1.0 testing
- More league context in race storytelling, including standings and track-history prompts when imported data is available

### Changed
- Tightened green-flag pit-cycle detection so one early retirement or isolated stop does not put the broadcast into pit-cycle mode
- Improved live battle wording so uncertain side-by-side or three-wide moments are described more carefully
- Reduced repetitive draft-track and long-green-run phrasing
- Refreshed overlay sponsor placement, driver-card details, and Producer Assist polish for early access testers

### Fixed
- Corrected several position-normalization issues that could affect driver cards, biggest movers, and mid-race rundown overlays
- Avoided stale pass prompts leaking internal guidance into spoken commentary
- Rebuilt the Windows installer as a v1.0.1 early-access refresh

## Version 1.0.0 - First Public Release Candidate

### Added
- v1.0 readiness checklist for final release smoke testing and packaging
- Release documentation now points testers toward the Windows Setup.exe path first
- Cleaner race-control debug probe output with short duplicate-event cooldowns
- Studio launcher, Producer Assist, overlay graphics, camera controls, replay controls, sponsor reads, music beds, Sim Racer Hub imports, race recaps, and Windows installer packaging

### Changed
- Refreshed project-state notes to match the current Studio, overlay, camera, replay, music, Producer Assist, race-control, and league-profile features
- Clarified the role of the tester ZIP versus the Windows installer for outside admins
- Versioned the app as 1.0.0 for the first release candidate build

## Version 0.18.2 - Producer Assist Release Candidate

### Added
- First-time setup checklist in the Studio help tab for release/admin readiness
- Prompt guidance for more natural Mike, Jeff, and Sarah booth handoffs
- Long-green booth conversations for more natural race storytelling
- Driver overlay card position, starting position, and position-change display
- Producer Assist pit road / strategy panel with last stop, pit lane time, stop time, tire age, position gain, and service guess
- Producer Assist manual camera handoff that disables auto-camera when moving to a driver or back to the leader

### Fixed
- Prevented AI commentary from calling out broadcaster names or using script-style booth labels
- Voice timing now uses actual generated ElevenLabs MP3 duration when available, reducing cut-off broadcaster calls
- Soft incident calls are more conservative to reduce false trouble reports

## Version 0.18.1 - Tester Installer Refresh

### Added
- Windows Setup.exe build for tester/admin installs
- Multiple RGC Anthem audio files during qualifying
- Clear MP3/WAV guidance for hidden Windows audio playback

### Fixed
- Top-ten reset gap wording now uses the gap to the car directly ahead
- Unsupported OGA/OGG anthem files are reported instead of failing silently
- Selected black flag and meatball flag calls can be detected without calling every black flag

### Added
- Progressive pre-race welcome, track, weather, and complete starting-field segments
- Support for grid positions reported as either zero- or one-based values
- Regression coverage based on the first live iRacing test
- Practice, Qualifying, Warmup, and Race session detection
- Safe startup voice diagnostics and a standalone `--voice-test`

### Fixed
- Initial green flag being described as a restart
- Opening package being skipped when connecting at one-to-green
- Zero-second gaps being announced as active battles
- Closing-stage calls firing immediately in short races
- Commentary starting before the Race session at multi-session league events
- Session data being read from the wrong iRacing session index

## Version 0.18 - Platform Foundation

### Added
- One orchestration engine shared by live and replay telemetry
- JSONL replay reader and telemetry adapter
- Automated race-control, scheduler, incident, replay, and session tests
- Dependency metadata and environment template
- Architecture and development documentation

### Changed
- Routed pass, pit, and intelligence stories through one editorial path
- Allowed OpenAI rendering for every assigned booth role
- Added queue expiration, deduplication, and race-control preemption
- Reset all production state between sessions
- Corrected one-to-green flag priority and lap-based green-run counting

### Removed
- Generated audio and compiled bytecode
- Duplicate race director, prompt, story, commentary, profile, and queue implementations
- Empty placeholders and unused legacy modules

## Version 0.7 - Voice Integration

### Added
- ElevenLabs integration
- Voice Manager foundation
- Lead announcer voice support
- Automatic audio playback
- Configurable voice IDs
- First AI-generated spoken commentary

## Version 0.6 - AI Commentary
Released: June 2026

### Added
- OpenAI GPT-5.5 integration
- Prompt Builder system
- OpenAI client
- Configuration file (.env support)
- AI and Template commentary modes
- Feature flag for enabling/disabling AI

---

## Version 0.5 - Broadcast Booth
Released: June 2026

### Added
- Broadcast Booth module
- Commentator module
- Modular commentary pipeline
- Randomized commentary templates
- Broadcast output formatting
- Separated commentary generation from race logic

---

## Version 0.4 - Broadcast Pipeline
Released: June 2026

### Added
- Event Queue
- Producer system
- Event prioritization
- Commentary Generator
- Modular broadcast architecture
- Event filtering based on importance

---

## Version 0.3 - Race Brain
Released: June 2026

### Added
- Race Brain
- Driver Manager
- Driver database
- Story Engine
- Driver statistics tracking
- Pass detection
- Driver momentum foundation

---

## Version 0.2 - Green Flag
Released: June 2026

### Added
- Live iRacing telemetry
- Running order tracking
- Driver identification
- Session detection
- Live race monitoring

---

## Version 0.1 - Ignition
Released: June 2026

### Added
- Initial project structure
- Python environment
- GitHub repository
- VS Code project
- First successful connection to iRacing
