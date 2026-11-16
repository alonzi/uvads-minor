"""Parse NON_DS_PLANS into one row per (student, plan) and map plans to disciplines/fields."""
import re

import pandas as pd

# Spelling variants in SIS plan names -> one discipline name
ALIASES = {
    "Behavioral Neurosci": "Behavioral Neuroscience",
    "Government-Foreign Affair": "Government-Foreign Affairs",
    "Mathematics-Grad Prep": "Mathematics-Graduate Prep",
    "Studio Art": "Art-Studio Art",
}
NOT_A_MAJOR = {"Echols Scholar"}  # a program flag, not a field of study

FIELDS = {
    "Computing": ["Computer Science", "Computer Engineering"],
    "Engineering (non-computing)": ["Systems Engineering", "Biomedical Engineering",
                                    "Chemical Engineering", "Electrical Engineering",
                                    "Mechanical Engineering", "Aerospace Engineering",
                                    "Materials Science and Eng"],
    "Business & Economics": ["Commerce", "Economics"],
    "Math & Statistics": ["Applied Statistics", "Statistics", "Mathematics",
                          "Mathematics-Financial", "Mathematics-Graduate Prep",
                          "Mathematics-Prob&Stats"],
    "Physical & Environmental Sci": ["Physics", "Astronomy-Physics", "Chemistry",
                                     "Chemistry-Biochemistry", "Environmental Sciences"],
    "Life & Behavioral Sci": ["Biology", "Human Biology", "Neuroscience",
                              "Behavioral Neuroscience", "Cognitive Science", "Psychology",
                              "Kinesiology"],
    "Social Sci & Policy": ["Global Studies", "Foreign Affairs", "Government",
                            "Government-Foreign Affairs", "Sociology", "Anthropology",
                            "Political&Soc Tht", "Urban & Environ Planning", "Media Studies",
                            "Linguistics", "Interdisciplinary", "Environ Tht & Pract"],
    "Humanities & Arts": ["History", "French", "English", "Spanish", "Music", "Art-Studio Art",
                          "Art History", "Drama", "Religious Studies", "Japanese Lang & Lit",
                          "Architecture"],
}
DISC_TO_FIELD = {d: f for f, ds in FIELDS.items() for d in ds}


def discipline(plan: str) -> str:
    d = re.sub(r"\s*\(.*\)$", "", plan).replace("INTER-", "").strip()
    return ALIASES.get(d, d)


def plan_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (student index, plan). Columns: plan, discipline, is_minor, field."""
    p = df["NON_DS_PLANS"].str.split(r",\s*(?=[A-Z])").explode().str.strip()
    t = pd.DataFrame({"sid": p.index, "plan": p.values})
    t["is_minor"] = t["plan"].str.contains(r"\(Minor\)")
    t["discipline"] = t["plan"].map(discipline)
    t["field"] = t["discipline"].map(DISC_TO_FIELD)
    t.loc[t["is_minor"], "field"] = None
    t = t[~t["discipline"].isin(NOT_A_MAJOR) | t["is_minor"]]
    return t


def majors(df: pd.DataFrame) -> pd.DataFrame:
    """Unique (student, discipline) for majors only; BA/BS/2nd-major collapsed."""
    t = plan_table(df)
    t = t[~t["is_minor"]].drop_duplicates(["sid", "discipline"])
    unmapped = set(t.loc[t["field"].isna(), "discipline"])
    if unmapped:
        raise ValueError(f"Unmapped disciplines: {sorted(unmapped)}")
    return t
