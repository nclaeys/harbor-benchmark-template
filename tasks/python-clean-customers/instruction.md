# Clean the customer export

Our CRM export `data/customers_raw.csv` is messy and the finance team cannot load it.
Implement `clean_customers.py` so that

```bash
python clean_customers.py data/customers_raw.csv out/customers_clean.csv
```

reads the raw export (first argument) and writes a cleaned CSV (second argument).
Create the output's parent directory if it does not exist. Use only the Python
standard library.

## Output format

UTF-8 CSV with a header row and exactly these columns, in this order:

```
customer_id,name,email,signup_date,country,monthly_spend_eur
```

Rules:

- **customer_id**: normalize to `C` followed by the number zero-padded to 4 digits
  (`c-0003`, `C0003` and ` 3 ` all become `C0003`). Drop rows whose customer id is
  blank or contains no digits.
- **Duplicates**: if a customer id appears more than once, keep only the **last**
  occurrence in the file (later rows are corrections of earlier ones).
- **name**: strip leading/trailing whitespace and collapse runs of internal
  whitespace to a single space. Do not change the capitalization.
- **email**: strip whitespace and lowercase.
- **signup_date**: ISO format `YYYY-MM-DD`. The input contains three formats:
  `YYYY-MM-DD`, `DD/MM/YYYY` (day first, this is a European export) and
  `D Mon YYYY` (e.g. `7 Mar 2025`).
- **country**: ISO 3166-1 alpha-2 code in upper case. The input contains codes in any
  case (`be`, `BE`) and English names in any case with stray whitespace
  (`Belgium`, `The Netherlands`, `Netherlands`, `Germany`, `France`).
- **monthly_spend_eur**: a plain number with exactly two decimals (`1234.50`). The input
  may contain a `€` sign, spaces, a decimal comma (`9,99`) and European thousands
  separators (`1.234,50`). Leave the field empty when the input is empty.
- Sort the output rows by `customer_id` ascending.

The script must work on any export with the same columns, not just this file.
