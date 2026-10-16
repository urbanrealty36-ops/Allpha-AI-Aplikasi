"""Curated 500-entry Agent Skill catalog derived from public use-case taxonomy.

The referenced upstream repository contains 500+ use cases, but only 21 self-contained
agent implementation folders in its current tree. These records are selectable
skill blueprints, not claims that 500 executable handlers or GLB files exist.
"""
from __future__ import annotations

import re
from typing import Any

UPSTREAM_REPOSITORY = "https://github.com/ashishpatel26/500-AI-Agents-Projects"
_UPSTREAM_EXAMPLES = [
    ("web-research-agent", "Web Research Agent", "research", "Search and synthesize public web information with source provenance."),
    ("code-review-agent", "Code Review Agent", "software_engineering", "Review source changes for defects, maintainability, and security risks."),
    ("pdf-qa-agent", "PDF Question Answering Agent", "documents", "Answer questions grounded in supplied PDF documents."),
    ("sql-query-agent", "SQL Query Agent", "data", "Draft and explain read-only SQL queries against an approved schema."),
    ("email-drafting-agent", "Email Drafting Agent", "communications", "Draft context-aware emails for human review."),
    ("news-summarizer-agent", "News Summarizer Agent", "research", "Summarize news with dates and source links."),
    ("github-issue-triager", "GitHub Issue Triage Agent", "software_engineering", "Classify and prioritize repository issues without taking unapproved actions."),
    ("data-analysis-agent", "Data Analysis Agent", "data", "Analyze structured data and explain methods and uncertainty."),
    ("resume-parser-agent", "Resume Parser Agent", "human_resources", "Extract structured resume fields with privacy-aware handling."),
    ("meeting-notes-agent", "Meeting Notes Agent", "productivity", "Turn meeting notes into decisions, tasks, and open questions."),
    ("stock-research-agent", "Stock Research Agent", "finance", "Prepare research summaries; not an autonomous trading authority."),
    ("travel-planner-agent", "Travel Planner Agent", "travel", "Build itineraries from user preferences and verified travel details."),
    ("customer-support-agent", "Customer Support Agent", "customer_experience", "Draft support responses and route unresolved cases."),
    ("social-media-agent", "Social Media Agent", "marketing", "Draft platform-specific social content for owner approval."),
    ("unit-test-generator", "Unit Test Generator", "software_engineering", "Propose unit tests for supplied code and acceptance criteria."),
    ("documentation-writer", "Documentation Writer", "software_engineering", "Generate maintainable technical documentation from verified source."),
    ("recipe-agent", "Recipe Agent", "food", "Suggest recipes constrained by ingredients and preferences."),
    ("job-application-agent", "Job Application Agent", "human_resources", "Tailor application materials while preserving factual accuracy."),
    ("competitive-analysis-agent", "Competitive Analysis Agent", "strategy", "Compare competitors from cited, dated evidence."),
    ("multi-agent-debate", "Multi-Agent Debate Facilitator", "research", "Structure multiple viewpoints and expose unresolved assumptions."),
    ("pii-sanitization-agent", "PII Sanitization Agent", "privacy_security", "Detect and redact personal data under an explicit policy."),
]
_DOMAINS = [
    ("research", "Research & Intelligence", "Research Specialist"),
    ("software_engineering", "Software Engineering", "Engineering Specialist"),
    ("data", "Data & Analytics", "Data Analyst"),
    ("documents", "Documents & Knowledge", "Knowledge Curator"),
    ("communications", "Writing & Communications", "Communications Specialist"),
    ("marketing", "Marketing & Content", "Creative Strategist"),
    ("sales", "Sales & Business Development", "Sales Advisor"),
    ("customer_experience", "Customer Experience", "Customer Success Guide"),
    ("finance", "Finance & Accounting", "Finance Analyst"),
    ("investing", "Investment Research", "Market Research Analyst"),
    ("healthcare", "Healthcare Administration", "Health Information Guide"),
    ("education", "Education & Learning", "Learning Coach"),
    ("human_resources", "Human Resources", "People Operations Guide"),
    ("legal_operations", "Legal Operations", "Legal Information Assistant"),
    ("cybersecurity", "Cybersecurity", "Security Analyst"),
    ("privacy_security", "Privacy & Trust", "Privacy Steward"),
    ("operations", "Business Operations", "Operations Coordinator"),
    ("productivity", "Personal Productivity", "Productivity Coach"),
    ("strategy", "Strategy & Planning", "Strategy Consultant"),
    ("travel", "Travel & Hospitality", "Travel Planner"),
    ("ecommerce", "E-commerce & Retail", "Commerce Specialist"),
    ("real_estate", "Real Estate", "Property Advisor"),
    ("manufacturing", "Manufacturing & Supply Chain", "Supply Chain Analyst"),
    ("food", "Food & Lifestyle", "Lifestyle Guide"),
    ("creative", "Creative & Design", "Creative Producer"),
]
_TASKS = [
    ("research", "Research and synthesize", "Collect available evidence, distinguish facts from assumptions, and return a cited summary."),
    ("summarize", "Summarize and brief", "Create a concise brief with key points, caveats, and follow-up questions."),
    ("classify", "Classify and route", "Classify supplied items against a defined taxonomy and explain uncertain classifications."),
    ("extract", "Extract structured information", "Extract fields into a validated structure without inventing missing values."),
    ("draft", "Draft for human review", "Prepare a first draft and flag facts requiring human verification."),
    ("analyze", "Analyze and explain", "Analyze supplied information, state methodology, and communicate uncertainty."),
    ("compare", "Compare options", "Compare alternatives using explicit criteria and identify trade-offs."),
    ("plan", "Plan a workflow", "Create a bounded step plan with dependencies, approvals, and success criteria."),
    ("audit", "Audit for quality", "Check supplied artifacts against an explicit checklist and cite evidence."),
    ("answer", "Answer grounded questions", "Answer only from available context and identify information gaps."),
    ("transform", "Transform content", "Transform supplied content while preserving meaning and required structure."),
    ("recommend", "Recommend next steps", "Offer evidence-based options with assumptions and risks stated."),
    ("monitor", "Monitor defined signals", "Review only configured signals and report changes; no external action without approval."),
    ("triage", "Triage incoming work", "Prioritize requests using declared rules and escalate ambiguous or high-risk cases."),
    ("generate_tests", "Generate validation tests", "Propose tests and expected behaviors from a supplied contract."),
    ("document", "Document a process", "Create versionable documentation from verified requirements and observed behavior."),
    ("coach", "Coach and explain", "Guide a user through a learning or problem-solving process without claiming professional authority."),
    ("validate", "Validate data quality", "Check completeness, format, consistency, and provenance; never fabricate missing fields."),
    ("prepare_meeting", "Prepare a meeting", "Prepare agenda, context, decisions needed, and action-item template."),
    ("sanitize", "Sanitize sensitive content", "Apply configured redaction and privacy constraints before output."),
]
def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def _build_catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for domain_key, domain_name, archetype in _DOMAINS:
        for task_key, task_name, task_description in _TASKS:
            key = f"{domain_key}.{task_key}"
            name = f"{domain_name}: {task_name}"
            description = f"{task_description} Domain focus: {domain_name.lower()}."
            rows.append({
                "key": key,
                "slug": _slug(key),
                "name": name,
                "category": domain_key,
                "category_label": domain_name,
                "description": description,
                "skill_kind": "blueprint",
                "execution_status": "catalog_only",
                "executable": False,
                "source": {
                    "repository": UPSTREAM_REPOSITORY,
                    "kind": "curated_use_case_taxonomy",
                    "license_note": "Use-case metadata only; upstream implementation code is not copied.",
                },
                "character_profile": {
                    "archetype_key": _slug(archetype),
                    "display_role": archetype,
                    "asset_key": None,
                    "asset_status": "needs_catalog_mapping",
                },
                "runtime": {
                    "requires_approved_policy": True,
                    "requires_registered_tools": True,
                    "requires_owner_or_operator_authorization": True,
                    "default_autonomy": "approval_required",
                },
            })
    # Ensure the 21 actual upstream example names appear as discoverable records while
    # keeping the catalog exactly 500 entries by replacing the first 21 generated rows.
    for index, (slug, name, category, description) in enumerate(_UPSTREAM_EXAMPLES):
        domain = next((d for d in _DOMAINS if d[0] == category), _DOMAINS[0])
        rows[index] = {
            **rows[index],
            "key": f"upstream.{slug}",
            "slug": slug,
            "name": name,
            "category": category,
            "category_label": domain[1],
            "description": description,
            "source": {
                "repository": UPSTREAM_REPOSITORY,
                "path": f"agents/{index + 1:02d}-{slug}",
                "kind": "repository_agent_example",
                "license_note": "Repository metadata reference only; no upstream code is executed by this catalog.",
            },
            "character_profile": {
                "archetype_key": _slug(domain[2]),
                "display_role": domain[2],
                "asset_key": None,
                "asset_status": "needs_catalog_mapping",
            },
        }
    return rows

SKILL_CATALOG = tuple(_build_catalog())
SKILL_CATALOG_BY_KEY = {item["key"]: item for item in SKILL_CATALOG}
SKILL_CATALOG_CATEGORIES = tuple(
    {"key": key, "label": label, "count": sum(1 for item in SKILL_CATALOG if item["category"] == key)}
    for key, label, _ in _DOMAINS
)

def search_skill_catalog(*, q: str = "", category: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Search catalog metadata only; catalog membership does not grant execution."""
    query = q.strip().casefold()
    selected = [
        item for item in SKILL_CATALOG
        if (not category or item["category"] == category)
        and (not query or query in item["name"].casefold()
             or query in item["description"].casefold()
             or query in item["key"].casefold())
    ]
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    return {
        "items": list(selected[safe_offset:safe_offset + safe_limit]),
        "total": len(selected),
        "limit": safe_limit,
        "offset": safe_offset,
        "categories": list(SKILL_CATALOG_CATEGORIES),
        "catalog_version": "allpha-skill-catalog-v1",
        "executable_count": sum(1 for item in selected if item["executable"]),
    }
