"""
Create one PNG summary chart per CrossCheckResult JSON file.

The top chart counts True/False values for every boolean "*Test" field found in
the JSON's "results" entries. The bottom chart classifies "ContainerFound"
values as:
  - TRUE  : an "unstructured" field was found inside the container
  - FALSE : a non-null container exists but has no "unstructured" field
  - NULL  : the container value is the literal "null" (or missing / None)

Usage
-----
python Chart_CrossCheckResults.py
python Chart_CrossCheckResults.py /path/to/CrossCheckResults
python Chart_CrossCheckResults.py /path/to/CrossCheckResults /path/to/output_dir
python Chart_CrossCheckResults.py /path/to/file_CrossCheckResult.json
"""

from __future__ import annotations

import json
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).parent
DEFAULT_INPUT = SCRIPT_DIR / "CrossCheckResults"
DEFAULT_OUTPUT = SCRIPT_DIR / "CrossCheckResultsCharts"

Color = Tuple[int, int, int]

WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)
BLUE: Color = (66, 133, 244)
GREEN: Color = (52, 168, 83)
RED: Color = (234, 67, 53)
GRAY: Color = (120, 120, 120)
LIGHT_GRAY: Color = (220, 220, 220)

FONT: Dict[str, Sequence[str]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


class Canvas:
    def __init__(self, width: int, height: int, background: Color = WHITE) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(bytes(background) * (width * height))

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self.pixels[idx:idx + 3] = bytes(color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + width)
        y1 = min(self.height, y + height)
        for row in range(y0, y1):
            start = (row * self.width + x0) * 3
            end = (row * self.width + x1) * 3
            self.pixels[start:end] = bytes(color) * (x1 - x0)

    def draw_rect_outline(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        self.fill_rect(x, y, width, 1, color)
        self.fill_rect(x, y + height - 1, width, 1, color)
        self.fill_rect(x, y, 1, height, color)
        self.fill_rect(x + width - 1, y, 1, height, color)

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: Color) -> None:
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        while True:
            self.set_pixel(x1, y1, color)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy

    def draw_text(self, x: int, y: int, text: str, color: Color = BLACK, scale: int = 2) -> None:
        cursor_x = x
        for raw_char in text:
            char = raw_char.upper()
            glyph = FONT.get(char, FONT[" "])
            for row_index, row in enumerate(glyph):
                for col_index, bit in enumerate(row):
                    if bit == "1":
                        self.fill_rect(
                            cursor_x + col_index * scale,
                            y + row_index * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor_x += (len(glyph[0]) + 1) * scale

    def save_png(self, path: Path) -> None:
        raw = bytearray()
        row_length = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * row_length
            raw.extend(self.pixels[start:start + row_length])

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack("!I", len(data))
                + tag
                + data
                + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        ihdr = struct.pack("!IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        png = b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                chunk(b"IHDR", ihdr),
                chunk(b"IDAT", zlib.compress(bytes(raw), level=9)),
                chunk(b"IEND", b""),
            ]
        )
        path.write_bytes(png)


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def iter_crosscheck_files(path: Path) -> List[Path]:
    if path.is_file() and path.suffix.lower() == ".json":
        return [path]
    if path.is_dir():
        return sorted(
            candidate for candidate in path.iterdir()
            if candidate.is_file() and candidate.suffix.lower() == ".json"
        )
    return []


def format_test_label(name: str) -> str:
    return re.sub(
        r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])",
        " ",
        name,
    )


def collect_test_names(results: Iterable[Dict[str, Any]]) -> List[str]:
    preferred = ["DOITest", "TitleTest", "UnstructuredTest"]
    discovered = {
        key
        for result in results
        for key, value in result.items()
        if key.endswith("Test") and isinstance(value, bool)
    }
    ordered = [name for name in preferred if name in discovered]
    ordered.extend(sorted(discovered - set(ordered)))
    return ordered


def count_test_values(results: Sequence[Dict[str, Any]], test_name: str) -> Tuple[int, int]:
    true_count = sum(1 for result in results if result.get(test_name) is True)
    false_count = sum(1 for result in results if result.get(test_name) is False)
    return true_count, false_count


def contains_unstructured(value: Any) -> bool:
    if isinstance(value, dict):
        if "unstructured" in value:
            return True
        return any(contains_unstructured(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_unstructured(item) for item in value)
    return False


def classify_container_found(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str) and value.strip().lower() == "null":
        return "NULL"
    return "TRUE" if contains_unstructured(value) else "FALSE"


def count_container_found(results: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"TRUE": 0, "FALSE": 0, "NULL": 0}
    for result in results:
        status = classify_container_found(result.get("ContainerFound"))
        counts[status] += 1
    return counts


def draw_centered_text(
    canvas: Canvas,
    x: int,
    y: int,
    width: int,
    text: str,
    color: Color = BLACK,
    scale: int = 2,
) -> None:
    text_width = 0 if not text else ((len(text) - 1) * 6 + 5) * scale
    start_x = x + max(0, (width - text_width) // 2)
    canvas.draw_text(start_x, y, text, color=color, scale=scale)


def draw_legend(canvas: Canvas, x: int, y: int, items: Sequence[Tuple[str, Color]]) -> None:
    cursor_x = x
    for label, color in items:
        canvas.fill_rect(cursor_x, y + 6, 18, 18, color)
        canvas.draw_rect_outline(cursor_x, y + 6, 18, 18, BLACK)
        canvas.draw_text(cursor_x + 28, y, label, BLACK, scale=2)
        cursor_x += 28 + len(label) * 12 + 36


def draw_grouped_test_chart(
    canvas: Canvas,
    x: int,
    y: int,
    width: int,
    height: int,
    test_counts: Sequence[Tuple[str, int, int]],
) -> None:
    canvas.draw_rect_outline(x, y, width, height, LIGHT_GRAY)
    draw_centered_text(canvas, x, y + 16, width, "TEST COUNTS", scale=3)
    draw_legend(canvas, x + 24, y + 58, [("TRUE", GREEN), ("FALSE", RED)])

    plot_left = x + 70
    plot_top = y + 110
    plot_right = x + width - 30
    plot_bottom = y + height - 70
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    canvas.draw_line(plot_left, plot_top, plot_left, plot_bottom, BLACK)
    canvas.draw_line(plot_left, plot_bottom, plot_right, plot_bottom, BLACK)

    max_value = max([1] + [max(true_count, false_count) for _, true_count, false_count in test_counts])
    tick_count = min(5, max_value)
    for step in range(tick_count + 1):
        value = round(max_value * step / max(tick_count, 1))
        y_pos = plot_bottom - int(plot_height * step / max(tick_count, 1))
        canvas.draw_line(plot_left - 4, y_pos, plot_right, y_pos, LIGHT_GRAY if step else BLACK)
        canvas.draw_text(x + 8, y_pos - 7, str(value), BLACK, scale=2)

    group_count = max(1, len(test_counts))
    group_width = plot_width // group_count
    bar_width = max(24, min(64, (group_width - 36) // 2))

    for index, (test_name, true_count, false_count) in enumerate(test_counts):
        group_start = plot_left + index * group_width
        center_x = group_start + group_width // 2
        bars = [("TRUE", true_count, GREEN), ("FALSE", false_count, RED)]
        for offset, (_, count, color) in enumerate(bars):
            bar_x = center_x - bar_width - 8 if offset == 0 else center_x + 8
            bar_height = int((count / max_value) * (plot_height - 10)) if max_value else 0
            bar_y = plot_bottom - bar_height
            canvas.fill_rect(bar_x, bar_y, bar_width, bar_height, color)
            canvas.draw_rect_outline(bar_x, bar_y, bar_width, max(1, bar_height), BLACK)
            draw_centered_text(canvas, bar_x, bar_y - 24, bar_width, str(count), scale=2)

        label = format_test_label(test_name)
        draw_centered_text(canvas, group_start, plot_bottom + 16, group_width, label, scale=2)


def draw_single_bar_chart(
    canvas: Canvas,
    x: int,
    y: int,
    width: int,
    height: int,
    counts: Sequence[Tuple[str, int, Color]],
) -> None:
    canvas.draw_rect_outline(x, y, width, height, LIGHT_GRAY)
    draw_centered_text(canvas, x, y + 16, width, "CONTAINERFOUND UNSTRUCTURED", scale=3)

    plot_left = x + 70
    plot_top = y + 80
    plot_right = x + width - 30
    plot_bottom = y + height - 70
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    canvas.draw_line(plot_left, plot_top, plot_left, plot_bottom, BLACK)
    canvas.draw_line(plot_left, plot_bottom, plot_right, plot_bottom, BLACK)

    max_value = max([1] + [count for _, count, _ in counts])
    tick_count = min(5, max_value)
    for step in range(tick_count + 1):
        value = round(max_value * step / max(tick_count, 1))
        y_pos = plot_bottom - int(plot_height * step / max(tick_count, 1))
        canvas.draw_line(plot_left - 4, y_pos, plot_right, y_pos, LIGHT_GRAY if step else BLACK)
        canvas.draw_text(x + 8, y_pos - 7, str(value), BLACK, scale=2)

    bar_slot = plot_width // max(1, len(counts))
    bar_width = max(40, min(100, bar_slot // 2))
    for index, (label, count, color) in enumerate(counts):
        center_x = plot_left + index * bar_slot + bar_slot // 2
        bar_x = center_x - bar_width // 2
        bar_height = int((count / max_value) * (plot_height - 10)) if max_value else 0
        bar_y = plot_bottom - bar_height
        canvas.fill_rect(bar_x, bar_y, bar_width, bar_height, color)
        canvas.draw_rect_outline(bar_x, bar_y, bar_width, max(1, bar_height), BLACK)
        draw_centered_text(canvas, bar_x, bar_y - 24, bar_width, str(count), scale=2)
        draw_centered_text(canvas, center_x - bar_slot // 2, plot_bottom + 16, bar_slot, label, scale=2)


def create_chart(image_path: Path, source_name: str, results: Sequence[Dict[str, Any]]) -> None:
    test_names = collect_test_names(results)
    test_counts = [
        (test_name, *count_test_values(results, test_name))
        for test_name in test_names
    ]
    container_counts = count_container_found(results)

    canvas = Canvas(width=1200, height=900, background=WHITE)
    draw_centered_text(canvas, 0, 18, canvas.width, "CROSSCHECK RESULTS SUMMARY", scale=4)
    draw_centered_text(canvas, 0, 60, canvas.width, source_name.replace("_", " "), scale=2)
    canvas.draw_text(36, 108, f"RESULTS: {len(results)}", BLACK, scale=2)

    draw_grouped_test_chart(canvas, 30, 140, 1140, 420, test_counts)
    draw_single_bar_chart(
        canvas,
        30,
        590,
        1140,
        280,
        [
            ("TRUE", container_counts["TRUE"], GREEN),
            ("FALSE", container_counts["FALSE"], BLUE),
            ("NULL", container_counts["NULL"], GRAY),
        ],
    )
    canvas.save_png(image_path)


def process_file(json_path: Path, output_dir: Path) -> bool:
    payload = load_json(json_path)
    if payload is None:
        print(f"Skipping unreadable JSON: {json_path}")
        return False

    results = payload.get("results", [])
    if not isinstance(results, list):
        print(f"Skipping JSON without a valid results list: {json_path}")
        return False

    output_path = output_dir / f"{json_path.stem}.png"
    create_chart(output_path, json_path.stem, [item for item in results if isinstance(item, dict)])
    print(f"Wrote {output_path}")
    return True


def main() -> None:
    input_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_INPUT
    output_dir = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else DEFAULT_OUTPUT

    files = iter_crosscheck_files(input_path)
    if not files:
        print(f"No CrossCheckResult JSON files found at {input_path}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for json_file in files:
        if process_file(json_file, output_dir):
            written += 1

    print(f"Done. Created {written} PNG file(s) in {output_dir}")


if __name__ == "__main__":
    main()
