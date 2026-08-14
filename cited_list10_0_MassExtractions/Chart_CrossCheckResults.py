from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "CrossCheckResults(2)"
DEFAULT_OUTPUT = SCRIPT_DIR / "CrossCheckResultsCharts"
DEFAULT_CITED_LIST = SCRIPT_DIR.parent / "cited_list10_0.json"

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"]
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

COMBO_LABELS = [
    "DOITest=True\nTitleTest=True",
    "DOITest=False\nTitleTest=False",
    "DOITest=True\nTitleTest=False",
    "DOITest=False\nTitleTest=True",
]
COMBO_KEYS = ["TT", "FF", "TF", "FT"]
COMBO_COLORS = ["#1f77b4", "#ff7f0e", "#9467bd", "#17becf"]

CONTAINER_KEYS = ["TRUE", "FALSE", "NULL"]
CONTAINER_COLORS = ["#4c78a8", "#f58518", "#b279a2"]


def load_json(path: Path) -> Dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def iter_crosscheck_files(path: Path) -> List[Path]:
    if path.is_file() and path.suffix.lower() == ".json":
        return [path]
    if path.is_dir():
        return sorted(
            item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".json"
        )
    return []


def contains_unstructured(value: Any) -> bool:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if "unstructured" in current:
                return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def classify_container_found(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str) and value.strip().lower() == "null":
        return "NULL"
    return "TRUE" if contains_unstructured(value) else "FALSE"


def summarize_results(results: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int], int, int, int]:
    combo_counts = {key: 0 for key in COMBO_KEYS}
    container_counts = {key: 0 for key in CONTAINER_KEYS}
    doi_and_unstructured_true_count = 0
    doi_or_title_true_count = 0

    for result in results:
        doi_test = result.get("DOITest")
        title_test = result.get("TitleTest")
        if doi_test is True and title_test is True:
            combo_counts["TT"] += 1
        elif doi_test is False and title_test is False:
            combo_counts["FF"] += 1
        elif doi_test is True and title_test is False:
            combo_counts["TF"] += 1
        elif doi_test is False and title_test is True:
            combo_counts["FT"] += 1

        container_status = classify_container_found(result.get("ContainerFound"))
        container_counts[container_status] += 1
        if doi_test is True or title_test is True:
            doi_or_title_true_count += 1
        if doi_test is True and container_status == "TRUE":
            doi_and_unstructured_true_count += 1

    return combo_counts, container_counts, len(results), doi_and_unstructured_true_count, doi_or_title_true_count


def to_percentage(count: int, total: int) -> float:
    return (count / total * 100.0) if total else 0.0


def make_dataset_label(dataset_doi: str, dataset_title: str) -> str:
    short_title = (dataset_title[:38] + "...") if len(dataset_title) > 38 else dataset_title
    return f"{dataset_doi}\n{short_title}"


def first_title(dataset_title: Any) -> str:
    if isinstance(dataset_title, list) and dataset_title:
        return str(dataset_title[0])
    if isinstance(dataset_title, str):
        return dataset_title
    return ""


def create_individual_chart(
    output_path: Path,
    dataset_doi: str,
    dataset_title: str,
    combo_counts: Dict[str, int],
    container_counts: Dict[str, int],
    total_publication_dois: int,
    doi_and_unstructured_true_count: int,
) -> None:
    fig, (ax_pie, ax_bar) = plt.subplots(1, 2, figsize=(16, 8), constrained_layout=True)

    combo_data = [
        (label, combo_counts[key], color) for label, key, color in zip(COMBO_LABELS, COMBO_KEYS, COMBO_COLORS) if combo_counts[key] > 0
    ]
    combo_values = [item[1] for item in combo_data]
    pie_labels = [f"{item[0]} ({item[1]})" for item in combo_data]
    pie_colors = [item[2] for item in combo_data]

    if sum(combo_values) == 0:
        ax_pie.axis("off")
        ax_pie.text(0.5, 0.5, "No DOITest/TitleTest results", ha="center", va="center", fontsize=14)
    else:
        ax_pie.pie(
            combo_values,
            labels=pie_labels,
            colors=pie_colors,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"fontsize": 12},
        )
        ax_pie.axis("equal")
    ax_pie.set_title("DOITest vs TitleTest", fontsize=16, pad=12)

    ax_pie.text(
        0.5,
        -0.14,
        (
            f"Total Publication DOIs: {total_publication_dois}\n"
            f'DOITest=TRUE and "unstructured"=TRUE: {doi_and_unstructured_true_count}'
        ),
        transform=ax_pie.transAxes,
        ha="center",
        va="center",
        fontsize=14,
    )

    true_count = container_counts["TRUE"]
    false_count = container_counts["FALSE"]
    null_count = container_counts["NULL"]

    bar_labels = ["True", "False", "Null"]
    bar_values = [true_count, false_count, null_count]
    bars = ax_bar.bar(bar_labels, bar_values, color=CONTAINER_COLORS)
    for bar, value in zip(bars, bar_values):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            str(value),
            ha="center",
            va="bottom",
            fontsize=14,
        )

    ax_bar.set_title('ContainerFound "unstructured" Counts', fontsize=16, pad=12)
    ax_bar.set_ylabel("Count", fontsize=13)
    ax_bar.tick_params(axis="both", labelsize=12)
    ax_bar.set_ylim(0, max(bar_values + [1]) * 1.15)

    fig.suptitle(f"{dataset_doi} | {dataset_title}", fontsize=17)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def load_cited_summary(cited_list_path: Path) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    try:
        with cited_list_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return summary

    if not isinstance(payload, list):
        return summary

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        dois = entry.get("doi")
        citation_count = entry.get("citation_count", 0)
        citation_dois = entry.get("citation_doi") or entry.get("Citation_doi") or []
        if not isinstance(citation_dois, list):
            citation_dois = []
        try:
            normalized_citation_count = int(citation_count)
        except (TypeError, ValueError):
            normalized_citation_count = 0

        if isinstance(dois, list):
            for doi in dois:
                if isinstance(doi, str):
                    summary[doi.strip().lower()] = {
                        "citation_count": normalized_citation_count,
                        "citation_doi_count": len(citation_dois),
                    }
    return summary


def create_comparison_chart(
    output_path: Path,
    dataset_rows: List[Dict[str, Any]],
    cited_summary: Dict[str, Dict[str, int]],
) -> None:
    labels = [row["dataset_label"] for row in dataset_rows]

    combo_pct = {
        key: [to_percentage(row["combo_counts"][key], row["total"]) for row in dataset_rows]
        for key in COMBO_KEYS
    }
    container_pct = {
        key: [to_percentage(row["container_counts"][key], row["total"]) for row in dataset_rows]
        for key in CONTAINER_KEYS
    }

    fig = plt.figure(figsize=(24, 18), constrained_layout=True)
    grid = fig.add_gridspec(3, 1, height_ratios=[1.5, 1.5, 1.5])

    ax_combo = fig.add_subplot(grid[0])
    ax_container = fig.add_subplot(grid[1], sharex=ax_combo)
    ax_success = fig.add_subplot(grid[2], sharex=ax_combo)

    x = list(range(len(labels)))

    ax_combo.plot(x, combo_pct["TT"], linestyle="-", marker="o", color=COMBO_COLORS[0], label="DOITest=True & TitleTest=True", markersize=12)
    ax_combo.plot(x, combo_pct["FF"], linestyle="--", marker="s", color=COMBO_COLORS[1], label="DOITest=False & TitleTest=False", markersize=12)
    ax_combo.plot(x, combo_pct["TF"], linestyle=":", marker="^", color=COMBO_COLORS[2], label="DOITest=True & TitleTest=False", markersize=12)
    ax_combo.plot(x, combo_pct["FT"], linestyle="-.", marker="d", color=COMBO_COLORS[3], label="DOITest=False & TitleTest=True", markersize=12)
    ax_combo.set_title("DOI and Title Test", fontsize=16, pad=10)
    ax_combo.set_ylabel("Percentages", fontsize=14)
    ax_combo.set_ylim(0, 100)
    ax_combo.set_yticks(range(0, 101, 20))
    ax_combo.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax_combo.tick_params(axis="both", labelsize=14)
    ax_combo.grid(axis="y", linestyle="--", alpha=0.4)
    ax_combo.legend(loc="upper right", fontsize=14)
    ax_combo.tick_params(labelbottom=False)

    ax_container.plot(x, container_pct["TRUE"], linestyle="-", marker="o", color=CONTAINER_COLORS[0], label="True", markersize=12)
    ax_container.plot(x, container_pct["FALSE"], linestyle="--", marker="s", color=CONTAINER_COLORS[1], label="False", markersize=12)
    ax_container.plot(x, container_pct["NULL"], linestyle=":", marker="^", color=CONTAINER_COLORS[2], label="Null", markersize=12)
    ax_container.set_title("Unstructured Test", fontsize=16, pad=10)
    ax_container.set_ylim(0, 100)
    ax_container.set_yticks(range(0, 101, 20))
    ax_container.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax_container.tick_params(axis="both", labelsize=14)
    ax_container.grid(axis="y", linestyle="--", alpha=0.4)
    ax_container.legend(loc="upper right", fontsize=14)
    ax_container.tick_params(labelbottom=False)

    success_rate_pct = []
    scix_detected_pct = []
    for row in dataset_rows:
        key = row["dataset_doi"].strip().lower()
        summary = cited_summary.get(key, {})
        citation_doi_count = int(summary.get("citation_doi_count", 0) or 0)
        citation_count = int(summary.get("citation_count", 0) or 0)
        success_rate_pct.append(to_percentage(row["doi_and_unstructured_true_count"], citation_doi_count))
        scix_detected_pct.append(to_percentage(citation_doi_count, citation_count))

    ax_success.plot(
        x,
        success_rate_pct,
        linestyle="-",
        marker="o",
        color="#2ca02c",
        label="Success Rate ((DOITest=True and UnstructuredTest=True) / citation_DOIs)", markersize=12
    )
    ax_success.plot(x, scix_detected_pct, linestyle="--", marker="s", color="#d62728", label="SciX DOI Detected (citation_DOIs / citation_count)", markersize=12)

    # Annotate citation_count and Citation_doi on their corresponding points
    for xi, row in enumerate(dataset_rows):
        key = row["dataset_doi"].strip().lower()
        summary = cited_summary.get(key, {})
        citation_doi_count = int(summary.get("citation_doi_count", 0) or 0)
        citation_count = int(summary.get("citation_count", 0) or 0)
        ax_success.annotate(
            f"Citation_doi={citation_doi_count}",
            xy=(xi, scix_detected_pct[xi]),
            xytext=(0, -18),
            textcoords="offset points",
            ha="center",
            fontsize=11,
            color="black",
        )
        ax_success.annotate(
            f"citation_count={citation_count}",
            xy=(xi, scix_detected_pct[xi]),
            xytext=(0, -32),
            textcoords="offset points",
            ha="center",
            fontsize=11,
            color="black",
        )
    ax_success.set_title("Success and SciX DOI Detection", fontsize=16, pad=10)
    ax_success.set_ylabel("Percentages", fontsize=13)
    ax_success.set_xlabel("Datasets", fontsize=13)
    ax_success.set_ylim(0, 100)
    ax_success.set_yticks(range(0, 101, 20))
    ax_success.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)}%"))
    ax_success.set_xticks(x)
    ax_success.set_xticklabels(labels, rotation=35, ha="right")
    ax_success.tick_params(axis="both", labelsize=14)
    ax_success.grid(axis="y", linestyle="--", alpha=0.4)
    ax_success.legend(loc="best", fontsize=14)

    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def process_all(input_path: Path, output_dir: Path, cited_list_path: Path) -> int:
    files = iter_crosscheck_files(input_path)
    if not files:
        print(f"No CrossCheckResult JSON files found at {input_path}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_rows: List[Dict[str, Any]] = []
    written = 0

    for json_file in files:
        payload = load_json(json_file)
        if payload is None:
            print(f"Skipping unreadable JSON: {json_file}")
            continue

        results_raw = payload.get("results")
        if not isinstance(results_raw, list):
            print(f"Skipping JSON without a valid results list: {json_file}")
            continue

        results = [entry for entry in results_raw if isinstance(entry, dict)]
        combo_counts, container_counts, total, doi_and_unstructured_true_count, doi_or_title_true_count = summarize_results(results)

        dataset_doi = str(payload.get("datasetDOI", json_file.stem))
        dataset_title = first_title(payload.get("datasetTitle"))

        image_path = output_dir / f"{json_file.stem}.png"
        create_individual_chart(
            image_path,
            dataset_doi,
            dataset_title,
            combo_counts,
            container_counts,
            total,
            doi_and_unstructured_true_count,
        )
        written += 1
        print(f"Wrote {image_path}")

        dataset_rows.append(
            {
                "dataset_doi": dataset_doi,
                "dataset_title": dataset_title,
                "dataset_label": make_dataset_label(dataset_doi, dataset_title),
                "combo_counts": combo_counts,
                "container_counts": container_counts,
                "total": total,
                "doi_and_unstructured_true_count": doi_and_unstructured_true_count,
            }
        )

    if dataset_rows:
        cited_summary = load_cited_summary(cited_list_path)
        comparison_path = output_dir / "Dataset_Comparison.png"
        create_comparison_chart(comparison_path, dataset_rows, cited_summary)
        print(f"Wrote {comparison_path}")

    return written


def main() -> None:
    input_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_INPUT
    output_dir = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else DEFAULT_OUTPUT
    cited_list_path = Path(sys.argv[3]).expanduser() if len(sys.argv) > 3 else DEFAULT_CITED_LIST

    written = process_all(input_path, output_dir, cited_list_path)
    print(f"Done. Created {written} individual PNG file(s) in {output_dir}")


if __name__ == "__main__":
    main()
