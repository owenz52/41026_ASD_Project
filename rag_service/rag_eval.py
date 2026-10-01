from pathlib import Path
import json

from rag_pipeline import (
    retrieve_context,
    answer_question,
    refresh_corpus,
)


METRICS_PATH = (
    Path(__file__).resolve().parent
    / "retrieval-metrics.md"
)


# ============================================================
# BENCHMARKS
# ============================================================

BENCHMARKS = [
    {
        "name": "course exam retrieval",
        "query": "course exams",
        "expected_source_types": {
            "database",
            "database_join",
        },
        "expected_authority": "tier_1",
        "min_relevant": 1,
    },
    {
        "name": "student count",
        "query": "student count",
        "expected_source_types": {
            "database",
        },
        "expected_authority": "tier_1",
        "required_terms": [
            "student",
        ],
        "min_relevant": 1,
    },
    {
        "name": "student exams",
        "query": "Which students have exams?",
        "expected_source_types": {
            "database",
            "database_join",
        },
        "expected_authority": "tier_1",
        "required_terms": [
            "student",
            "exam",
        ],
        "min_relevant": 1,
    },
    {
        "name": "exam schedule",
        "query": "exam schedule",
        "expected_source_types": {
            "database",
        },
        "expected_authority": "tier_1",
        "required_terms": [
            "exam",
        ],
        "min_relevant": 1,
    },
    {
        "name": "report retrieval",
        "query": "CI report status",
        "expected_source_types": {
            "report",
        },
        "expected_authority": "tier_2",
        "required_terms": [
            "report",
        ],
        "min_relevant": 1,
    },
]


# ============================================================
# HELPERS
# ============================================================

def contains_terms(
    text: str,
    terms: list[str],
) -> bool:
    """
    Require ALL terms to appear.

    This is deliberately stricter than:
        any(keyword in text)
    """

    lowered = text.lower()

    return all(
        term.lower() in lowered
        for term in terms
    )


def source_type_matches(
    result: dict,
    expected_types: set[str],
) -> bool:

    source_id = (
        result.get("source_id")
        or ""
    )

    authority = (
        result.get("authority_tier")
        or ""
    )

    text = (
        result.get("text")
        or ""
    )

    # Database chunks
    if (
        authority == "tier_1"
        and (
            "database" in source_id
            or "Student exam" in text
            or "Course exam" in text
        )
    ):
        return (
            "database"
            in expected_types
            or "database_join"
            in expected_types
        )

    # Reports
    if (
        authority == "tier_2"
        and "reports/" in source_id
    ):
        return "report" in expected_types

    return False


def evaluate_relevance(
    result: dict,
    benchmark: dict,
) -> bool:

    text = result.get(
        "text",
        "",
    )

    if not text:
        return False

    required_terms = benchmark.get(
        "required_terms",
        [],
    )

    if required_terms and not contains_terms(
        text,
        required_terms,
    ):
        return False

    expected_types = benchmark.get(
        "expected_source_types",
        set(),
    )

    if expected_types and not source_type_matches(
        result,
        expected_types,
    ):
        return False

    return True


def calculate_precision_at_k(
    relevant_count: int,
    retrieved_count: int,
    k: int,
) -> float:

    denominator = min(
        k,
        retrieved_count,
    )

    if denominator == 0:
        return 0.0

    return relevant_count / denominator


def calculate_recall_at_k(
    relevant_count: int,
    expected_relevant: int,
) -> float:

    if expected_relevant <= 0:
        return 0.0

    return min(
        1.0,
        relevant_count / expected_relevant,
    )


# ============================================================
# RETRIEVAL EVALUATION
# ============================================================

def evaluate_query(
    benchmark: dict,
    k: int = 5,
) -> dict:

    response = retrieve_context(
        benchmark["query"],
        k,
        caller="validation",
    )

    results = (
        response.get("results", [])
        if response.get("status") == "success"
        else []
    )

    relevant = [
        result
        for result in results
        if evaluate_relevance(
            result,
            benchmark,
        )
    ]

    tier_1_count = sum(
        1
        for result in results
        if result.get(
            "authority_tier"
        ) == "tier_1"
    )

    tier_2_count = sum(
        1
        for result in results
        if result.get(
            "authority_tier"
        ) == "tier_2"
    )

    expected_relevant = benchmark.get(
        "min_relevant",
        1,
    )

    precision_at_k = (
        calculate_precision_at_k(
            len(relevant),
            len(results),
            k,
        )
    )

    recall_at_k = (
        calculate_recall_at_k(
            len(relevant),
            expected_relevant,
        )
    )

    return {
        "name": benchmark["name"],
        "query": benchmark["query"],
        "retrieval_status": response.get(
            "status"
        ),
        "retrieval_mode": response.get(
            "retrieval_mode"
        ),
        "retrieved_chunk_ids": [
            result.get("chunk_id")
            for result in results
        ],
        "relevant_chunk_ids": [
            result.get("chunk_id")
            for result in relevant
        ],
        "retrieved_count": len(results),
        "relevant_count": len(relevant),
        "tier_1_count": tier_1_count,
        "tier_2_count": tier_2_count,
        "p_at_5": precision_at_k,
        "r_at_5": recall_at_k,
    }


# ============================================================
# ANSWER VALIDATION
# ============================================================

def evaluate_answer(
    query: str,
    expected_terms: list[str],
) -> dict:

    response = answer_question(
        query,
        k=5,
        caller="validation",
    )

    answer = response.get(
        "answer",
        "",
    )

    answer_lower = answer.lower()

    missing_terms = [
        term
        for term in expected_terms
        if term.lower() not in answer_lower
    ]

    return {
        "query": query,
        "status": response.get(
            "status"
        ),
        "answer": answer,
        "confidence": response.get(
            "confidence_category"
        ),
        "citation_count": len(
            response.get(
                "citations",
                [],
            )
        ),
        "missing_terms": missing_terms,
        "passed": (
            response.get("status") == "success"
            and not missing_terms
            and len(
                response.get(
                    "citations",
                    [],
                )
            ) > 0
        ),
    }


# ============================================================
# REPORT
# ============================================================

def write_metrics_report(
    retrieval_results: list[dict],
    answer_results: list[dict],
) -> None:

    lines = [
        "# Retrieval Validation",
        "",
        "## Retrieval metrics",
        "",
    ]

    for result in retrieval_results:

        lines.append(
            f"### {result['name']}"
        )

        lines.append(
            f"- Query: `{result['query']}`"
        )

        lines.append(
            f"- Retrieval status: "
            f"`{result['retrieval_status']}`"
        )

        lines.append(
            f"- Retrieval mode: "
            f"`{result['retrieval_mode']}`"
        )

        lines.append(
            f"- Retrieved: "
            f"{result['retrieved_count']}"
        )

        lines.append(
            f"- Relevant: "
            f"{result['relevant_count']}"
        )

        lines.append(
            f"- Tier 1 results: "
            f"{result['tier_1_count']}"
        )

        lines.append(
            f"- Tier 2 results: "
            f"{result['tier_2_count']}"
        )

        lines.append(
            f"- P@5: "
            f"{result['p_at_5']:.3f}"
        )

        lines.append(
            f"- R@5: "
            f"{result['r_at_5']:.3f}"
        )

        lines.append(
            f"- Retrieved chunks: "
            f"{result['retrieved_chunk_ids']}"
        )

        lines.append(
            f"- Relevant chunks: "
            f"{result['relevant_chunk_ids']}"
        )

        lines.append("")

    lines.extend(
        [
            "## Answer validation",
            "",
        ]
    )

    for result in answer_results:

        lines.append(
            f"### {result['query']}"
        )

        lines.append(
            f"- Status: "
            f"`{result['status']}`"
        )

        lines.append(
            f"- Confidence: "
            f"`{result['confidence']}`"
        )

        lines.append(
            f"- Citation count: "
            f"{result['citation_count']}"
        )

        lines.append(
            f"- Missing expected terms: "
            f"{result['missing_terms']}"
        )

        lines.append(
            f"- Passed: "
            f"`{result['passed']}`"
        )

        lines.append(
            f"- Answer: "
            f"{result['answer']}"
        )

        lines.append("")

    METRICS_PATH.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("Refreshing corpus...")

    refresh_result = refresh_corpus(
        caller="validation"
    )

    print(
        json.dumps(
            refresh_result,
            indent=2,
        )
    )

    retrieval_results = []

    for benchmark in BENCHMARKS:

        result = evaluate_query(
            benchmark,
            k=5,
        )

        retrieval_results.append(
            result
        )

        print()
        print(
            "Query:",
            result["query"],
        )

        print(
            "Mode:",
            result["retrieval_mode"],
        )

        print(
            "Retrieved:",
            result["retrieved_chunk_ids"],
        )

        print(
            "Relevant:",
            result["relevant_chunk_ids"],
        )

        print(
            "P@5:",
            result["p_at_5"],
        )

        print(
            "R@5:",
            result["r_at_5"],
        )

        print("---")

    # --------------------------------------------------------
    # ANSWER TESTS
    # --------------------------------------------------------

    answer_tests = [
        (
            "student count",
            ["student"],
        ),
        (
            "Which students have exams?",
            ["student", "exam"],
        ),
        (
            "What exams are available?",
            ["exam"],
        ),
    ]

    answer_results = []

    for query, expected_terms in answer_tests:

        result = evaluate_answer(
            query,
            expected_terms,
        )

        answer_results.append(
            result
        )

        print()
        print(
            "Answer query:",
            query,
        )

        print(
            "Passed:",
            result["passed"],
        )

        print(
            "Answer:",
            result["answer"],
        )

        print("---")

    write_metrics_report(
        retrieval_results,
        answer_results,
    )


if __name__ == "__main__":
    main()
