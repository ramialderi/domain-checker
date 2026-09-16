#!/usr/bin/env python3
"""
rank_domains.py
----------------
Reads the "available" domain files produced by domain_checker.py
(available_com.txt / available_net.txt — one "name.tld" per line) and
scores each one on letter/digit quality, pattern, and memorability, then
maps that score to a rough suggested asking-price tier.

This is a HEURISTIC based on general domain-investing conventions (see
README for sources/reasoning). It is not an appraisal and does not
guarantee any domain will actually sell — always sanity-check top
candidates against recent comparable sales before spending real money
on registration or marketing.

Usage:
    python rank_domains.py available_com.txt available_net.txt \
        --output ranked_domains.csv

    # Only list domains worth the trouble (score >= 6):
    python rank_domains.py available_net.txt --min-score 6
"""

import argparse
import csv
import sys

# Letter quality tiers (commonly cited in domain-investing guides).
PREMIUM_LETTERS = set("abcdefghilmnoprst")
MID_LETTERS = set("jkuvw")
LOW_LETTERS = set("qxyz")

VOWELS = set("aeiou")

# Digit quality: 0 and 4 are generally the least desired (4 especially
# disliked by Chinese buyers, sounds like "death"); 8 is the most sought
# after (sounds like "prosperity"); the rest are neutral-positive.
BAD_DIGITS = {"0", "4"}
LUCKY_DIGITS = {"8"}

# Pattern quality (L=letter, N=digit), from domain-investor consensus:
# LLN > LNN ~ NLL > NNL > LNL ~ NLN. LLL/NNN included for completeness.
PATTERN_SCORE = {
    "LLL": 10,
    "LLN": 9,
    "NLL": 8,
    "LNN": 8,
    "NNL": 6,
    "LNL": 5,
    "NLN": 5,
    "NNN": 4,
}

PRICE_TIERS = [
    # (min_score, label, suggested_range_usd)
    (14, "A - ممتاز", "$300 - $1000+"),
    (9, "B - جيد", "$80 - $300"),
    (5, "C - متوسط", "$25 - $80"),
    (float("-inf"), "D - ضعيف (بالكاد يستاهل سعر التسجيل)", "$8 - $20"),
]


def classify_pattern(label: str) -> str:
    return "".join("L" if c.isalpha() else "N" for c in label)


def score_domain(label: str) -> dict:
    pattern = classify_pattern(label)
    pattern_score = PATTERN_SCORE.get(pattern, 5)

    letter_score = 0
    has_vowel = False
    for c in label:
        if c.isalpha():
            if c in PREMIUM_LETTERS:
                letter_score += 2
            elif c in MID_LETTERS:
                letter_score += 1
            elif c in LOW_LETTERS:
                letter_score -= 3
            if c in VOWELS:
                has_vowel = True

    digit_score = 0
    for c in label:
        if c.isdigit():
            if c in LUCKY_DIGITS:
                digit_score += 3
            elif c in BAD_DIGITS:
                digit_score -= 2
            else:
                digit_score += 1

    repeat_bonus = 0
    if label[0] == label[1] == label[2]:
        repeat_bonus = 3
    elif label[0] == label[1] or label[1] == label[2] or label[0] == label[2]:
        repeat_bonus = 1

    vowel_bonus = 1 if has_vowel else 0

    total = pattern_score + letter_score + digit_score + repeat_bonus + vowel_bonus

    return {
        "pattern": pattern,
        "pattern_score": pattern_score,
        "letter_score": letter_score,
        "digit_score": digit_score,
        "repeat_bonus": repeat_bonus,
        "vowel_bonus": vowel_bonus,
        "total_score": total,
    }


def price_tier(score: int):
    for min_score, label, price_range in PRICE_TIERS:
        if score >= min_score:
            return label, price_range
    return PRICE_TIERS[-1][1], PRICE_TIERS[-1][2]


def load_domains(paths):
    seen = set()
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    domain = line.strip()
                    if domain and domain not in seen:
                        seen.add(domain)
                        yield domain
        except FileNotFoundError:
            print(f"Warning: {path} not found, skipping.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Score and price-tier available short domains.")
    parser.add_argument("files", nargs="+", help="available_*.txt files to read (one domain per line)")
    parser.add_argument("--output", default="ranked_domains.csv", help="Output CSV path")
    parser.add_argument("--min-score", type=int, default=None,
                         help="Only include domains scoring at or above this total")
    args = parser.parse_args()

    rows = []
    for domain in load_domains(args.files):
        label, _, tld = domain.rpartition(".")
        if not label:
            continue
        s = score_domain(label)
        if args.min_score is not None and s["total_score"] < args.min_score:
            continue
        tier_label, price_range = price_tier(s["total_score"])
        rows.append({
            "domain": domain,
            "tld": tld,
            "pattern": s["pattern"],
            "total_score": s["total_score"],
            "price_tier": tier_label,
            "suggested_price_usd": price_range,
            "letter_score": s["letter_score"],
            "digit_score": s["digit_score"],
            "pattern_score": s["pattern_score"],
            "repeat_bonus": s["repeat_bonus"],
        })

    rows.sort(key=lambda r: r["total_score"], reverse=True)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "domain", "tld", "pattern", "total_score", "price_tier",
            "suggested_price_usd", "letter_score", "digit_score",
            "pattern_score", "repeat_bonus",
        ])
        writer.writeheader()
        writer.writerows(rows)

    a_count = sum(1 for r in rows if r["price_tier"].startswith("A"))
    b_count = sum(1 for r in rows if r["price_tier"].startswith("B"))
    print(f"Ranked {len(rows)} domains -> {args.output}", file=sys.stderr)
    print(f"Tier A (ممتاز): {a_count} | Tier B (جيد): {b_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
