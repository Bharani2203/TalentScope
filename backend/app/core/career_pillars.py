"""Core Career Pillars Configuration and Taxonomy Mapping for TalentScope.ai.

Defines the 10 foundational career pillars, their constituent trackable skills,
representative Wikipedia telemetry articles, Stack Overflow tags, GitHub topics,
and classification helpers.
"""

from __future__ import annotations

from typing import Any, TypedDict


class TrackableSkill(TypedDict):
    name: str
    slug: str
    db_name: str
    wikipedia_slug: str
    so_tag: str
    github_topic: str


class PillarDefinition(TypedDict):
    id: int
    slug: str
    title: str
    representative_article: str
    keywords: list[str]
    description: str
    trackable_skills: list[TrackableSkill]


CAREER_PILLARS: dict[str, PillarDefinition] = {
    "ai_machine_learning": {
        "id": 1,
        "slug": "ai-and-machine-learning",
        "title": "Artificial Intelligence and Machine Learning",
        "representative_article": "Artificial intelligence",
        "keywords": [
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "natural language processing",
            "nlp",
            "computer vision",
            "neural networks",
            "large language models",
            "llm",
            "generative ai",
            "genai",
            "pytorch",
            "tensorflow",
            "reinforcement learning",
            "hugging face",
            "transformers",
        ],
        "description": "Design, training, and deployment of intelligent systems, statistical learning models, and cognitive architectures.",
        "trackable_skills": [
            {
                "name": "Generative AI",
                "slug": "generative-ai",
                "db_name": "generative ai",
                "wikipedia_slug": "Generative_artificial_intelligence",
                "so_tag": "generative-ai",
                "github_topic": "generative-ai",
            },
            {
                "name": "PyTorch",
                "slug": "pytorch",
                "db_name": "pytorch",
                "wikipedia_slug": "PyTorch",
                "so_tag": "pytorch",
                "github_topic": "pytorch",
            },
            {
                "name": "LangChain",
                "slug": "langchain",
                "db_name": "langchain",
                "wikipedia_slug": "LangChain",
                "so_tag": "langchain",
                "github_topic": "langchain",
            },
            {
                "name": "TensorFlow",
                "slug": "tensorflow",
                "db_name": "tensorflow",
                "wikipedia_slug": "TensorFlow",
                "so_tag": "tensorflow",
                "github_topic": "tensorflow",
            },
        ],
    },
    "data_analysis_science": {
        "id": 2,
        "slug": "data-analysis-and-data-science",
        "title": "Data Analysis and Data Science",
        "representative_article": "Data science",
        "keywords": [
            "data analysis",
            "data science",
            "statistics",
            "data engineering",
            "data visualization",
            "business intelligence",
            "bi",
            "pandas",
            "numpy",
            "sql",
            "tableau",
            "power bi",
            "data mining",
            "predictive modeling",
            "big data",
        ],
        "description": "Extraction of quantitative insights, statistical modeling, data exploration, and executive intelligence reporting.",
        "trackable_skills": [
            {
                "name": "SQL",
                "slug": "sql",
                "db_name": "sql",
                "wikipedia_slug": "SQL",
                "so_tag": "sql",
                "github_topic": "sql",
            },
            {
                "name": "PostgreSQL",
                "slug": "postgresql",
                "db_name": "postgresql",
                "wikipedia_slug": "PostgreSQL",
                "so_tag": "postgresql",
                "github_topic": "postgresql",
            },
            {
                "name": "Pandas",
                "slug": "pandas",
                "db_name": "pandas",
                "wikipedia_slug": "Pandas_(software)",
                "so_tag": "pandas",
                "github_topic": "pandas",
            },
            {
                "name": "Power BI",
                "slug": "power-bi",
                "db_name": "power bi",
                "wikipedia_slug": "Power_BI",
                "so_tag": "powerbi",
                "github_topic": "powerbi",
            },
        ],
    },
    "cybersecurity": {
        "id": 3,
        "slug": "cybersecurity",
        "title": "Cybersecurity",
        "representative_article": "Cybersecurity",
        "keywords": [
            "cybersecurity",
            "information security",
            "infosec",
            "penetration testing",
            "network security",
            "cryptography",
            "security operations center",
            "soc",
            "siem",
            "vulnerability assessment",
            "threat intelligence",
            "zero trust",
            "incident response",
            "ethical hacking",
            "identity and access management",
            "iam",
        ],
        "description": "Defensive governance, infrastructure hardening, cryptographic privacy, threat mitigation, and vulnerability remediation.",
        "trackable_skills": [
            {
                "name": "Penetration Testing",
                "slug": "penetration-testing",
                "db_name": "penetration testing",
                "wikipedia_slug": "Penetration_test",
                "so_tag": "penetration-testing",
                "github_topic": "penetration-testing",
            },
            {
                "name": "SIEM",
                "slug": "siem",
                "db_name": "siem",
                "wikipedia_slug": "Security_information_and_event_management",
                "so_tag": "siem",
                "github_topic": "siem",
            },
            {
                "name": "Cryptography",
                "slug": "cryptography",
                "db_name": "cryptography",
                "wikipedia_slug": "Cryptography",
                "so_tag": "cryptography",
                "github_topic": "cryptography",
            },
            {
                "name": "Network Security",
                "slug": "network-security",
                "db_name": "network security",
                "wikipedia_slug": "Network_security",
                "so_tag": "network-security",
                "github_topic": "network-security",
            },
        ],
    },
    "cloud_devops": {
        "id": 4,
        "slug": "cloud-computing-and-devops",
        "title": "Cloud Computing and DevOps",
        "representative_article": "Cloud computing",
        "keywords": [
            "cloud computing",
            "devops",
            "aws",
            "amazon web services",
            "azure",
            "google cloud",
            "gcp",
            "docker",
            "kubernetes",
            "k8s",
            "ci/cd",
            "continuous integration",
            "terraform",
            "infrastructure as code",
            "iac",
            "site reliability engineering",
            "sre",
            "ansible",
            "microservices",
        ],
        "description": "Elastic distributed infrastructure, container orchestration, automated release pipelines, and site reliability.",
        "trackable_skills": [
            {
                "name": "AWS",
                "slug": "aws",
                "db_name": "aws",
                "wikipedia_slug": "Amazon_Web_Services",
                "so_tag": "amazon-web-services",
                "github_topic": "aws",
            },
            {
                "name": "Docker",
                "slug": "docker",
                "db_name": "docker",
                "wikipedia_slug": "Docker_(software)",
                "so_tag": "docker",
                "github_topic": "docker",
            },
            {
                "name": "Kubernetes",
                "slug": "kubernetes",
                "db_name": "kubernetes",
                "wikipedia_slug": "Kubernetes",
                "so_tag": "kubernetes",
                "github_topic": "kubernetes",
            },
            {
                "name": "Terraform",
                "slug": "terraform",
                "db_name": "terraform",
                "wikipedia_slug": "Terraform_(software)",
                "so_tag": "terraform",
                "github_topic": "terraform",
            },
        ],
    },
    "software_engineering_fullstack": {
        "id": 5,
        "slug": "software-engineering-and-fullstack",
        "title": "Software Engineering and Full-Stack Development",
        "representative_article": "Software engineering",
        "keywords": [
            "software engineering",
            "full stack",
            "full-stack development",
            "frontend",
            "backend",
            "web development",
            "javascript",
            "typescript",
            "python",
            "react",
            "node.js",
            "angular",
            "vue",
            "java",
            "c#",
            "c++",
            "golang",
            "api development",
            "system design",
            "object-oriented programming",
        ],
        "description": "End-to-end software architecture, modular application development, reusable libraries, and distributed web applications.",
        "trackable_skills": [
            {
                "name": "Python",
                "slug": "python",
                "db_name": "python",
                "wikipedia_slug": "Python_(programming_language)",
                "so_tag": "python",
                "github_topic": "python",
            },
            {
                "name": "TypeScript",
                "slug": "typescript",
                "db_name": "typescript",
                "wikipedia_slug": "TypeScript",
                "so_tag": "typescript",
                "github_topic": "typescript",
            },
            {
                "name": "React",
                "slug": "react",
                "db_name": "react",
                "wikipedia_slug": "React_(software)",
                "so_tag": "reactjs",
                "github_topic": "react",
            },
            {
                "name": "Node.js",
                "slug": "nodejs",
                "db_name": "node.js",
                "wikipedia_slug": "Node.js",
                "so_tag": "node.js",
                "github_topic": "nodejs",
            },
        ],
    },
    "project_management_coordination": {
        "id": 6,
        "slug": "project-management-and-coordination",
        "title": "Project Management and Stakeholder Coordination",
        "representative_article": "Project management",
        "keywords": [
            "project management",
            "scrum",
            "agile",
            "kanban",
            "stakeholder management",
            "stakeholder coordination",
            "jira",
            "confluence",
            "product roadmap",
            "pmp",
            "sprint planning",
            "cross-functional coordination",
            "resource allocation",
            "risk management",
            "program management",
        ],
        "description": "Agile project orchestration, delivery cadence, team facilitation, alignment across stakeholder groups, and scope tracking.",
        "trackable_skills": [
            {
                "name": "Jira",
                "slug": "jira",
                "db_name": "jira",
                "wikipedia_slug": "Jira_(software)",
                "so_tag": "jira",
                "github_topic": "jira",
            },
            {
                "name": "Scrum",
                "slug": "scrum",
                "db_name": "scrum",
                "wikipedia_slug": "Scrum_(software_development)",
                "so_tag": "scrum",
                "github_topic": "scrum",
            },
            {
                "name": "Agile",
                "slug": "agile",
                "db_name": "agile",
                "wikipedia_slug": "Agile_software_development",
                "so_tag": "agile",
                "github_topic": "agile",
            },
            {
                "name": "Confluence",
                "slug": "confluence",
                "db_name": "confluence",
                "wikipedia_slug": "Confluence_(software)",
                "so_tag": "confluence",
                "github_topic": "confluence",
            },
        ],
    },
    "ux_ui_product_design": {
        "id": 7,
        "slug": "ux-ui-and-product-design",
        "title": "UX/UI Design and Product Design",
        "representative_article": "User experience design",
        "keywords": [
            "ux design",
            "ui design",
            "product design",
            "user experience",
            "user interface",
            "figma",
            "wireframing",
            "prototyping",
            "user research",
            "usability testing",
            "design systems",
            "interaction design",
            "information architecture",
            "accessibility",
            "wcag",
        ],
        "description": "Human-centered design, interactive design system specification, design thinking, and high-fidelity product prototyping.",
        "trackable_skills": [
            {
                "name": "Figma",
                "slug": "figma",
                "db_name": "figma",
                "wikipedia_slug": "Figma",
                "so_tag": "figma",
                "github_topic": "figma",
            },
            {
                "name": "User Research",
                "slug": "user-research",
                "db_name": "user research",
                "wikipedia_slug": "User_research",
                "so_tag": "accessibility",
                "github_topic": "design-system",
            },
            {
                "name": "Wireframing",
                "slug": "wireframing",
                "db_name": "wireframing",
                "wikipedia_slug": "Website_wireframe",
                "so_tag": "figma",
                "github_topic": "figma",
            },
            {
                "name": "Design Systems",
                "slug": "design-systems",
                "db_name": "design systems",
                "wikipedia_slug": "Design_system",
                "so_tag": "accessibility",
                "github_topic": "design-system",
            },
        ],
    },
    "digital_marketing_growth": {
        "id": 8,
        "slug": "digital-marketing-and-growth",
        "title": "Digital Marketing and Performance Growth",
        "representative_article": "Digital marketing",
        "keywords": [
            "digital marketing",
            "seo",
            "search engine optimization",
            "sem",
            "growth marketing",
            "content strategy",
            "social media marketing",
            "email marketing",
            "google analytics",
            "conversion rate optimization",
            "cro",
            "performance marketing",
            "customer acquisition",
            "campaign management",
        ],
        "description": "Multi-channel funnel acquisition, organic/paid discovery, audience engagement, conversion funnels, and marketing analytics.",
        "trackable_skills": [
            {
                "name": "SEO",
                "slug": "seo",
                "db_name": "seo",
                "wikipedia_slug": "Search_engine_optimization",
                "so_tag": "seo",
                "github_topic": "seo",
            },
            {
                "name": "Google Analytics",
                "slug": "google-analytics",
                "db_name": "google analytics",
                "wikipedia_slug": "Google_Analytics",
                "so_tag": "google-analytics",
                "github_topic": "google-analytics",
            },
            {
                "name": "Content Strategy",
                "slug": "content-strategy",
                "db_name": "content strategy",
                "wikipedia_slug": "Content_strategy",
                "so_tag": "seo",
                "github_topic": "seo",
            },
            {
                "name": "Social Media Marketing",
                "slug": "social-media-marketing",
                "db_name": "social media marketing",
                "wikipedia_slug": "Social_media_marketing",
                "so_tag": "google-analytics",
                "github_topic": "google-analytics",
            },
        ],
    },
    "analytical_critical_thinking": {
        "id": 9,
        "slug": "analytical-and-critical-thinking",
        "title": "Analytical and Critical Thinking",
        "representative_article": "Critical thinking",
        "keywords": [
            "critical thinking",
            "analytical thinking",
            "problem solving",
            "decision making",
            "root cause analysis",
            "first principles",
            "data-driven decision making",
            "strategic thinking",
            "logical reasoning",
            "deductive reasoning",
            "quantitative reasoning",
            "hypothesis testing",
        ],
        "description": "Systemic root cause decomposition, logical reasoning, structured evidence evaluation, and cognitive decision modeling.",
        "trackable_skills": [
            {
                "name": "Problem Solving",
                "slug": "problem-solving",
                "db_name": "problem solving",
                "wikipedia_slug": "Problem_solving",
                "so_tag": "debugging",
                "github_topic": "debugging",
            },
            {
                "name": "Root Cause Analysis",
                "slug": "root-cause-analysis",
                "db_name": "root cause analysis",
                "wikipedia_slug": "Root_cause_analysis",
                "so_tag": "architecture",
                "github_topic": "system-architecture",
            },
            {
                "name": "Logical Reasoning",
                "slug": "logical-reasoning",
                "db_name": "logical reasoning",
                "wikipedia_slug": "Logical_reasoning",
                "so_tag": "debugging",
                "github_topic": "debugging",
            },
            {
                "name": "Data-Driven Decision Making",
                "slug": "data-driven-decision-making",
                "db_name": "data-driven decision making",
                "wikipedia_slug": "Data-informed_decision-making",
                "so_tag": "architecture",
                "github_topic": "system-architecture",
            },
        ],
    },
    "adaptability_continuous_learning": {
        "id": 10,
        "slug": "adaptability-and-continuous-learning",
        "title": "Adaptability and Continuous Learning",
        "representative_article": "Lifelong learning",
        "keywords": [
            "adaptability",
            "continuous learning",
            "resilience",
            "growth mindset",
            "upskilling",
            "reskilling",
            "curiosity",
            "agility",
            "self-directed learning",
            "change management",
            "cognitive flexibility",
            "emotional intelligence",
            "professional development",
        ],
        "description": "Agile learning capacity, rapid tool and paradigm adoption, resilience under change, and proactive skills acquisition.",
        "trackable_skills": [
            {
                "name": "Continuous Learning",
                "slug": "continuous-learning",
                "db_name": "continuous learning",
                "wikipedia_slug": "Lifelong_learning",
                "so_tag": "prompt-engineering",
                "github_topic": "prompt-engineering",
            },
            {
                "name": "Resilience",
                "slug": "resilience",
                "db_name": "resilience",
                "wikipedia_slug": "Psychological_resilience",
                "so_tag": "github-copilot",
                "github_topic": "prompt-engineering",
            },
            {
                "name": "Upskilling",
                "slug": "upskilling",
                "db_name": "upskilling",
                "wikipedia_slug": "Upskilling",
                "so_tag": "prompt-engineering",
                "github_topic": "prompt-engineering",
            },
            {
                "name": "Change Management",
                "slug": "change-management",
                "db_name": "change management",
                "wikipedia_slug": "Change_management",
                "so_tag": "github-copilot",
                "github_topic": "prompt-engineering",
            },
        ],
    },
}


def get_all_pillars() -> list[PillarDefinition]:
    """Return all 10 defined career pillars sorted by their ID."""
    return sorted(CAREER_PILLARS.values(), key=lambda p: p["id"])


def get_pillar_by_slug(slug: str) -> PillarDefinition | None:
    """Find a pillar definition by its slug identifier."""
    norm = slug.lower().strip()
    for pillar in CAREER_PILLARS.values():
        if pillar["slug"] == norm or pillar["slug"].replace("-", "_") == norm.replace("-", "_"):
            return pillar
    return None


def get_trackable_skills_for_pillar(pillar_slug: str) -> list[TrackableSkill]:
    """Return list of trackable skills belonging to a pillar."""
    p = get_pillar_by_slug(pillar_slug)
    return p["trackable_skills"] if p else []


def get_all_curated_skills() -> list[dict[str, Any]]:
    """Return a flattened list of all curated trackable skills tagged with their parent pillar."""
    curated = []
    for p_key, pillar in CAREER_PILLARS.items():
        for skill in pillar.get("trackable_skills", []):
            item = dict(skill)
            item["pillar_id"] = pillar["id"]
            item["pillar_slug"] = pillar["slug"]
            item["pillar_title"] = pillar["title"]
            curated.append(item)
    return curated


def find_pillar_for_skill(skill_name: str) -> PillarDefinition | None:
    """Classify a skill into one of the 10 career pillars based on keyword matching."""
    norm = skill_name.lower().strip()
    for pillar in CAREER_PILLARS.values():
        # First check explicit trackable skills
        for ts in pillar.get("trackable_skills", []):
            if ts["db_name"] == norm or ts["slug"] == norm or ts["name"].lower() == norm:
                return pillar
        # Fallback to broader keyword list
        if any(kw == norm or kw in norm for kw in pillar["keywords"]):
            return pillar
    return None


def get_pillar_article_map() -> dict[str, str]:
    """Return a mapping of pillar slug to its representative Wikipedia article title."""
    return {pillar["slug"]: pillar["representative_article"] for pillar in CAREER_PILLARS.values()}


NON_CODING_PILLAR_IDS: set[int] = {7, 8, 9, 10}
NON_CODING_PILLAR_SLUGS: set[str] = {
    "ux-ui-and-product-design",
    "digital-marketing-and-growth",
    "analytical-and-critical-thinking",
    "adaptability-and-continuous-learning",
}


def is_non_coding_pillar(pillar_id_or_slug: int | str | None) -> bool:
    """Return True if the pillar represents a non-coding domain requiring adjusted external weighting."""
    if pillar_id_or_slug is None:
        return False
    if isinstance(pillar_id_or_slug, int):
        return pillar_id_or_slug in NON_CODING_PILLAR_IDS
    norm = str(pillar_id_or_slug).lower().strip()
    return norm in NON_CODING_PILLAR_SLUGS or norm.replace("-", "_") in {
        s.replace("-", "_") for s in NON_CODING_PILLAR_SLUGS
    }
