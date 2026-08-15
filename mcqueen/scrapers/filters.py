from ats_scrapers.models import Job
import re


def default_is_singapore(j: Job) -> bool:
    _SINGAPORE_RE = re.compile(r"\b(singapore|sg|sgp)\b", re.IGNORECASE)
    return bool(j.location and _SINGAPORE_RE.search(j.location))


def default_is_intern(j: Job) -> bool:
    _INTERN_RE = re.compile(r"\b(intern|summer|fall|winter)\b", re.IGNORECASE)
    return bool(j.employment_type and j.employment_type == "INTERN") or bool(
        j.title and _INTERN_RE.search(j.title)
    )


NON_TECH_ENGINEERING_RE = re.compile(
    r"\b(civil|mechanical|electrical|chemical|structural|industrial|"
    r"aerospace|biomedical|environmental|process)\s+engineer",
    re.IGNORECASE,
)


TECH_RE = re.compile(
    r"""
    \b(
        # --- generic role words (catch bare usage) ---
        software |
        developer(s)? | development |
        engineer(ing)?(s)? |                        # catches "Engineer", "Engineering", bare
        programmer |
        research(er)?\s+scientist | applied\s+scientist |
        algorithm(s)? |
        architect |

        # --- stack / specialization ---
        swe |
        full[-\s]?stack | front[-\s]?end | back[-\s]?end |
        computer\s+science | computer\s+engineer(ing)? |

        # --- data (broad catch, per your request) ---
        \bdata\b |
        data\s+(scien(ce|tist)|engineer(ing)?|analy(st|tics)) |

        # --- ML / AI ---
        machine\s+learning | \bml\b |
        artificial\s+intelligence | \bai\b |
        deep\s+learning | \bnlp\b |
        large\s+(language\s+)?model(s)? | \bllm\b |
        knowledge\s+graph |

        # --- infra / ops ---
        dev\s?ops | site\s+reliability | \bsre\b |
        cloud\s+engineer | infrastructure\s+engineer | platform\s+engineer |

        # --- security ---
        cyber\s?security | \bsecurity\b |           
        information\s+security | infosec |

        # --- QA / test ---
        quality\s+assurance | \bqa\s+engineer\b | test\s+engineer | \bsdet\b |

        # --- mobile ---
        mobile\s+(developer|engineer) |
        \bios\b\s+(developer|engineer) |
        android\s+(developer|engineer) |

        # --- product / program mgmt ---
        product\s+manag(er|ement) | associate\s+product\s+manager | \bapm\b |
        technical\s+program\s+manager | \btpm\b |

        # --- systems / IT ---
        information\s+technology | systems?\s+(engineer|development) |
        network\s+engineer |
        database\s+administrator | \bdba\b |

        # --- generic fallback ---
        technology |
        product\s+designer |
        IT | 
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def default_is_tech(j: Job) -> bool:
    haystack = " ".join(filter(None, [j.title, j.department]))
    if NON_TECH_ENGINEERING_RE.search(haystack):
        return False
    return bool(TECH_RE.search(haystack))
