#!/usr/bin/env python3
"""
domain_checker.py
------------------
Generates all possible short domain names (letters + digits) of a given
length and checks their availability for one or more TLDs using RDAP
(Registration Data Access Protocol) — the modern, structured replacement
for WHOIS.

Example:
    python domain_checker.py --tlds com net --length 3 --charset alnum \
        --workers 5 --delay 0.3 --output results.csv

Only available domains are also written to available_<tld>.txt for
convenience.

NOTE ON RATE LIMITS
--------------------
RDAP registries (Verisign for .com/.net) rate-limit aggressive querying
and may temporarily block an IP that hammers them. Keep --workers low
(3-8) and use --delay to space out requests. The script writes results
incrementally so it is safe to stop (Ctrl+C) and resume later with
--resume — already-checked domains are skipped.
"""

import argparse
import csv
import itertools
import os
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from tqdm import tqdm
except ImportError:  # tqdm is optional, fall back to no progress bar
    def tqdm(iterable, **kwargs):
        return iterable

# RDAP base URLs per TLD. Verisign operates the registry RDAP service
# for .com and .net. Add more TLDs here if you extend the tool.
RDAP_ENDPOINTS = {
    "com": "https://rdap.verisign.com/com/v1/domain/{name}",
    "net": "https://rdap.verisign.com/net/v1/domain/{name}",
}

CHARSETS = {
    "letters": string.ascii_lowercase,
    "digits": string.digits,
    "alnum": string.ascii_lowercase + string.digits,
}

STATUS_AVAILABLE = "available"
STATUS_REGISTERED = "registered"
STATUS_ERROR = "error"


def build_session(retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "domain-checker/1.0 (RDAP client)"})
    return session


def check_domain(session: requests.Session, name: str, tld: str, timeout: float = 10.0) -> str:
    """Return one of STATUS_AVAILABLE / STATUS_REGISTERED / STATUS_ERROR."""
    url = RDAP_ENDPOINTS[tld].format(name=f"{name}.{tld}")
    try:
        resp = session.get(url, timeout=timeout)
    except requests.RequestException:
        return STATUS_ERROR

    if resp.status_code == 404:
        return STATUS_AVAILABLE
    if resp.status_code == 200:
        return STATUS_REGISTERED
    # 429 (rate limited) will already have been retried by the adapter;
    # anything else we can't confidently classify.
    return STATUS_ERROR


def generate_names(length: int, charset_key: str):
    chars = CHARSETS[charset_key]
    for combo in itertools.product(chars, repeat=length):
        yield "".join(combo)


def load_already_checked(path: str) -> set:
    done = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["domain"], row["tld"]))
    return done


def main():
    parser = argparse.ArgumentParser(description="Bulk short-domain RDAP availability checker.")
    parser.add_argument("--tlds", nargs="+", default=["com", "net"], choices=list(RDAP_ENDPOINTS),
                         help="TLDs to check (default: com net)")
    parser.add_argument("--length", type=int, default=3, help="Domain label length (default: 3)")
    parser.add_argument("--charset", choices=list(CHARSETS), default="alnum",
                         help="Character set: letters, digits, or alnum (default: alnum)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent requests (default: 5, keep low)")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay in seconds between task submissions")
    parser.add_argument("--output", default="results.csv", help="CSV file for full results")
    parser.add_argument("--resume", action="store_true", help="Skip domains already present in --output")
    parser.add_argument("--limit", type=int, default=None, help="Only check the first N names (for testing)")
    args = parser.parse_args()

    names = list(generate_names(args.length, args.charset))
    if args.limit:
        names = names[: args.limit]

    tasks = [(name, tld) for tld in args.tlds for name in names]

    already_done = load_already_checked(args.output) if args.resume else set()
    tasks = [t for t in tasks if t not in already_done]

    print(f"Total combinations to check: {len(tasks)} "
          f"({len(names)} names x {len(args.tlds)} TLD(s))", file=sys.stderr)

    write_header = not (args.resume and os.path.exists(args.output))
    session = build_session()

    available_files = {tld: open(f"available_{tld}.txt", "a", encoding="utf-8") for tld in args.tlds}

    with open(args.output, "a" if args.resume else "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(["domain", "tld", "status", "checked_at_utc"])

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for name, tld in tasks:
                futures[executor.submit(check_domain, session, name, tld)] = (name, tld)
                time.sleep(args.delay)  # gentle pacing on submission

            for future in tqdm(as_completed(futures), total=len(futures), desc="Checking"):
                name, tld = futures[future]
                status = future.result()
                ts = datetime.now(timezone.utc).isoformat()
                writer.writerow([name, tld, status, ts])
                csvfile.flush()
                if status == STATUS_AVAILABLE:
                    full = f"{name}.{tld}"
                    available_files[tld].write(full + "\n")
                    available_files[tld].flush()
                    print(f"AVAILABLE: {full}")

    for f in available_files.values():
        f.close()

    print("Done. Full results in", args.output, file=sys.stderr)


if __name__ == "__main__":
    main()
