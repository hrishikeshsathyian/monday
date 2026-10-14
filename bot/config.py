"""Monday bot settings: which services exist and how each one is run."""

# Services that can be toggled on and off
MONDAY_TOGGLE_SERVICES: dict[str, tuple[str, str]] = {
    "mcqueen": ("McQueen", "Live Alerts for New SG Computing Internships"),
    "hermione": (
        "Hermione",
        "Automatic Daily NUS Class Schedule & Assignment Reminders",
    ),
}

# Services run on request rather than toggled, so they have no user_services row.
MONDAY_LONG_RUNNING_SERVICES: dict[str, tuple[str, str]] = {
    "walle": (
        "Wall-E",
        "One Tap NUS Canvas Course Files Downloader",
    ),
}

# Services that need the user's Canvas key before they can be enabled.
CANVAS_DEPENDENT_SERVICES = {"hermione", "walle"}
