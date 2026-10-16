"""Small canonical skill registry shared by matching and source mappings."""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    aliases: tuple[str, ...]
    github_topics: tuple[str, ...] = ()
    stack_exchange_tags: tuple[str, ...] = ()
    category: str | None = None
    ambiguous: bool = False


_DEFINITIONS = (
    SkillDefinition("ai", "AI", ("artificial intelligence",), category="AI & Data"),
    SkillDefinition("angular", "Angular", ("angular.js", "angularjs", "angular 2+", "angular framework"), ("angular",), ("angular", "angularjs"), "Frontend"),
    SkillDefinition("aws", "AWS", ("amazon web services",), ("aws",), ("amazon-web-services",), "Cloud & Infrastructure"),
    SkillDefinition("aws_lambda", "AWS Lambda", ("lambda", "amazon lambda"), ("aws-lambda",), ("aws-lambda",), "Cloud & Infrastructure"),
    SkillDefinition("azure", "Azure", ("microsoft azure",), ("azure",), ("azure",), "Cloud & Infrastructure"),
    SkillDefinition("azure_functions", "Azure Functions", ("azure function",), ("azure-functions",), ("azure-functions",), "Cloud & Infrastructure"),
    SkillDefinition("c_plus_plus", "C++", ("cpp", "c plus plus", "c-plus-plus"), ("cpp",), ("c++",), "Programming"),
    SkillDefinition("c_sharp", "C#", ("c sharp", "csharp", "c#", "c-sharp"), ("csharp",), ("c#",), "Programming"),
    SkillDefinition("c", "C", ("c language", "c programming"), ("c",), ("c",), "Programming", True),
    SkillDefinition("cloud_computing", "Cloud Computing", ("cloud",), category="Cloud & Infrastructure"),
    SkillDefinition("cybersecurity", "Cybersecurity", ("cyber security", "information security"), category="Security"),
    SkillDefinition("data_analytics", "Data Analytics", ("data analysis",), category="Data"),
    SkillDefinition("data_engineering", "Data Engineering", (), category="Data"),
    SkillDefinition("data_science", "Data Science", (), category="Data"),
    SkillDefinition("django", "Django", (), ("django",), ("django",), "Backend"),
    SkillDefinition("docker", "Docker", (), ("docker",), ("docker",), "Cloud & Infrastructure"),
    SkillDefinition("express_js", "Express.js", ("express", "expressjs", "express js"), ("express",), ("express",), "Backend"),
    SkillDefinition("fastapi", "FastAPI", (), ("fastapi",), ("fastapi",), "Backend"),
    SkillDefinition("generative_ai", "Generative AI", ("gen ai", "genai"), category="AI & Data"),
    SkillDefinition("git", "Git", (), ("git",), ("git",), "Developer Tools"),
    SkillDefinition("github", "GitHub", (), ("github",), ("github",), "Developer Tools"),
    SkillDefinition("go", "Go", ("golang", "go language", "go programming", "go programming language"), ("go", "golang"), ("go",), "Programming", True),
    SkillDefinition("google_cloud", "Google Cloud", ("google cloud platform", "gcp"), ("google-cloud", "gcp"), ("google-cloud-platform",), "Cloud & Infrastructure"),
    SkillDefinition("html", "HTML", (), ("html",), ("html",), "Frontend"),
    SkillDefinition("java", "Java", (), ("java",), ("java",), "Programming"),
    SkillDefinition("javascript", "JavaScript", ("java script", "js"), ("javascript",), ("javascript",), "Programming"),
    SkillDefinition("kubernetes", "Kubernetes", ("k8s",), ("kubernetes",), ("kubernetes",), "Cloud & Infrastructure"),
    SkillDefinition("machine_learning", "Machine Learning", ("ml",), ("machine-learning",), ("machine-learning",), "AI & Data"),
    SkillDefinition("mongodb", "MongoDB", ("mongo db", "mongo"), ("mongodb",), ("mongodb",), "Database"),
    SkillDefinition("mongodb_atlas", "MongoDB Atlas", ("mongo atlas",), ("mongodb-atlas",), ("mongodb-atlas",), "Database"),
    SkillDefinition("node_js", "Node.js", ("nodejs", "node js", "node.js", "node"), ("nodejs",), ("node.js",), "Backend"),
    SkillDefinition("numpy", "NumPy", (), ("numpy",), ("numpy",), "AI & Data"),
    SkillDefinition("pandas", "Pandas", (), ("pandas",), ("pandas",), "Data"),
    SkillDefinition("postgresql", "PostgreSQL", ("postgres",), ("postgresql",), ("postgresql",), "Database"),
    SkillDefinition("pytorch", "PyTorch", (), ("pytorch",), ("pytorch",), "AI & Data"),
    SkillDefinition("python", "Python", ("python 3", "python3"), ("python",), ("python",), "Programming"),
    SkillDefinition("r", "R", ("r language", "r programming", "r programming language", "rstats", "rstudio"), ("rstats", "r-language"), ("r", "rstats"), "Programming", True),
    SkillDefinition("react", "React", ("react.js", "reactjs"), ("react",), ("reactjs",), "Frontend"),
    SkillDefinition("react_native", "React Native", ("react-native",), ("react-native",), ("react-native",), "Frontend"),
    SkillDefinition("redis", "Redis", (), ("redis",), ("redis",), "Database"),
    SkillDefinition("spring_framework", "Spring", ("spring framework", "java spring", "spring boot", "springboot"), ("spring", "spring-boot"), ("spring", "spring-boot"), "Backend", True),
    SkillDefinition("sql", "SQL", ("structured query language",), ("sql",), ("sql",), "Database"),
    SkillDefinition("sql_server", "SQL Server", ("microsoft sql server", "ms sql server", "mssql"), ("sql-server", "mssql"), ("sql-server",), "Database"),
    SkillDefinition("terraform", "Terraform", (), ("terraform",), ("terraform",), "Cloud & Infrastructure"),
    SkillDefinition("typescript", "TypeScript", ("type script", "ts"), ("typescript",), ("typescript",), "Programming"),
    SkillDefinition("ui_ux", "UI/UX", ("uiux", "ui-ux", "ui ux", "user interface", "user experience", "ux design", "ui design", "product design"), ("ui", "ux", "ui-ux"), ("ui", "ux"), "Design & Frontend"),
    SkillDefinition("vue_js", "Vue.js", ("vuejs", "vue.js", "vue"), ("vuejs",), ("vue.js",), "Frontend"),
)

SKILLS: tuple[SkillDefinition, ...] = _DEFINITIONS
BY_ID = {item.skill_id: item for item in SKILLS}
BY_NAME = {item.name.casefold(): item for item in SKILLS}
_ALIASES = {
    alias.casefold(): item
    for item in SKILLS
    for alias in (item.name, *item.aliases)
}


@dataclass(frozen=True)
class NormalizedSkill:
    canonical_skill_id: str | None
    canonical_name: str
    display_name: str
    category: str | None
    is_known: bool
    raw_input: str


def normalize_skill_entry(value: str) -> NormalizedSkill:
    """Deterministic skill normalization pipeline returning a full identity envelope."""
    if not isinstance(value, str):
        raw = str(value or "")
    else:
        raw = value
    cleaned = " ".join(raw.strip().split())
    definition = _ALIASES.get(cleaned.casefold())
    if definition:
        return NormalizedSkill(
            canonical_skill_id=definition.skill_id,
            canonical_name=definition.name,
            display_name=definition.name,
            category=definition.category,
            is_known=True,
            raw_input=value,
        )
    return NormalizedSkill(
        canonical_skill_id=None,
        canonical_name=cleaned,
        display_name=cleaned,
        category=None,
        is_known=False,
        raw_input=value,
    )


def normalize_skill(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    definition = _ALIASES.get(cleaned.casefold())
    return definition.name if definition else cleaned


def canonical_skill_id(value: str) -> str | None:
    definition = _ALIASES.get(" ".join(value.strip().split()).casefold())
    return definition.skill_id if definition else None


def reference_skill_id(value: str) -> str:
    """Stable local reference entity ID for a non-registry taxonomy label."""
    cleaned = " ".join(str(value or "").strip().split())
    token = re.sub(r"[^a-z0-9]+", "_", cleaned.casefold()).strip("_")[:48] or "skill"
    digest = hashlib.sha256(cleaned.casefold().encode("utf-8")).hexdigest()[:12]
    return f"refskill:{token}:{digest}"


def skill_category(value: str) -> str | None:
    definition = BY_NAME.get(normalize_skill(value).casefold())
    return definition.category if definition else None


def source_mapping(source: str, value: str) -> SkillDefinition | None:
    source_key = source.casefold().replace(" ", "_").replace("-", "_")
    token = value.strip().casefold().replace(" ", "-")
    field = {"github": "github_topics", "github_topic": "github_topics",
             "stack_exchange": "stack_exchange_tags", "stackexchange": "stack_exchange_tags",
             "stack_exchange_tag": "stack_exchange_tags"}.get(source_key)
    if not field:
        return None
    return next((item for item in SKILLS if token in getattr(item, field)), None)


def _pattern(value: str) -> re.Pattern[str]:
    escaped = re.escape(value).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)


_TERMS = sorted(
    ((alias, item, _pattern(alias)) for item in SKILLS for alias in (item.name, *item.aliases)),
    key=lambda entry: len(entry[0]), reverse=True,
)
_GO_CONTEXT = _pattern("go language")
_R_CONTEXT = re.compile(r"\b(?:r\s+programming|r\s+language|rstats|rstudio|tidyverse|ggplot2|dplyr|shiny\s+app)\b", re.I)
_C_CONTEXT = re.compile(r"\b(?:c\s+programming|c\s+language|c/c\+\+|gcc|clang|libc)\b", re.I)


def _ambiguous_match(item: SkillDefinition, text: str, start: int, end: int) -> bool:
    if not item.ambiguous:
        return True
    window = text[max(0, start - 48):min(len(text), end + 48)]
    if item.skill_id == "go":
        return bool(_GO_CONTEXT.search(window) or re.search(r"\b(?:golang|go\s+programming)\b", window, re.I))
    if item.skill_id == "r":
        return bool(_R_CONTEXT.search(window))
    if item.skill_id == "c":
        return bool(_C_CONTEXT.search(window))
    if item.skill_id == "spring_framework":
        return bool(re.search(r"\b(?:spring\s+(?:boot|framework)|java\s+spring)\b", window, re.I))
    return False


def extract_skills(*texts: str | None) -> list[str]:
    text = " ".join(value for value in texts if value)
    found: dict[str, str] = {}
    for _, item, pattern in _TERMS:
        if item.skill_id in found:
            continue
        match = pattern.search(text)
        if match and _ambiguous_match(item, text, match.start(), match.end()):
            found[item.skill_id] = item.name
    return sorted(found.values(), key=str.casefold)
