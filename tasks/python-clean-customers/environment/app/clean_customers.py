"""Clean the CRM customer export. See the task instruction for the rules.

Usage:
    python clean_customers.py data/customers_raw.csv out/customers_clean.csv
"""
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: clean_customers.py INPUT_CSV OUTPUT_CSV", file=sys.stderr)
        return 2
    input_path, output_path = argv
    # TODO: implement the cleaning rules.
    raise NotImplementedError("clean_customers.py is not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
