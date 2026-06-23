"""Pitchwork Data Analyzer.

Generate a polished PDF report from the bundled Pitchfork SQLite database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "database.sqlite" / "database.sqlite"
DEFAULT_OUTPUT = ROOT / "pitchwork_analysis_report.pdf"

INK = colors.HexColor("#17212B")
MUTED = colors.HexColor("#65717E")
PAPER = colors.HexColor("#F8F5EF")
PANEL = colors.HexColor("#FFFFFF")
ACCENT = colors.HexColor("#D64550")
TEAL = colors.HexColor("#147D7E")
GOLD = colors.HexColor("#D9A441")
LINE = colors.HexColor("#DDD7CD")


@dataclass(frozen=True)
class Metric:
    label: str
    value: str
    note: str


def fetch_all(conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()) -> list[tuple]:
    return conn.execute(sql, params).fetchall()


def fetch_one(conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()) -> tuple:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise RuntimeError(f"No data returned for query: {sql}")
    return row


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def validate_database(conn: sqlite3.Connection) -> None:
    required = {"reviews", "genres", "labels", "artists", "years", "content"}
    found = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing = sorted(required - found)
    if missing:
        raise RuntimeError(f"Database is missing required tables: {', '.join(missing)}")


def format_number(value: int | float | None, digits: int = 0) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and digits:
        return f"{value:,.{digits}f}"
    return f"{value:,.0f}"


def pct(numerator: int | float, denominator: int | float) -> str:
    if not denominator:
        return "0.0%"
    return f"{(numerator / denominator) * 100:.1f}%"


def clean_label(value: object) -> str:
    if value is None or value == "":
        return "Unknown"
    return str(value).title()


def shorten(value: object, max_chars: int = 36) -> str:
    text = clean_label(value)
    return text if len(text) <= max_chars else f"{text[: max_chars - 1]}..."


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=32,
            alignment=TA_CENTER,
            textColor=INK,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            alignment=TA_CENTER,
            textColor=MUTED,
            spaceAfter=20,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.6,
            leading=13.8,
            textColor=INK,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
        "right": ParagraphStyle(
            "Right",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
            textColor=MUTED,
        ),
    }


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, stroke=0, fill=1)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.55 * inch, width - doc.rightMargin, 0.55 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(doc.leftMargin, 0.36 * inch, "Pitchwork Data Analyzer")
    canvas.drawRightString(width - doc.rightMargin, 0.36 * inch, f"Page {doc.page}")
    canvas.restoreState()


def metric_cards(metrics: Iterable[Metric]) -> Table:
    cells = []
    for metric in metrics:
        cells.append(
            [
                Paragraph(metric.value, ParagraphStyle("metric_value", fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=INK)),
                Paragraph(metric.label, ParagraphStyle("metric_label", fontName="Helvetica-Bold", fontSize=8.5, leading=10, textColor=ACCENT)),
                Paragraph(metric.note, ParagraphStyle("metric_note", fontName="Helvetica", fontSize=7.8, leading=9.5, textColor=MUTED)),
            ]
        )
    table = Table([cells], colWidths=[1.82 * inch] * len(cells), hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def data_table(headers: Sequence[str], rows: Sequence[Sequence[object]], col_widths: Sequence[float]) -> LongTable:
    table_data = [[Paragraph(str(h), ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.8, leading=9.5, textColor=colors.white)) for h in headers]]
    body_style = ParagraphStyle("td", fontName="Helvetica", fontSize=7.5, leading=9.3, textColor=INK)
    for row in rows:
        table_data.append([Paragraph(str(cell), body_style) for cell in row])
    table = LongTable(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("BACKGROUND", (0, 1), (-1, -1), PANEL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFAF7")]),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def save_bar_chart(path: Path, title: str, labels: Sequence[str], values: Sequence[float], color: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.1), dpi=170)
    fig.patch.set_facecolor("#F8F5EF")
    ax.set_facecolor("#FFFFFF")
    bars = ax.barh(range(len(labels)), values, color=color, edgecolor="#17212B", linewidth=0.3)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.invert_yaxis()
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", pad=10, color="#17212B")
    ax.tick_params(axis="x", labelsize=7, colors="#65717E")
    ax.tick_params(axis="y", colors="#17212B")
    ax.grid(axis="x", color="#DDD7CD", linewidth=0.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#DDD7CD")
    max_value = max(values) if values else 1
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + max_value * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,.1f}" if isinstance(value, float) and value % 1 else f"{value:,.0f}",
            va="center",
            fontsize=7,
            color="#65717E",
        )
    fig.tight_layout(pad=1.1)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def save_line_chart(path: Path, rows: Sequence[tuple[int, int, float]]) -> None:
    years = [row[0] for row in rows]
    counts = [row[1] for row in rows]
    scores = [row[2] for row in rows]
    fig, ax1 = plt.subplots(figsize=(7.2, 3.25), dpi=170)
    fig.patch.set_facecolor("#F8F5EF")
    ax1.set_facecolor("#FFFFFF")
    ax1.plot(years, counts, color="#147D7E", linewidth=2.0, marker="o", markersize=3.2)
    ax1.fill_between(years, counts, color="#147D7E", alpha=0.12)
    ax1.set_ylabel("Reviews", fontsize=8, color="#147D7E")
    ax1.tick_params(axis="x", labelsize=7, colors="#65717E")
    ax1.tick_params(axis="y", labelsize=7, colors="#147D7E")
    ax1.grid(axis="y", color="#DDD7CD", linewidth=0.6)
    ax2 = ax1.twinx()
    ax2.plot(years, scores, color="#D64550", linewidth=1.8, marker="s", markersize=3)
    ax2.set_ylabel("Avg score", fontsize=8, color="#D64550")
    ax2.tick_params(axis="y", labelsize=7, colors="#D64550")
    ax1.set_title("Publishing volume and average score by year", loc="left", fontsize=11, fontweight="bold", pad=10, color="#17212B")
    for ax in (ax1, ax2):
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#DDD7CD")
    fig.tight_layout(pad=1.1)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def build_story(conn: sqlite3.Connection, output: Path, max_rows: int) -> list:
    style = styles()
    total_reviews, avg_score, bnm_count, min_year, max_year = fetch_one(
        conn,
        """
        SELECT COUNT(*), AVG(score), SUM(best_new_music), MIN(pub_year), MAX(pub_year)
        FROM reviews
        """,
    )
    genre_count = fetch_one(conn, "SELECT COUNT(DISTINCT genre) FROM genres WHERE genre IS NOT NULL")[0]
    label_count = fetch_one(conn, "SELECT COUNT(DISTINCT label) FROM labels WHERE label IS NOT NULL")[0]
    author_count = fetch_one(conn, "SELECT COUNT(DISTINCT author) FROM reviews WHERE author IS NOT NULL")[0]
    top_score = fetch_one(conn, "SELECT MAX(score) FROM reviews")[0]

    genre_rows = fetch_all(
        conn,
        """
        SELECT COALESCE(g.genre, 'Unknown') AS genre,
               COUNT(*) AS reviews,
               ROUND(AVG(r.score), 2) AS avg_score,
               SUM(r.best_new_music) AS best_new_music
        FROM genres g
        JOIN reviews r USING(reviewid)
        GROUP BY COALESCE(g.genre, 'Unknown')
        ORDER BY reviews DESC
        LIMIT ?
        """,
        (max_rows,),
    )
    year_rows = fetch_all(
        conn,
        """
        SELECT pub_year, COUNT(*) AS reviews, ROUND(AVG(score), 2) AS avg_score
        FROM reviews
        WHERE pub_year IS NOT NULL
        GROUP BY pub_year
        ORDER BY pub_year
        """,
    )
    author_rows = fetch_all(
        conn,
        """
        SELECT author, COUNT(*) AS reviews, ROUND(AVG(score), 2) AS avg_score
        FROM reviews
        GROUP BY author
        ORDER BY reviews DESC, avg_score DESC
        LIMIT ?
        """,
        (max_rows,),
    )
    label_rows = fetch_all(
        conn,
        """
        SELECT label, COUNT(*) AS reviews, ROUND(AVG(r.score), 2) AS avg_score
        FROM labels l
        JOIN reviews r USING(reviewid)
        GROUP BY label
        ORDER BY reviews DESC
        LIMIT ?
        """,
        (max_rows,),
    )
    standout_rows = fetch_all(
        conn,
        """
        SELECT title, artist, score, pub_year, best_new_music
        FROM reviews
        ORDER BY score DESC, best_new_music DESC, pub_year DESC
        LIMIT ?
        """,
        (max_rows,),
    )
    content_length = fetch_one(
        conn,
        """
        SELECT ROUND(AVG(LENGTH(content)), 0), MAX(LENGTH(content))
        FROM content
        WHERE content IS NOT NULL
        """,
    )

    story = [
        Paragraph("Pitchwork Data Analysis", style["title"]),
        Paragraph(
            f"A refined, print-ready view of {format_number(total_reviews)} Pitchfork reviews "
            f"from {min_year} to {max_year}. Generated {dt.date.today().isoformat()}.",
            style["subtitle"],
        ),
        metric_cards(
            [
                Metric("Reviews", format_number(total_reviews), f"{min_year}-{max_year} coverage"),
                Metric("Average Score", format_number(avg_score, 2), f"Top observed score: {top_score:.1f}"),
                Metric("Best New Music", format_number(bnm_count), pct(bnm_count, total_reviews)),
                Metric("Genres", format_number(genre_count), f"{format_number(label_count)} labels tracked"),
            ]
        ),
        Spacer(1, 0.16 * inch),
        Paragraph("Executive Readout", style["section"]),
        Paragraph(
            f"The archive averages {avg_score:.2f} across {format_number(author_count)} critics. "
            f"Best New Music appears in {pct(bnm_count, total_reviews)} of reviews, with an average "
            f"text length of {format_number(content_length[0])} characters. The layout below keeps "
            "tables compact and lets long sections flow cleanly across pages.",
            style["body"],
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        genre_chart = tmp_path / "genres.png"
        year_chart = tmp_path / "years.png"
        author_chart = tmp_path / "authors.png"
        save_bar_chart(
            genre_chart,
            "Most reviewed genres",
            [shorten(row[0], 22) for row in genre_rows[:10]],
            [row[1] for row in genre_rows[:10]],
            "#147D7E",
        )
        save_line_chart(year_chart, year_rows)
        save_bar_chart(
            author_chart,
            "Most prolific critics",
            [shorten(row[0], 24) for row in author_rows[:10]],
            [row[1] for row in author_rows[:10]],
            "#D64550",
        )

        for image_path in (year_chart, genre_chart, author_chart):
            story.append(Spacer(1, 0.08 * inch))
            story.append(Image(str(image_path), width=6.8 * inch, height=3.05 * inch))

        story.extend(
            [
                Paragraph("Genre Performance", style["section"]),
                data_table(
                    ["Genre", "Reviews", "Avg Score", "Best New Music"],
                    [
                        [clean_label(g), format_number(c), f"{s:.2f}", format_number(b)]
                        for g, c, s, b in genre_rows
                    ],
                    [2.2 * inch, 1.05 * inch, 1.1 * inch, 1.35 * inch],
                ),
                Paragraph("Critic Activity", style["section"]),
                data_table(
                    ["Author", "Reviews", "Avg Score"],
                    [[clean_label(a), format_number(c), f"{s:.2f}"] for a, c, s in author_rows],
                    [3.0 * inch, 1.25 * inch, 1.25 * inch],
                ),
                Paragraph("Label Concentration", style["section"]),
                data_table(
                    ["Label", "Reviews", "Avg Score"],
                    [[clean_label(label), format_number(c), f"{s:.2f}"] for label, c, s in label_rows],
                    [3.0 * inch, 1.25 * inch, 1.25 * inch],
                ),
                Paragraph("Highest Scored Reviews", style["section"]),
                data_table(
                    ["Title", "Artist", "Score", "Year", "BNM"],
                    [
                        [
                            shorten(title, 34),
                            shorten(artist, 28),
                            f"{score:.1f}",
                            year,
                            "Yes" if bnm else "No",
                        ]
                        for title, artist, score, year, bnm in standout_rows
                    ],
                    [1.9 * inch, 1.8 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch],
                ),
                Spacer(1, 0.05 * inch),
                KeepTogether(
                    [
                        Paragraph("Method Notes", style["section"]),
                        Paragraph(
                            "All numbers are computed directly from the SQLite database supplied at runtime. "
                            "Charts are rendered as fixed-size images, while tables use repeating headers and "
                            "natural pagination to prevent overlapping rows or orphaned headers.",
                            style["body"],
                        ),
                    ]
                ),
            ]
        )

        doc = SimpleDocTemplate(
            str(output),
            pagesize=A4,
            rightMargin=0.55 * inch,
            leftMargin=0.55 * inch,
            topMargin=0.62 * inch,
            bottomMargin=0.72 * inch,
            title="Pitchwork Data Analysis",
            author="Pitchwork Data Analyzer",
        )
        doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)

    return story


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a polished PDF analysis report from the Pitchwork SQLite database."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to SQLite database. Default: {DEFAULT_DB}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"PDF output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=12,
        help="Maximum rows shown in each detail table.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = args.db.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    if args.max_rows < 5:
        raise ValueError("--max-rows must be at least 5")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        validate_database(conn)
        build_story(conn, output_path, args.max_rows)

    print(f"Created PDF report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
