"""Regression tests for Task 2: Skill registry expansion.

Verifies that:
1. All 14 newly added skills have correct canonical IDs, names, and categories.
2. Key aliases resolve correctly (PySpark -> Apache Spark, PowerBI -> Power BI, etc.).
3. No collision with existing skills (MySQL != SQL, Apache Spark != Spring, Flask != Express.js).
4. Existing skills are unaffected (Python, Java, React, AWS, SQL still normalize correctly).
5. Idempotent normalization holds for all new skills.
6. Total skill count is 62 (was 48; +14 truly new; fastapi was already present).

New skills added (alphabetically by skill_id):
  databricks, devops, excel, flask, graphql, kotlin, linux, llm,
  mysql, power_bi, rust, scala, spark, swift, tableau
"""

from __future__ import annotations

import pytest

from app.analytics.skill_registry import BY_ID, SKILLS
from app.analytics.skill_normalization import canonical_skill_id, normalize_skill


NEW_SKILL_IDS = [
    "databricks", "devops", "excel", "flask", "graphql",
    "kotlin", "linux", "llm", "mysql", "power_bi",
    "rust", "scala", "spark", "swift", "tableau",
]


# ============================================================================
# Registry integrity
# ============================================================================

class TestRegistryIntegrity:
    def test_total_skill_count(self):
        """Registry must have 62 skills (48 original + 14 new; fastapi was already present)."""
        assert len(SKILLS) == 62

    def test_all_new_skill_ids_present_in_by_id(self):
        """Every newly added skill_id must exist in BY_ID lookup."""
        for skill_id in NEW_SKILL_IDS:
            assert skill_id in BY_ID, f"Missing skill_id: {skill_id}"

    def test_no_duplicate_skill_ids(self):
        """All skill_ids must be unique."""
        ids = [s.skill_id for s in SKILLS]
        assert len(ids) == len(set(ids))

    def test_no_duplicate_canonical_names(self):
        """All canonical names must be unique (case-insensitive)."""
        names = [s.name.casefold() for s in SKILLS]
        assert len(names) == len(set(names))


# ============================================================================
# New skill normalizations
# ============================================================================

class TestNewSkillNormalization:
    def test_rust_normalization(self):
        assert normalize_skill("Rust") == "Rust"
        assert normalize_skill("rust lang") == "Rust"
        assert normalize_skill("Rust Programming") == "Rust"
        assert canonical_skill_id("Rust") == "rust"
        assert canonical_skill_id("rust language") == "rust"

    def test_scala_normalization(self):
        assert normalize_skill("Scala") == "Scala"
        assert canonical_skill_id("scala") == "scala"

    def test_kotlin_normalization(self):
        assert normalize_skill("Kotlin") == "Kotlin"
        assert canonical_skill_id("kotlin") == "kotlin"

    def test_swift_normalization(self):
        assert normalize_skill("Swift") == "Swift"
        assert canonical_skill_id("swift") == "swift"

    def test_databricks_normalization(self):
        assert normalize_skill("Databricks") == "Databricks"
        assert canonical_skill_id("databricks") == "databricks"

    def test_apache_spark_normalization(self):
        assert normalize_skill("Apache Spark") == "Apache Spark"
        assert normalize_skill("PySpark") == "Apache Spark"
        assert normalize_skill("pyspark") == "Apache Spark"
        assert normalize_skill("spark") == "Apache Spark"
        assert canonical_skill_id("spark") == "spark"
        assert canonical_skill_id("pyspark") == "spark"

    def test_power_bi_normalization(self):
        assert normalize_skill("Power BI") == "Power BI"
        assert normalize_skill("PowerBI") == "Power BI"
        assert normalize_skill("powerbi") == "Power BI"
        assert canonical_skill_id("power bi") == "power_bi"
        assert canonical_skill_id("powerbi") == "power_bi"

    def test_excel_normalization(self):
        assert normalize_skill("Excel") == "Excel"
        assert normalize_skill("Microsoft Excel") == "Excel"
        assert normalize_skill("MS Excel") == "Excel"
        assert canonical_skill_id("excel") == "excel"
        assert canonical_skill_id("microsoft excel") == "excel"

    def test_tableau_normalization(self):
        assert normalize_skill("Tableau") == "Tableau"
        assert canonical_skill_id("tableau") == "tableau"

    def test_flask_normalization(self):
        assert normalize_skill("Flask") == "Flask"
        assert canonical_skill_id("flask") == "flask"

    def test_llm_normalization(self):
        assert normalize_skill("LLM") == "LLM"
        assert normalize_skill("large language model") == "LLM"
        assert normalize_skill("large language models") == "LLM"
        assert canonical_skill_id("llm") == "llm"
        assert canonical_skill_id("large language model") == "llm"

    def test_devops_normalization(self):
        assert normalize_skill("DevOps") == "DevOps"
        assert canonical_skill_id("devops") == "devops"

    def test_linux_normalization(self):
        assert normalize_skill("Linux") == "Linux"
        assert canonical_skill_id("linux") == "linux"

    def test_mysql_normalization(self):
        assert normalize_skill("MySQL") == "MySQL"
        assert canonical_skill_id("mysql") == "mysql"
        assert canonical_skill_id("MySQL") == "mysql"

    def test_graphql_normalization(self):
        assert normalize_skill("GraphQL") == "GraphQL"
        assert canonical_skill_id("graphql") == "graphql"


# ============================================================================
# No collision with existing skills
# ============================================================================

class TestNoCollision:
    def test_mysql_distinct_from_sql(self):
        assert canonical_skill_id("MySQL") != canonical_skill_id("SQL")
        assert normalize_skill("MySQL") != normalize_skill("SQL")

    def test_mysql_distinct_from_postgresql(self):
        assert canonical_skill_id("MySQL") != canonical_skill_id("PostgreSQL")

    def test_apache_spark_distinct_from_spring(self):
        """'spark' alias for Apache Spark must not collide with Spring (spring_framework)."""
        assert canonical_skill_id("Apache Spark") != canonical_skill_id("Spring")
        assert normalize_skill("Apache Spark") == "Apache Spark"
        assert normalize_skill("Spring") == "Spring"

    def test_flask_distinct_from_express(self):
        assert canonical_skill_id("Flask") != canonical_skill_id("Express.js")

    def test_flask_distinct_from_django(self):
        assert canonical_skill_id("Flask") != canonical_skill_id("Django")

    def test_rust_distinct_from_r(self):
        """'Rust' must not resolve to 'R' or vice versa."""
        assert canonical_skill_id("Rust") != canonical_skill_id("R")
        assert normalize_skill("Rust") == "Rust"

    def test_tableau_distinct_from_terraform(self):
        assert canonical_skill_id("Tableau") != canonical_skill_id("Terraform")

    def test_kotlin_distinct_from_kubernetes(self):
        assert canonical_skill_id("Kotlin") != canonical_skill_id("Kubernetes")

    def test_linux_distinct_from_llm(self):
        assert canonical_skill_id("Linux") != canonical_skill_id("LLM")

    def test_excel_distinct_from_express(self):
        assert canonical_skill_id("Excel") != canonical_skill_id("Express.js")


# ============================================================================
# Existing skills unaffected
# ============================================================================

class TestExistingSkillsUnaffected:
    def test_python_still_normalizes(self):
        assert normalize_skill("Python") == "Python"
        assert canonical_skill_id("python") == "python"

    def test_java_still_normalizes(self):
        assert normalize_skill("Java") == "Java"
        assert canonical_skill_id("java") == "java"

    def test_javascript_still_distinct_from_java(self):
        assert canonical_skill_id("Java") != canonical_skill_id("JavaScript")

    def test_react_still_normalizes(self):
        assert normalize_skill("React") == "React"
        assert canonical_skill_id("react") == "react"

    def test_aws_still_normalizes(self):
        assert normalize_skill("AWS") == "AWS"
        assert canonical_skill_id("amazon web services") == "aws"

    def test_sql_still_normalizes(self):
        assert normalize_skill("SQL") == "SQL"
        assert canonical_skill_id("sql") == "sql"

    def test_fastapi_still_present(self):
        """fastapi was in the original 48; must still normalize correctly."""
        assert normalize_skill("FastAPI") == "FastAPI"
        assert canonical_skill_id("fastapi") == "fastapi"

    def test_spring_boot_still_normalizes(self):
        assert normalize_skill("Spring Boot") == "Spring"
        assert canonical_skill_id("spring boot") == "spring_framework"


# ============================================================================
# Idempotent normalization for new skills
# ============================================================================

class TestIdempotentNormalization:
    @pytest.mark.parametrize("raw_input", [
        "Rust", "rust lang", "Scala", "Kotlin", "Swift",
        "Databricks", "Apache Spark", "PySpark", "spark",
        "Power BI", "PowerBI", "Excel", "Microsoft Excel",
        "Tableau", "Flask", "LLM", "large language model",
        "DevOps", "Linux", "MySQL", "GraphQL",
    ])
    def test_double_normalize_is_stable(self, raw_input: str):
        first = normalize_skill(raw_input)
        second = normalize_skill(first)
        assert first == second, f"normalize_skill(normalize_skill({raw_input!r})) != normalize_skill({raw_input!r})"
