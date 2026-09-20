# Sales Data Cleaning Pipeline

A Python pipeline that turns messy Excel and CSV exports into one clean, validated dataset, and reports every row it could not clean instead of dropping it silently.

Built from a real client project. The client's data is not included here, so the repository ships with a sample generator that reproduces the same defects.

## The problem

Sales records had accumulated across dozens of Excel and CSV exports produced by different people over several years. The totals did not reconcile and nobody could say why.

The data had six recurring problems:

* The same customer recorded under several spellings, inflating the customer count
* Duplicate line items from files exported more than once
* Three different date formats in one column, plus Excel serial numbers that had lost their formatting
* Prices stored as text with currency symbols and thousand separators
* Region recorded as `North`, `north`, `N` and blank
* "Grand Total" rows sitting inside the data, ready to be double counted

## What the pipeline does

1. Loads every file in `data/raw` with all columns as text, so nothing is auto-converted and leading zeros survive
2. Standardises column names and maps the synonyms different exports use for the same field
3. Removes total rows, blank rows and rows without an order ID
4. Parses dates with explicit formats in passes, and converts Excel serial numbers
5. Strips currency symbols and coerces numeric fields, tracking what failed
6. Standardises regions, statuses and product names through lookup maps
7. Deduplicates on order ID plus product, which is the real unique key
8. Builds an exceptions report listing every failing row and the reason
9. Validates the output with assertions, so a bad run fails instead of shipping quietly
10. Writes a clean CSV, a formatted Excel workbook and the exceptions report

## Results on the sample data

|Stage|Rows|
|-|-|
|Loaded|421|
|Structural junk removed|1|
|Duplicates removed|71|
|Flagged for review|32|
|Clean rows written|326|

## Quick start

```bash
git clone https://github.com/heisenberg49/sales-data-cleaning-pipeline.git
cd sales-data-cleaning-pipeline

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate

pip install -r requirements.txt

python src/generate\_sample\_data.py   # creates a messy sample export
python src/clean\_sales.py            # cleans it
```

Outputs land in `data/clean/` and `reports/`.

To run it on your own data, drop your CSV or Excel files into `data/raw/` and run `python src/clean\_sales.py`. You will likely need to extend `COLUMN\_MAP` in `src/clean\_sales.py` to match your column names.

## Walkthrough notebook

`notebooks/data\_cleaning\_walkthrough.ipynb` shows the process stage by stage with outputs, including the fuzzy customer matching step that is not part of the automated script.

Customer matching is deliberately kept out of the pipeline. `rapidfuzz` generates candidate pairs above a similarity threshold, but whether "Sharma Traders" and "Sharma Trading" are the same business is a judgement call. The notebook produces a review sheet for a human to confirm, and the confirmed answers become a mapping file.

## Why the exceptions report matters

Most cleaning scripts drop bad rows. This one exports them with a reason attached:

|exception\_reason|rows|
|-|-|
|date could not be parsed|14|
|quantity missing or not numeric|10|
|negative quantity|9|

On the original project, the client's operations team worked through this file and fixed the issues in their source system. The following month's export arrived cleaner. Cleaning data helps once; telling people exactly what is broken helps permanently.

## Project structure

```
.
├── data/
│   ├── raw/          # input files, git-ignored
│   └── clean/        # outputs, git-ignored
├── notebooks/
│   └── data\_cleaning\_walkthrough.ipynb
├── reports/          # exceptions report, git-ignored
├── src/
│   ├── generate\_sample\_data.py
│   └── clean\_sales.py
├── requirements.txt
└── README.md
```

Nothing in `data/` or `reports/` is committed. Client data does not belong in a public repository.

## Design decisions worth explaining

**Load everything as text first.** Letting pandas infer types turns an order ID of `00123` into `123` and the leading zeros are gone permanently.

**Explicit date formats, never inference.** `05/04/2026` is 5 April under one convention and 4 May under another. Inference can read different rows differently, shifting data by months while everything still looks valid.

**Flag, do not drop.** A row removed without a record is a number that quietly changes. Every removal is counted in the log and every failure is listed in the exceptions report.

**Assertions before export.** A script that crashes tells you something changed upstream. A script that happily writes a smaller file tells you nothing until it is too late.

## Built with

Python, pandas, numpy, openpyxl, rapidfuzz, and the standard library `logging` module.

## Licence

MIT

