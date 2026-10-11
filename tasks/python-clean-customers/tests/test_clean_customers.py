"""Hidden grader for python-clean-customers.

One test per rule from the instruction, so the pytest summary line gives
partial credit (scripts/results.py reports the fraction of tests passed).
"""

EXPECTED_HEADER = ["customer_id", "name", "email", "signup_date", "country", "monthly_spend_eur"]


def test_output_header(output_header):
    assert output_header == EXPECTED_HEADER


def test_drops_blank_ids_and_duplicates(rows):
    ids = [r["customer_id"] for r in rows]
    assert len(ids) == 8, f"expected 8 customers, got {len(ids)}: {ids}"
    assert len(set(ids)) == len(ids), "duplicate customer ids in output"


def test_customer_id_format(by_id):
    assert set(by_id) == {f"C{n:04d}" for n in range(1, 9)}


def test_sorted_by_customer_id(rows):
    ids = [r["customer_id"] for r in rows]
    assert ids == sorted(ids)


def test_duplicate_keeps_last_occurrence(by_id):
    bram = by_id["C0002"]
    assert bram["email"] == "bram.peeters@new-example.com"
    assert bram["monthly_spend_eur"] == "14.99"


def test_names_whitespace(by_id):
    assert by_id["C0001"]["name"] == "Alice Janssens"
    assert by_id["C0007"]["name"] == "Gwen Dubois"
    assert by_id["C0003"]["name"] == "Chloé Martin"  # unicode preserved, case untouched


def test_emails_trimmed_and_lowercased(by_id):
    assert by_id["C0001"]["email"] == "alice.janssens@example.com"
    assert by_id["C0003"]["email"] == "chloe.martin@example.fr"


def test_unambiguous_dates_to_iso(by_id):
    assert by_id["C0001"]["signup_date"] == "2025-01-15"
    assert by_id["C0003"]["signup_date"] == "2025-03-07"   # "7 Mar 2025"
    assert by_id["C0007"]["signup_date"] == "2025-06-01"   # "1 Jun 2025"
    assert by_id["C0008"]["signup_date"] == "2025-05-25"   # "25/05/2025"


def test_slash_dates_are_day_first(by_id):
    # Easy to miss: 03/02/2025 is 3 February, not 2 March (European export).
    assert by_id["C0002"]["signup_date"] == "2025-02-03"
    assert by_id["C0005"]["signup_date"] == "2025-04-11"


def test_country_codes(by_id):
    expected = {"C0001": "BE", "C0002": "BE", "C0003": "FR", "C0004": "NL",
                "C0005": "DE", "C0006": "DE", "C0007": "FR", "C0008": "BE"}
    assert {k: v["country"] for k, v in by_id.items()} == expected


def test_spend_simple_amounts(by_id):
    assert by_id["C0001"]["monthly_spend_eur"] == "12.50"
    assert by_id["C0004"]["monthly_spend_eur"] == "45.00"
    assert by_id["C0006"]["monthly_spend_eur"] == "19.00"
    assert by_id["C0007"]["monthly_spend_eur"] == "7.50"
    assert by_id["C0008"]["monthly_spend_eur"] == "100.00"


def test_spend_european_thousands_separator(by_id):
    # Easy to miss: "€1.234,50" is one thousand two hundred thirty-four euro fifty.
    assert by_id["C0003"]["monthly_spend_eur"] == "1234.50"


def test_blank_spend_stays_blank(by_id):
    assert by_id["C0005"]["monthly_spend_eur"] == ""


def test_generalizes_to_unseen_export(hidden_rows):
    # A second export the agent never saw: guards against hard-coded answers.
    got = [tuple(r[c] for c in EXPECTED_HEADER) for r in hidden_rows]
    assert got == [
        ("C0100", "Jonas Wouters", "jonas.wouters@example.org", "2025-07-01", "BE", "3.50"),
        ("C0101", "Ines Claes", "ines.claes@example.org", "2025-06-05", "NL", "2500.00"),
        ("C0102", "Karel Smet", "karel@example.org", "2025-08-12", "BE", "0.99"),
        ("C0103", "Lotte Maes", "lotte@example.org", "2025-10-09", "DE", ""),
    ]
