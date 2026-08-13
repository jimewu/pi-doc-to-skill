"""Tests for scripts/split_reference.py (verbatim chapter splitting)."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SPLITTER = REPO_ROOT / "scripts" / "split_reference.py"

SAMPLE = """\
Regulation (EU) 2017/745

CHAPTER I
CHAPTER II
ANNEX I

CHAPTER I — Scope and definitions

Article 1 — Subject matter

This Regulation lays down rules concerning medical devices.

Article 2 — Definitions

(1) 'medical device' means any instrument, apparatus, appliance, software,
implant, reagent, material or other article intended by the manufacturer.

CHAPTER II — Making available on the market

Article 5 — Placing on the market

A device may be made available on the market only if it complies.

ANNEX I — General Safety and Performance Requirements

1. General requirements

1.1. Devices shall achieve the performance intended by the manufacturer.
"""


def _run(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    src = tmp_path / "full_text.txt"
    src.write_text(SAMPLE, encoding="utf-8")
    out = tmp_path / "chapters"
    return subprocess.run(
        [sys.executable, str(SPLITTER), str(src), "-o", str(out), *extra],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_splits_by_top_level_headings(tmp_path: Path):
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    files = sorted(p.name for p in (tmp_path / "chapters").glob("*.md"))
    assert files == [
        "ch01-scope-and-definitions.md",
        "ch02-making-available-on-the-market.md",
        "ch03-general-safety-and-performance-requirements.md",
    ]


def test_skips_table_of_contents(tmp_path: Path):
    result = _run(tmp_path)
    assert result.returncode == 0
    (ch01,) = (tmp_path / "chapters").glob("ch01-*.md")
    text = ch01.read_text(encoding="utf-8")
    assert "CHAPTER I\nCHAPTER II\nANNEX I" not in text  # ToC run dropped
    assert "CHAPTER I — Scope and definitions" in text


def test_verbatim_content_preserved(tmp_path: Path):
    result = _run(tmp_path)
    assert result.returncode == 0
    (ch01,) = (tmp_path / "chapters").glob("ch01-*.md")
    text = ch01.read_text(encoding="utf-8")
    assert "implant, reagent, material or other article intended by the manufacturer." in text
    assert "(1) 'medical device' means" in text


def test_article_index_generated(tmp_path: Path):
    result = _run(tmp_path)
    assert result.returncode == 0
    (ch01,) = (tmp_path / "chapters").glob("ch01-*.md")
    text = ch01.read_text(encoding="utf-8")
    assert "**Article Index**: Articles 1–2" in text
    assert "> - Art 1 — Subject matter" in text
    assert "> - Art 2 — Definitions" in text


def test_dry_run_writes_nothing(tmp_path: Path):
    result = _run(tmp_path, "--dry-run")
    assert result.returncode == 0
    assert "BODY" in result.stdout
    assert not (tmp_path / "chapters").exists()


def test_source_banner_labeled(tmp_path: Path):
    src = tmp_path / "full_text.txt"
    src.write_text(
        "=======\nSOURCE: MDR_en.pdf (Path: /x/MDR_en.pdf)\n=======\n"
        + SAMPLE,
        encoding="utf-8",
    )
    out = tmp_path / "chapters"
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src), "-o", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    (ch01,) = out.glob("ch01-*.md")
    text = ch01.read_text(encoding="utf-8")
    assert "MDR_en.pdf" in text.splitlines()[1]  # Source: line


def test_cjk_headings(tmp_path: Path):
    src = tmp_path / "full_text.txt"
    body = (
        "第一章\n第二章\n\n"
        "第一章 — 範圍\n\n"
        "第1條 — 主旨\n\n"
        "本條例訂定醫療器材之製造、販賣及使用之規定，以保障病人、使用者"
        "及其他相關人員之健康與安全，並確保醫療器材於歐盟市場之自由流通。"
        "本條例適用於人體使用之醫療器材及其附件。本條例亦適用於體外診斷"
        "醫療器材，但其他歐盟法律另有規定者，從其規定。製造商應建立、"
        "實施並維護符合本條例之品質管理系統，以確保其產品持續符合本條例"
        "之要求，並應建立上市後監督制度，主動收集與分析其器材之使用經驗。\n\n"
        "第二章 — 上市\n\n"
        "第5條 — 上市條件\n\n"
        "器材除符合本條例之規定外，不得於市場上市或開始使用。製造商應確保"
        "其器材符合相關一般安全及性能要求，並依規定完成符合性評估程序。"
        "符合性評估應由製造商選定之驗證機構辦理，並依器材之分類決定評估"
        "程序之嚴格程度。經符合性評估後，製造商應簽署符合性宣告，並貼上"
        "CE 標誌後始得上市。\n"
    )
    src.write_text(body, encoding="utf-8")
    out = tmp_path / "chapters"
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src), "-o", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    files = sorted(out.glob("*.md"))
    assert len(files) == 2
    (ch01,) = out.glob("ch01*.md")
    text = ch01.read_text(encoding="utf-8")
    assert "第1條" in text
    assert "本條例訂定醫療器材之製造、販賣及使用之規定" in text


# ---------------------------------------------------------------------------
# Three-level progressive disclosure (indexes/ + chapters/)
# ---------------------------------------------------------------------------

LONG_SAMPLE = """\
Regulation (EU) 2017/745

CHAPTER I
CHAPTER II

CHAPTER I — Scope and definitions

Article 1 — Subject matter

This Regulation lays down rules concerning medical devices.

Article 2 — Definitions

For the purposes of this Regulation, the following definitions apply:

""" + "\n".join(
    f"({i}) 'term {i}' means a concept defined as the combination of its "
    f"essential characteristics and its intended purpose within the "
    f"regulatory framework of this Regulation."
    for i in range(1, 60)
) + """

CHAPTER II — Making available on the market

Article 5 — Placing on the market

A device may be made available on the market only if it complies.
"""


def _run_long(tmp_path: Path, *extra: str) -> subprocess.CompletedProcess:
    src = tmp_path / "full_text.txt"
    src.write_text(LONG_SAMPLE, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable, str(SPLITTER), str(src),
            "-o", str(tmp_path / "chapters"),
            "--index-dir", str(tmp_path / "indexes"),
            *extra,
        ],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_auto_split_long_chapter(tmp_path: Path):
    """Chapters over the token threshold get an L1 index + article files."""
    result = _run_long(tmp_path, "--max-chapter-tokens", "1500")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "indexes" / "ch01-index.md").is_file()
    files = sorted(p.name for p in (tmp_path / "chapters").glob("*.md"))
    assert "ch01-art-1-subject-matter.md" in files
    assert "ch01-art-2-definitions.md" in files
    # Short chapter stays a single file with no index layer.
    assert not (tmp_path / "indexes" / "ch02-index.md").exists()


def test_index_lists_article_files(tmp_path: Path):
    result = _run_long(tmp_path, "--max-chapter-tokens", "1500")
    assert result.returncode == 0
    index = (tmp_path / "indexes" / "ch01-index.md").read_text(encoding="utf-8")
    assert "ch01-art-1-subject-matter.md" in index
    assert "ch01-art-2-definitions.md" in index


def test_article_per_file_preserves_items(tmp_path: Path):
    result = _run_long(tmp_path, "--max-chapter-tokens", "1500")
    assert result.returncode == 0
    art2 = (tmp_path / "chapters" / "ch01-art-2-definitions.md").read_text(encoding="utf-8")
    assert "(1) 'term 1'" in art2
    assert "(59) 'term 59'" in art2


def test_oversized_article_split_by_items(tmp_path: Path):
    result = _run_long(tmp_path, "--max-chapter-tokens", "1500", "--max-file-tokens", "500")
    assert result.returncode == 0
    parts = sorted((tmp_path / "chapters").glob("ch01-art-2-part-*.md"))
    assert len(parts) >= 2
    first = parts[0].read_text(encoding="utf-8")
    assert "(1) 'term 1'" in first


def test_topic_clusters(tmp_path: Path):
    clusters = tmp_path / "clusters.yaml"
    clusters.write_text(
        "clusters:\n"
        "  - chapter: 1\n"
        "    clusters:\n"
        "      - file: ch01-defs-first\n"
        "        label: \"first twenty\"\n"
        "        parts: [\"art-2:1-20\"]\n"
        "      - file: ch01-defs-rest\n"
        "        label: \"the rest\"\n"
        "        parts: [\"art-2:21-59\"]\n",
        encoding="utf-8",
    )
    result = _run_long(
        tmp_path, "--max-chapter-tokens", "1500", "--clusters-file", str(clusters)
    )
    assert result.returncode == 0, result.stderr
    first = (tmp_path / "chapters" / "ch01-defs-first.md").read_text(encoding="utf-8")
    rest = (tmp_path / "chapters" / "ch01-defs-rest.md").read_text(encoding="utf-8")
    assert "(1) 'term 1'" in first and "(20) 'term 20'" in first
    assert "(21) 'term 21'" in rest and "(59) 'term 59'" in rest
    assert "(21) 'term 21'" not in first
    assert "(20) 'term 20'" not in rest
    index = (tmp_path / "indexes" / "ch01-index.md").read_text(encoding="utf-8")
    assert "ch01-defs-first.md" in index and "first twenty" in index


def test_granularity_chapter_keeps_single_files(tmp_path: Path):
    result = _run_long(
        tmp_path, "--max-chapter-tokens", "1500", "--granularity", "chapter"
    )
    assert result.returncode == 0
    assert not (tmp_path / "indexes").exists()
    files = sorted(p.name for p in (tmp_path / "chapters").glob("*.md"))
    assert "ch01-scope-and-definitions.md" in files


# ---------------------------------------------------------------------------
# Annex structure handling (annex-internal CHAPTERs, italic headings, item fallback)
# ---------------------------------------------------------------------------

ANNEX_SAMPLE = """\
Regulation (EU) 2017/745

CHAPTER I
*ANNEX I*

CHAPTER I — Scope

Article 1 — Subject matter

This Regulation lays down rules concerning the placing on the market, making\
available on the market or putting into service of medical devices for human use\
and accessories for such devices in the Union. It shall also apply to clinical\
investigations concerning such devices and accessories conducted in the Union.\
The Regulation establishes high standards of quality and safety for medical\
devices, addressing common safety concerns for such devices, and reinforces\
transparency with regard to medical devices, in particular through EUDAMED.\n\n*ANNEX I*\n\n**GENERAL SAFETY AND PERFORMANCE REQUIREMENTS**\n\nCHAPTER I\n\nGENERAL REQUIREMENTS\n\n1. Devices shall achieve the performance intended by their manufacturer and\nshall be designed and manufactured in such a way that, during normal conditions\nof use, they are suitable for their intended purpose. They shall be safe and\neffective and shall not compromise the clinical condition or the safety of\npatients, or the safety and health of users or, where applicable, other persons.\n2. The manufacturer shall implement a risk management system, understood as a\ncontinuous iterative process throughout the entire lifecycle of the device.\n\nCHAPTER II\n\nREQUIREMENTS REGARDING DESIGN\n\n1. Devices shall be designed to reduce risks as far as possible, taking into\naccount the generally acknowledged state of the art, and shall be manufactured\nin such a way as to remove or reduce as far as possible the risk of injury.\n2. Devices shall be manufactured in a sterile condition where necessary and\nshall be packaged appropriately to maintain their characteristics during\ntransport and storage.\n"""


def test_annex_internal_chapters_not_top_level(tmp_path: Path):
    """CHAPTER headings inside an annex are not top-level chapters."""
    src = tmp_path / "full_text.txt"
    src.write_text(ANNEX_SAMPLE, encoding="utf-8")
    out = tmp_path / "chapters"
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src), "-o", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    # Top-level: Chapter I (main body) + ANNEX I. Annex-internal CHAPTER I/II
    # must NOT become ch02/ch03.
    names = sorted(p.name for p in out.glob("*.md"))
    assert len(names) == 2, names
    assert any(n.startswith("ch01-") for n in names)
    assert any(n.startswith("ch02-") and "annex" in n for n in names)


def test_long_annex_split_by_internal_chapters(tmp_path: Path):
    """A large annex with internal CHAPTER headings splits by them + gets an index."""
    src = tmp_path / "full_text.txt"
    # Make the annex long enough to exceed a low threshold.
    big = "\n\n".join(
        f"{i}. Devices shall be designed and manufactured in accordance with the "
        f"state of the art, taking into account the intended purpose, the risks "
        f"associated with the device and the clinical benefit to be achieved."
        for i in range(1, 60)
    )
    art1 = (
        "This Regulation lays down rules concerning medical devices and their "
        "accessories. It shall also apply to clinical investigations concerning "
        "such devices and accessories conducted in the Union, and to the free "
        "movement of devices in the internal market. The objectives of this "
        "Regulation are to ensure the safe and effective use of medical devices. "
        "The Regulation establishes high standards of quality and safety for "
        "medical devices, addressing common safety concerns for such devices. "
        "The Regulation reinforces the transparency with regard to medical devices."
    )
    text = (
        "CHAPTER I\n*ANNEX I*\n\nCHAPTER I — Scope\n\nArticle 1 — Subject matter\n\n"
        + art1 + "\n\n"
        "*ANNEX I*\n\n**GENERAL SAFETY AND PERFORMANCE REQUIREMENTS**\n\n"
        "CHAPTER I\n\nGENERAL REQUIREMENTS\n\n" + big + "\n"
    )
    src.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src),
         "-o", str(tmp_path / "chapters"), "--index-dir", str(tmp_path / "indexes"),
         "--max-chapter-tokens", "1500"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "indexes" / "ch02-index.md").is_file()
    annex_files = sorted(p.name for p in (tmp_path / "chapters").glob("ch02-*.md"))
    assert len(annex_files) >= 1
    first = (tmp_path / "chapters" / annex_files[0]).read_text(encoding="utf-8")
    assert "GENERAL REQUIREMENTS" in first


def test_annex_without_sections_falls_back_to_items(tmp_path: Path):
    """An annex with numbered items but no internal CHAPTER splits by items."""
    src = tmp_path / "full_text.txt"
    art1 = (
        "This Regulation lays down rules concerning medical devices and their "
        "accessories. It shall also apply to clinical investigations concerning "
        "such devices and accessories conducted in the Union, and to the free "
        "movement of devices in the internal market. The objectives of this "
        "Regulation are to ensure the safe and effective use of medical devices "
        "and to establish high standards of quality and safety for such devices. "
        "The Regulation reinforces transparency with regard to medical devices."
    )
    text = (
        "CHAPTER I\n*ANNEX VII*\n\nCHAPTER I — Scope\n\nArticle 1 — Subject matter\n\n"
        + art1 + "\n\n"
        "*ANNEX VII*\n\n**TECHNICAL DOCUMENTATION**\n\n"
        "1. ORGANISATIONAL AND GENERAL REQUIREMENTS\n\n"
        "The manufacturer shall establish, document, implement and maintain a "
        "quality management system that ensures compliance with this Regulation, "
        "in a manner that is proportionate to the risk class and the size of the "
        "undertaking. The quality management system shall cover the organisational "
        "structure, responsibilities and procedures of the manufacturer.\n\n"
        "2. QUALITY MANAGEMENT REQUIREMENTS\n\n"
        "The quality management system shall address the documentation, records, "
        "change control and audit requirements applicable to the manufacturer. "
        "The manufacturer shall keep the technical documentation and other "
        "relevant records available for the competent authorities.\n"
    )
    src.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src),
         "-o", str(tmp_path / "chapters"), "--index-dir", str(tmp_path / "indexes"),
         "--granularity", "article"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    item_files = sorted((tmp_path / "chapters").glob("ch02-item-*.md"))
    assert len(item_files) == 2, [p.name for p in (tmp_path / "chapters").glob("ch02*")]
    assert (tmp_path / "indexes" / "ch02-index.md").is_file()


# ---------------------------------------------------------------------------
# Item heading refinement (numbered paragraphs vs headings; annex grouping)
# ---------------------------------------------------------------------------

def test_numbered_paragraphs_not_items(tmp_path: Path):
    """Long numbered paragraphs like '1.1.1. Each notified body shall ...' are
    body text, not item headings."""
    src = tmp_path / "full_text.txt"
    text = (
        "CHAPTER I\n*ANNEX I*\n\nCHAPTER I — Scope\n\nArticle 1 — Subject matter\n\n"
        "This Regulation lays down rules concerning medical devices and their "
        "accessories. It shall also apply to clinical investigations concerning "
        "such devices and accessories conducted in the Union, and to the free "
        "movement of devices in the internal market. The Regulation establishes "
        "high standards of quality and safety for medical devices, addressing "
        "common safety concerns for such devices.\n\n"
        "*ANNEX VII*\n\n**TECHNICAL DOCUMENTATION**\n\n"
        "### 1. ORGANISATIONAL AND GENERAL REQUIREMENTS\n\n"
        "1.1. Legal status and organisational structure\n\n"
        "1.1.1. Each notified body shall be established under the national law "
        "of a Member State, or under the law of a third country with which the "
        "Union has concluded an agreement in this respect. Its legal personality "
        "and status shall be fully documented. Such documentation shall include "
        "information about ownership and the legal or natural persons exercising "
        "control over the notified body.\n\n"
        "1.1.2. If the notified body is a legal entity that is part of a larger "
        "organisation, the activities of that organisation as well as its "
        "organisational structure and governance shall be clearly documented.\n\n"
        "### 2. QUALITY MANAGEMENT REQUIREMENTS\n\n"
        "2.1. The quality management system shall cover the organisational "
        "structure, responsibilities and procedures of the manufacturer.\n"
    )
    src.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src),
         "-o", str(tmp_path / "chapters"), "--index-dir", str(tmp_path / "indexes"),
         "--granularity", "article"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    # Annex VII splits by main numbered sections (1, 2), not by 1.1.1. paragraphs.
    files = sorted(p.name for p in (tmp_path / "chapters").glob("ch02-*.md"))
    assert "ch02-item-1.md" in files and "ch02-item-2.md" in files
    assert len(files) == 2, files
    item1 = (tmp_path / "chapters" / "ch02-item-1.md").read_text(encoding="utf-8")
    assert "1.1. Legal status and organisational structure" in item1
    assert "1.1.1. Each notified body shall be established" in item1
    assert "1.1.2. If the notified body is a legal entity" in item1
    assert "QUALITY MANAGEMENT" not in item1


def test_index_has_topics_table(tmp_path: Path):
    """L1 index files carry an empty Topics table for the agent to fill."""
    src = tmp_path / "full_text.txt"
    text = (
        "CHAPTER I\n\nCHAPTER I — Scope\n\nArticle 1 — Subject matter\n\n"
        "This Regulation lays down rules concerning medical devices and their "
        "accessories, and applies to clinical investigations concerning such "
        "devices. The Regulation establishes high standards of quality and "
        "safety for medical devices, addressing common safety concerns.\n\n"
        "Article 2 — Definitions\n\n"
        "For the purposes of this Regulation, the following definitions apply:\n\n"
        + "\n\n".join(
            f"({i}) 'term {i}' means a concept defined as the combination of its "
            f"essential characteristics and its intended purpose within the "
            f"regulatory framework of this Regulation."
            for i in range(1, 40)
        ) + "\n"
    )
    src.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src),
         "-o", str(tmp_path / "chapters"), "--index-dir", str(tmp_path / "indexes"),
         "--max-chapter-tokens", "1000"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    index = (tmp_path / "indexes" / "ch01-index.md").read_text(encoding="utf-8")
    assert "## Topics" in index
    assert "| Topic | Articles → Files |" in index
    assert "## Articles" in index
    # Article titles appear in the Articles table.
    assert "Art 1 — Subject matter" in index


# ---------------------------------------------------------------------------
# PART A/B/C (letter sections) and false-positive guards
# ---------------------------------------------------------------------------

def test_letter_parts_in_annex(tmp_path: Path):
    """'PART A' / 'PART B' (letter sections) inside an annex split correctly."""
    src = tmp_path / "full_text.txt"
    part_a = (
        "INFORMATION TO BE SUBMITTED UPON THE REGISTRATION OF DEVICES\n\n"
        "Manufacturers shall submit the information referred to in Section 1 and "
        "shall ensure that the information on their devices is complete, correct "
        "and updated by the relevant party.\n\n"
        "1. Information relating to the economic operator\n\n"
        "1.1. type of economic operator (manufacturer, authorised representative "
        "or importer),\n\n1.2. name, address and contact details of the economic "
        "operator.\n\n2. Information relating to the device\n\n2.1. Basic UDI-DI,"
        "\n\n2.2. type, number and expiry date of the certificate.\n"
    )
    part_b = (
        "CORE DATA ELEMENTS TO BE PROVIDED IN THE UDI DATABASE\n\n"
        "The UDI database shall contain the core data elements relating to the "
        "identification of the device and the manufacturer or economic operator. "
        "The elements shall include the Basic UDI-DI and the UDI-DI.\n"
    )
    text = (
        "CHAPTER I\n*ANNEX VI*\n\nCHAPTER I — Scope\n\nArticle 1 — Subject matter\n\n"
        "This Regulation lays down rules concerning medical devices and their "
        "accessories. It shall also apply to clinical investigations concerning "
        "such devices and accessories conducted in the Union, and to the free "
        "movement of devices in the internal market.\n\n"
        "*ANNEX VI*\n\n**INFORMATION THAT IS TO BE SUBMITTED UPON THE "
        "REGISTRATION**\n\n## PART A\n\n" + part_a + "\n## PART B\n\n" + part_b + "\n"
    )
    src.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src),
         "-o", str(tmp_path / "chapters"), "--index-dir", str(tmp_path / "indexes"),
         "--granularity", "article"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    part_a_file = tmp_path / "chapters" / "ch02-part-a.md"
    part_b_file = tmp_path / "chapters" / "ch02-part-b.md"
    assert part_a_file.is_file(), [p.name for p in (tmp_path / "chapters").glob("ch02-*")]
    assert part_b_file.is_file()
    ta = part_a_file.read_text(encoding="utf-8")
    assert "Basic UDI-DI" in ta and "Information relating to the economic operator" in ta
    tb = part_b_file.read_text(encoding="utf-8")
    assert "CORE DATA ELEMENTS" in tb and "UDI-DI" in tb


def test_plural_annex_heading_not_annex_e(tmp_path: Path):
    """'ANNEXES' (plural) is not misread as 'ANNEX E'; 'PARTS AND COMPONENTS'
    is not misread as 'PART S'."""
    src = tmp_path / "full_text.txt"
    text = (
        "ANNEXES\n\nCHAPTER I\n\nCHAPTER I — Scope\n\nArticle 1 — Subject matter\n\n"
        "This Regulation lays down rules concerning medical devices and their "
        "accessories, and applies to clinical investigations concerning such "
        "devices. The Regulation establishes high standards of quality and "
        "safety for medical devices, addressing common safety concerns.\n\n"
        "PARTS AND COMPONENTS\n\n"
        "The manufacturer shall ensure that parts and components are identified "
        "and traceable. Systems and procedure packs shall be assembled in "
        "accordance with the requirements of this Regulation. The manufacturer "
        "shall provide the relevant information to the user.\n\n"
        "ANNEX I\n\n**GENERAL SAFETY AND PERFORMANCE REQUIREMENTS**\n\n"
        "1. Devices shall achieve the performance intended by their manufacturer "
        "and shall be designed and manufactured in such a way that, during normal "
        "conditions of use, they are suitable for their intended purpose. They "
        "shall be safe and effective and shall not compromise the clinical "
        "condition or the safety of patients.\n"
    )
    src.write_text(text, encoding="utf-8")
    out = tmp_path / "chapters"
    result = subprocess.run(
        [sys.executable, str(SPLITTER), str(src), "-o", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    names = sorted(p.name for p in out.glob("*.md"))
    # Top-level: Chapter I + ANNEX I only. No 'Part S' / 'ANNEX E' files.
    assert len(names) == 2, names
    assert not any("part-s" in n or "annex-e" in n for n in names)
    assert any("annex" in n for n in names)
