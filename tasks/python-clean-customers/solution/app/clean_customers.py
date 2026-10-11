"""Clean the CRM customer export (reference solution).

Usage:
    python clean_customers.py data/customers_raw.csv out/customers_clean.csv
"""
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

COLUMNS = ["customer_id", "name", "email", "signup_date", "country", "monthly_spend_eur"]
COUNTRIES = {
    "belgium": "BE",
    "netherlands": "NL",
    "the netherlands": "NL",
    "germany": "DE",
    "france": "FR",
}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y")


def clean_id(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    return f"C{int(digits):04d}" if digits else None


def clean_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {raw!r}")


def clean_country(raw: str) -> str:
    value = " ".join(raw.split())
    if len(value) == 2:
        return value.upper()
    return COUNTRIES[value.lower()]


def clean_amount(raw: str) -> str:
    value = re.sub(r"[€\s]", "", raw or "")
    if not value:
        return ""
    if "," in value and "." in value:
        # The right-most separator is the decimal one, the other groups thousands.
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    else:
        value = value.replace(",", ".")
    return f"{float(value):.2f}"


def clean(input_path: Path, output_path: Path) -> None:
    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # header
        latest: dict[str, dict] = {}
        for row in reader:
            if not row:
                continue
            raw_id, name, email, signup, country, spend = row
            cid = clean_id(raw_id)
            if cid is None:
                continue
            latest[cid] = {  # later rows overwrite earlier ones
                "customer_id": cid,
                "name": " ".join(name.split()),
                "email": email.strip().lower(),
                "signup_date": clean_date(signup),
                "country": clean_country(country),
                "monthly_spend_eur": clean_amount(spend),
            }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for cid in sorted(latest):
            writer.writerow(latest[cid])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: clean_customers.py INPUT_CSV OUTPUT_CSV", file=sys.stderr)
        return 2
    clean(Path(argv[0]), Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
