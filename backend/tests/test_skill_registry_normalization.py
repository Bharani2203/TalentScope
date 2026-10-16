"""Comprehensive tests for G1.2 Skill Normalization & Canonical Skill Registry.

Validates:
1. Case normalization (python, PYTHON, Python -> Python)
2. Whitespace normalization (leading, trailing, internal excess spaces)
3. Alias resolution (JS -> JavaScript, Golang -> Go, SpringBoot -> Spring)
4. Canonical ID determinism (C# -> c_sharp, C++ -> c_plus_plus, Node.js -> node_js)
5. Multi-word skills (Machine Learning, Cloud Computing, Data Science)
6. Punctuation variations (C-Sharp, C Sharp, C-Plus-Plus, C Plus Plus, Node JS, Node.js)
7. C# handling and compatibility with existing Adzuna observations
8. C++ handling
9. Node.js handling
10. React handling
11. AWS handling (Amazon Web Services -> AWS)
12. Azure handling (Microsoft Azure -> Azure)
13. Java vs JavaScript separation (strictly distinct)
14. React vs React Native separation (strictly distinct)
15. SQL vs PostgreSQL separation (strictly distinct)
16. Node.js vs Express.js separation (strictly distinct)
17. Unknown skill handling (preserves raw value, is_known=False, canonical_skill_id=None)
18. Existing Adzuna C# compatibility (c_sharp ID matches production observation)
19. Existing user profile compatibility (selected_skills round trip cleanly)
20. Idempotent repeated normalization (normalize(normalize(x)) == normalize(x))
"""

import pytest

from app.analytics.skill_normalization import (
    NormalizedSkill,
    canonical_skill_id,
    extract_skills,
    normalize_skill,
    normalize_skill_entry,
    skill_category,
)


def test_1_case_normalization():
    assert normalize_skill("python") == "Python"
    assert normalize_skill("PYTHON") == "Python"
    assert normalize_skill("PyThOn") == "Python"
    assert canonical_skill_id("python") == "python"
    assert canonical_skill_id("PYTHON") == "python"


def test_2_whitespace_normalization():
    assert normalize_skill("   Python   ") == "Python"
    assert normalize_skill("Machine    Learning") == "Machine Learning"
    assert canonical_skill_id("   Machine   Learning   ") == "machine_learning"


def test_3_alias_resolution():
    assert normalize_skill("JS") == "JavaScript"
    assert normalize_skill("Javascript") == "JavaScript"
    assert normalize_skill("Golang") == "Go"
    assert normalize_skill("Spring Boot") == "Spring"
    assert normalize_skill("SpringBoot") == "Spring"
    assert normalize_skill("Postgres") == "PostgreSQL"
    assert normalize_skill("GCP") == "Google Cloud"
    assert normalize_skill("Google Cloud Platform") == "Google Cloud"


def test_4_canonical_id_determinism():
    assert canonical_skill_id("Python") == "python"
    assert canonical_skill_id("C#") == "c_sharp"
    assert canonical_skill_id("C++") == "c_plus_plus"
    assert canonical_skill_id("Node.js") == "node_js"
    assert canonical_skill_id("AWS") == "aws"
    assert canonical_skill_id("Azure") == "azure"


def test_5_multi_word_skills():
    assert normalize_skill("machine learning") == "Machine Learning"
    assert normalize_skill("cloud computing") == "Cloud Computing"
    assert normalize_skill("data science") == "Data Science"
    assert normalize_skill("data analytics") == "Data Analytics"
    assert normalize_skill("generative ai") == "Generative AI"
    assert canonical_skill_id("Data Science") == "data_science"


def test_6_punctuation_variations():
    assert normalize_skill("C-Sharp") == "C#"
    assert normalize_skill("C Sharp") == "C#"
    assert normalize_skill("C-Plus-Plus") == "C++"
    assert normalize_skill("C Plus Plus") == "C++"
    assert normalize_skill("Node JS") == "Node.js"
    assert normalize_skill("NodeJS") == "Node.js"
    assert normalize_skill("Node.js") == "Node.js"
    assert normalize_skill("React.js") == "React"
    assert normalize_skill("ReactJS") == "React"
    assert normalize_skill("Vue.js") == "Vue.js"
    assert normalize_skill("Angular.js") == "Angular"


def test_7_c_sharp_handling():
    assert normalize_skill("c#") == "C#"
    assert normalize_skill("C#") == "C#"
    assert normalize_skill("c sharp") == "C#"
    assert canonical_skill_id("C#") == "c_sharp"
    assert canonical_skill_id("c sharp") == "c_sharp"
    assert canonical_skill_id("c-sharp") == "c_sharp"


def test_8_c_plus_plus_handling():
    assert normalize_skill("c++") == "C++"
    assert normalize_skill("C++") == "C++"
    assert normalize_skill("cpp") == "C++"
    assert normalize_skill("c plus plus") == "C++"
    assert canonical_skill_id("C++") == "c_plus_plus"
    assert canonical_skill_id("cpp") == "c_plus_plus"


def test_9_node_js_handling():
    assert normalize_skill("node.js") == "Node.js"
    assert normalize_skill("Node.js") == "Node.js"
    assert normalize_skill("nodejs") == "Node.js"
    assert normalize_skill("node js") == "Node.js"
    assert canonical_skill_id("Node.js") == "node_js"
    assert canonical_skill_id("nodejs") == "node_js"


def test_10_react_handling():
    assert normalize_skill("react") == "React"
    assert normalize_skill("React.js") == "React"
    assert normalize_skill("ReactJS") == "React"
    assert canonical_skill_id("React") == "react"
    assert canonical_skill_id("react.js") == "react"


def test_11_aws_handling():
    assert normalize_skill("aws") == "AWS"
    assert normalize_skill("Amazon Web Services") == "AWS"
    assert canonical_skill_id("AWS") == "aws"
    assert canonical_skill_id("amazon web services") == "aws"


def test_12_azure_handling():
    assert normalize_skill("azure") == "Azure"
    assert normalize_skill("Microsoft Azure") == "Azure"
    assert canonical_skill_id("Azure") == "azure"
    assert canonical_skill_id("microsoft azure") == "azure"


def test_13_java_vs_javascript_separation():
    # Crucial collision safety: Java must NEVER resolve to JavaScript and vice versa
    assert normalize_skill("Java") == "Java"
    assert normalize_skill("JavaScript") == "JavaScript"
    assert canonical_skill_id("Java") == "java"
    assert canonical_skill_id("JavaScript") == "javascript"
    assert canonical_skill_id("Java") != canonical_skill_id("JavaScript")


def test_14_react_vs_react_native_separation():
    # React and React Native are distinct ecosystems
    assert normalize_skill("React") == "React"
    assert normalize_skill("React Native") == "React Native"
    assert canonical_skill_id("React") == "react"
    assert canonical_skill_id("React Native") == "react_native"
    assert canonical_skill_id("React") != canonical_skill_id("React Native")


def test_15_sql_vs_postgresql_vs_sql_server_separation():
    # SQL, PostgreSQL, and SQL Server are distinct database skills
    assert normalize_skill("SQL") == "SQL"
    assert normalize_skill("PostgreSQL") == "PostgreSQL"
    assert normalize_skill("Postgres") == "PostgreSQL"
    assert normalize_skill("SQL Server") == "SQL Server"
    assert normalize_skill("MS SQL Server") == "SQL Server"
    assert canonical_skill_id("SQL") == "sql"
    assert canonical_skill_id("PostgreSQL") == "postgresql"
    assert canonical_skill_id("SQL Server") == "sql_server"
    assert len({canonical_skill_id("SQL"), canonical_skill_id("PostgreSQL"), canonical_skill_id("SQL Server")}) == 3


def test_16_node_js_vs_express_js_separation():
    # Node.js runtime vs Express framework
    assert normalize_skill("Node.js") == "Node.js"
    assert normalize_skill("Express") == "Express.js"
    assert normalize_skill("Express.js") == "Express.js"
    assert canonical_skill_id("Node.js") == "node_js"
    assert canonical_skill_id("Express.js") == "express_js"
    assert canonical_skill_id("Node.js") != canonical_skill_id("Express.js")


def test_17_unknown_skill_handling():
    # An unknown skill must preserve its cleaned raw value without crashing or mapping to a random skill
    unknown = "Quantum Hyperloop Engineering 2026"
    assert normalize_skill(unknown) == unknown
    assert canonical_skill_id(unknown) is None

    entry = normalize_skill_entry(unknown)
    assert isinstance(entry, NormalizedSkill)
    assert entry.is_known is False
    assert entry.canonical_skill_id is None
    assert entry.canonical_name == unknown
    assert entry.display_name == unknown
    assert entry.category is None
    assert entry.raw_input == unknown


def test_18_existing_adzuna_c_sharp_compatibility():
    # Production Firestore observation uses:
    # skill="C#", series_id="adzuna:adzuna:47838af054a71a055855:job-demand:c_sharp:v1"
    assert normalize_skill("C#") == "C#"
    assert canonical_skill_id("C#") == "c_sharp"
    entry = normalize_skill_entry("C#")
    assert entry.canonical_skill_id == "c_sharp"
    assert entry.canonical_name == "C#"
    assert entry.is_known is True
    assert entry.category == "Programming"


def test_19_existing_user_profile_compatibility():
    # Profile skills e.g. ["Python", "Machine Learning", "c#"] must cleanly normalize
    user_skills = ["Python", "Machine Learning", "c#", "Postgres", "AWS"]
    normalized = [normalize_skill(s) for s in user_skills]
    assert normalized == ["Python", "Machine Learning", "C#", "PostgreSQL", "AWS"]
    canonical_ids = [canonical_skill_id(s) for s in user_skills]
    assert canonical_ids == ["python", "machine_learning", "c_sharp", "postgresql", "aws"]


def test_20_idempotent_repeated_normalization():
    skills = [
        "Python", "python 3", "JS", "C#", "C-Sharp", "C++", "c plus plus",
        "Node.js", "node js", "React", "React.js", "Postgres", "SQL",
        "AWS", "amazon web services", "Azure", "microsoft azure",
        "Some Custom Unknown Framework",
    ]
    for s in skills:
        norm1 = normalize_skill(s)
        norm2 = normalize_skill(norm1)
        norm3 = normalize_skill(norm2)
        assert norm1 == norm2 == norm3

        entry1 = normalize_skill_entry(s)
        entry2 = normalize_skill_entry(entry1.canonical_name)
        assert entry1.canonical_name == entry2.canonical_name
        assert entry1.canonical_skill_id == entry2.canonical_skill_id
        assert entry1.is_known == entry2.is_known
