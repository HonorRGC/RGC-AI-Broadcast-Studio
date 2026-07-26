TRUE_PACK_DRAFT_TRACKS = (
    "daytona",
    "talladega",
    "dega",
    "atlanta",
    "echopark",
    "echo park",
)

LONG_STRAIGHT_DRAFT_ASSIST_TRACKS = (
    "indianapolis",
    "indy",
    "pocono",
)

SHORT_TRACKS = (
    "martinsville",
    "bristol",
    "richmond",
    "wilkesboro",
    "iowa",
)

ROAD_COURSE_MARKERS = (
    "road",
    "road course",
    "circuit",
    "grand prix",
    "glen",
    "sonoma",
    "spa",
    "mosport",
    "virginia",
    "watkins",
    "roval",
    "sebring",
    "silverstone",
    "monza",
    "imola",
    "suzuka",
    "interlagos",
    "mount panorama",
    "bathurst",
    "laguna",
    "lime rock",
    "mid-ohio",
    "mid ohio",
    "barber",
    "zandvoort",
    "zolder",
    "le mans",
    "nurburgring",
    "nürburgring",
)


def track_text(track_info):
    track_info = track_info or {}
    return " ".join(
        str(track_info.get(key, "") or "").lower()
        for key in (
            "track_name",
            "track_display_name",
            "track_config",
            "track_type",
            "category",
        )
    )


def is_true_pack_drafting_track(track_info):
    text = track_text(track_info)
    return any(name in text for name in TRUE_PACK_DRAFT_TRACKS)


def is_long_straight_draft_assist_track(track_info):
    text = track_text(track_info)
    return any(name in text for name in LONG_STRAIGHT_DRAFT_ASSIST_TRACKS)


def is_short_track(track_info):
    text = track_text(track_info)
    return any(name in text for name in SHORT_TRACKS)


def is_road_course(track_info):
    text = track_text(track_info)
    return any(name in text for name in ROAD_COURSE_MARKERS)


def racecraft_profile(track_info):
    if is_true_pack_drafting_track(track_info):
        return {
            "style": "pack_draft",
            "label": "pack drafting track",
            "notes": (
                "Drafting, pack momentum, lane timing, and freight-train risk "
                "are appropriate themes here."
            ),
        }
    if is_long_straight_draft_assist_track(track_info):
        return {
            "style": "long_straight_draft_assist",
            "label": "long-straight track",
            "notes": (
                "The draft can help on long straights, but avoid Daytona-style "
                "pack or freight-train language. Emphasize braking, corner exit, "
                "clean air, and runs down the straightaways."
            ),
        }
    if is_short_track(track_info):
        return {
            "style": "short_track",
            "label": "short track",
            "notes": (
                "Emphasize track position, patience, brake heat, tire heat, "
                "traffic, and keeping the nose clean."
            ),
        }
    if is_road_course(track_info):
        return {
            "style": "road_course",
            "label": "road course",
            "notes": (
                "Emphasize rhythm, braking zones, corner exits, curbs, traffic, "
                "off-track moments, undercut/overcut strategy, and tire "
                "management. Do not use oval pack-drafting or freight-train "
                "language."
            ),
        }
    return {
        "style": "standard_oval",
        "label": "standard oval",
        "notes": (
            "Emphasize clean air, corner entry and exit, tire falloff, traffic, "
            "and handling balance. Avoid freight-train language."
        ),
    }
