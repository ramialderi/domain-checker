# Short Domain Availability Checker

Generates every possible short domain label (letters, digits, or both) of a
given length and checks live availability for `.com` and `.net` using
**RDAP** (Registration Data Access Protocol) — the structured, machine-friendly
successor to WHOIS operated directly by the registries (Verisign for
`.com`/`.net`).

For a 3-character alphanumeric label the tool checks all `36³ = 46,656`
combinations per TLD.

## Features

- Generate combinations by charset: `letters`, `digits`, or `alnum` (both)
- Configurable label length (default `3`)
- Checks multiple TLDs in one run (`com`, `net`)
- Concurrent requests with a configurable worker pool and per-request delay
  to stay respectful of RDAP rate limits
- Automatic retries with backoff on transient errors / HTTP 429
- Results streamed to CSV as they arrive (safe to interrupt)
- `--resume` to pick up where you left off without re-checking domains
- Separate `available_com.txt` / `available_net.txt` files listing only the
  free domains found

## Installation

```bash
git clone https://github.com/<your-username>/domain-checker.git
cd domain-checker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Usage

Check all 3-character alphanumeric names for `.com` and `.net`:

```bash
python domain_checker.py --tlds com net --length 3 --charset alnum
```

Letters only, `.net` only, more conservative rate:

```bash
python domain_checker.py --tlds net --length 3 --charset letters --workers 3 --delay 0.5
```

Quick smoke test on the first 20 combinations:

```bash
python domain_checker.py --limit 20
```

Resume an interrupted run:

```bash
python domain_checker.py --tlds com net --length 3 --charset alnum --resume
```

### CLI options

| Flag         | Default      | Description                                     |
|--------------|--------------|--------------------------------------------------|
| `--tlds`     | `com net`    | TLDs to check                                    |
| `--length`   | `3`          | Label length                                     |
| `--charset`  | `alnum`      | `letters`, `digits`, or `alnum`                  |
| `--workers`  | `5`          | Concurrent requests                              |
| `--delay`    | `0.2`        | Seconds between submitting each request          |
| `--output`   | `results.csv`| Full results CSV (domain, tld, status, timestamp)|
| `--resume`   | off          | Skip domains already logged in `--output`        |
| `--limit`    | none         | Only check first N generated names (for testing) |

## Output

`results.csv`:

```
domain,tld,status,checked_at_utc
abc,com,registered,2026-09-16T12:00:00+00:00
a1z,net,available,2026-09-16T12:00:01+00:00
...
```

`available_com.txt` / `available_net.txt` — one free domain per line, e.g.:

```
a1z.net
q9x.net
```

## Running it via GitHub Actions

The repo includes `.github/workflows/domain-check.yml`, which runs the
checker on GitHub's own runners (useful if you don't want to run it
locally, or want a scheduled recurring scan).

- **Manual run**: go to the repo's **Actions** tab → **Domain Availability
  Check** → **Run workflow**, and optionally override `tlds`, `length`,
  `charset`, `workers`, `delay`, or `limit`.
- **Scheduled run**: it's set to run automatically every Monday at 03:00
  UTC. Edit or delete the `schedule:` block in the workflow file if you
  don't want that.
- **Results**: after the run finishes, download `results.csv` and
  `available_com.txt` / `available_net.txt` from the run's **Artifacts**
  section (kept for 30 days).

A full `46,656`-combination alnum scan across two TLDs is ~93k requests;
with the conservative default pacing this can take a long time, so the
workflow's job timeout is set generously (350 minutes). Narrow `--tlds`,
`--charset`, or use `--limit` for a quicker run, or run locally instead
if you need finer control.

## A note on realistic expectations

- All `17,576` pure-letter `.com` and `.net` combinations (3 letters, A–Z)
  have been registered for years — you will not find any of those free.
- Adding digits expands the space to `46,656` combinations, and mixed
  letter+digit labels are meaningfully more likely to still be unregistered,
  especially on `.net`.
- Please respect the registries' rate limits: keep `--workers` low and use
  `--delay`. Aggressive scanning can get your IP temporarily blocked.

## License

MIT
