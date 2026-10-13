"""Monday bot settings: which services exist and how each one is run."""

# Services that can be toggled on and off
MONDAY_TOGGLE_SERVICES: dict[str, tuple[str, str]] = {
    "mcqueen": ("McQueen", "Live Alerts for new SG Computing Internship Listings"),
    "hermione": (
        "Hermione",
        "Automatic Daily NUS Canvas Digest: Upcoming Classes and Deadlines",
    ),
}

# Services run on request rather than toggled, so they have no user_services row.
MONDAY_LONG_RUNNING_SERVICES: dict[str, tuple[str, str]] = {
    "walle": (
        "Wall-E",
        "Pick a Canvas Course and instantly get all of its files in one zip",
    ),
}

# Services that need the user's Canvas key before they can be enabled.
CANVAS_DEPENDENT_SERVICES = {"hermione", "walle"}
