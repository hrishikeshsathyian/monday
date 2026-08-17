from ats_scrapers.models import Job
import re


def default_is_singapore(j: Job) -> bool:
    _SINGAPORE_RE = re.compile(r"\b(singapore|sg|sgp)\b", re.IGNORECASE)
    return bool(j.location and _SINGAPORE_RE.search(j.location))


def default_is_intern(j: Job) -> bool:
    _INTERN_RE = re.compile(r"\b(intern(ship)?|summer|fall|winter)\b", re.IGNORECASE)
    return bool(j.employment_type and j.employment_type == "INTERN") or bool(
        j.title and _INTERN_RE.search(j.title)
    )


# --- tech classification ---------------------------------------------------

# Engineering disciplines that are never software/tech, even though their
# titles contain the bare word "engineer(ing)" that TECH_RE would otherwise
# catch. No trailing \b is used after "engineer" so this also matches
# "Engineering" / "Engineers" (e.g. a "Civil Engineering" department).
NON_TECH_ENGINEERING_RE = re.compile(
    r"""
    \b(
        civil | structural | geotechnical | traffic | transportation |
        mechanical | electrical | electronics | instrumentation |
        chemical | process | materials | metallurgical |
        industrial | manufacturing | production | quality | plant |
        aerospace | aeronautical | avionics | marine | naval | offshore |
        automotive | rail | mining | petroleum | piping |
        biomedical | environmental | agricultural | food |
        hvac | facilities | maintenance | field | service |
        sales | pre[-\s]?sales | fire | safety | acoustic 
    )\s+engineer
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "Architect" alone defaults to the building-design profession, not
# software — only count it as tech when it's qualified.
TECH_ARCHITECT_RE = re.compile(
    r"""
    \b(
        software | solutions? | cloud | data | security | network |
        systems? | enterprise | infrastructure | platform | application |
        integration | technical | devops | ai | ml
    )\s+architect\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "Data" alone shows up constantly in clerical/compliance titles that have
# nothing to do with engineering or analytics. Excluded before falling
# back to the broad \bdata\b match in TECH_RE.
NON_TECH_DATA_RE = re.compile(
    r"\bdata\s+(entry|clerk|privacy\s+officer|protection\s+officer)\b",
    re.IGNORECASE,
)

TECH_RE = re.compile(
    r"""
    \b(
        # --- generic role words (catch bare usage) ---
        software |
        developer(s)? |
        engineer(ing)?(s)? |                        # catches "Engineer", "Engineering", bare
        programmer |
        research(er)?\s+scientist | applied\s+scientist |
        algorithm(s)? |

        # --- stack / specialization ---
        swe |
        full[-\s]?stack | front[-\s]?end | back[-\s]?end |
        computer\s+(science|engineer(ing)?|vision) |
        embedded\s+(systems?|software) | firmware | \bfpga\b | \basic\b |

        # --- data / analytics (broad catch, minus clerical exclusions above) ---
        data\s+(scien(ce|tist)|engineer(ing)?|analy(st|tics)|architect|platform|pipeline) |
        \bdata\b |
        business\s+intelligence | \bbi\s+(developer|engineer|analyst)\b |
        analytics\s+engineer |

        # --- ML / AI ---
        machine\s+learning | \bml\b |
        artificial\s+intelligence | \bai\b |
        deep\s+learning | \bnlp\b | natural\s+language\s+processing |
        large\s+(language\s+)?model(s)? | \bllm\b |
        computer\s+vision | reinforcement\s+learning |
        knowledge\s+graph | prompt\s+engineer(ing)? |

        # --- infra / ops ---
        dev\s?ops | site\s+reliability | \bsre\b |
        cloud\s+engineer | infrastructure\s+engineer | platform\s+engineer |

        # --- security (qualified only — bare "security" also matches
        # security guards / physical security, which aren't tech) ---
        cyber\s?security | information\s+security | infosec |
        security\s+(engineer|analyst|architect|researcher|consultant|specialist|operations) |
        application\s+security | product\s+security | network\s+security |
        penetration\s+test(er|ing)? | \bpentest(er)?\b |
        red\s+team | blue\s+team | \bsoc\s+analyst\b |
        threat\s+intelligence | incident\s+response |
        vulnerability\s+(management|research) |

        # --- QA / test ---
        quality\s+assurance | \bqa\s+engineer\b | test\s+engineer | \bsdet\b |

        # --- mobile ---
        mobile\s+(developer|engineer) |
        \bios\b\s+(developer|engineer) |
        android\s+(developer|engineer) |

        # --- UX / product design ---
        \bux\b | \bui\b | user\s+experience | user\s+interface |
        interaction\s+design(er)? | product\s+designer |

        # --- product / program mgmt ---
        product\s+manag(er|ement) | associate\s+product\s+manager | \bapm\b |
        technical\s+program\s+manager | \btpm\b |

        # --- systems / IT ---
        information\s+technology | systems?\s+(engineer|development|administrator) |
        \bsysadmin\b | network\s+engineer |
        database\s+administrator | \bdba\b |
        help\s?desk | service\s+desk | desktop\s+support | technical\s+support |

        # --- emerging / misc tech ---
        blockchain | web3 | smart\s+contract | robotics |
        augmented\s+reality | virtual\s+reality |

        # --- generic fallback ---
        technology
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Bare 1-3 letter acronyms are only trustworthy in their conventional
# uppercase form — lowercased, they collide with ordinary English words
# ("it", "ai") that show up in unrelated title text. Deliberately NOT
# case-insensitive.
TECH_ACRONYM_RE = re.compile(r"\b(IT|AI|ML)\b")


def default_is_tech(j: Job) -> bool:
    haystack = " ".join(filter(None, [j.title, j.department]))

    if NON_TECH_ENGINEERING_RE.search(haystack):
        return False
    if NON_TECH_DATA_RE.search(haystack):
        return False

    return bool(
        TECH_RE.search(haystack)
        or TECH_ARCHITECT_RE.search(haystack)
        or TECH_ACRONYM_RE.search(haystack)
    )


# --- grad vs. senior classification -----------------------------------------

# Titles that look senior at a glance but are conventionally entry/grad-level
# (e.g. "Associate Product Manager", "Assistant Manager", "Management
# Associate"/"Management Trainee" schemes). Checked first so these are never
# flagged as senior.
GRAD_FRIENDLY_TITLE_RE = re.compile(
    r"""
    \b(associate|assistant)\s+(\w+\s+){0,2}manager\b |
    \bmanagement\s+(associate|trainee)\b |
    \bmanager\s+trainee\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

SENIOR_TITLE_RE = re.compile(
    r"""
    \b(
        senior | sr\.? |
        staff\s+(\w+\s+){0,2}(engineer|scientist|developer|architect|analyst|designer) |
        principal | distinguished | chief |
        lead |
        director | head\s+of | department\s+head |
        vice\s+president | \bvp\b | \bsvp\b | \bevp\b |
        \bcto\b | \bciso\b | \bcio\b | \bcpo\b |
        president |
        group\s+(product\s+)?manager |
        manager | \bmgr\b |
        supervisor
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def default_is_senior(j: Job) -> bool:
    """True for postings that read as experienced/managerial rather than
    grad-appropriate — used to keep senior roles out of the non-intern
    "grad" bucket. Checks years-of-experience when the ATS exposes it,
    otherwise falls back to title keywords.
    """
    if j.experience is not None and j.experience >= 3:
        return True

    if not j.title:
        return False
    if GRAD_FRIENDLY_TITLE_RE.search(j.title):
        return False
    return bool(SENIOR_TITLE_RE.search(j.title))
