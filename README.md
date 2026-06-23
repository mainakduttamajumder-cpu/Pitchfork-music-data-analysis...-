# Pitchwork Data Analyzer

Pitchwork Data Analyzer generates a polished PDF report from the included Pitchfork-style SQLite database. It summarizes review volume, average scores, Best New Music share, genre performance, critic activity, label concentration, and the highest scored reviews.

## Features

- Direct SQLite analysis with no manual exports required.
- Clean ReportLab PDF layout with natural pagination, repeating table headers, fixed chart sizing, and no overlapping content.
- Compact Matplotlib charts for yearly trends, top genres, and critic activity.
- Command-line options for database path, output path, and table length.

## Quick Start

Use the Windows Python launcher from this folder:

```powershell
py -m pip install -r requirements.txt
py Pitchwork_Data_Analyzer.py
```

The default output is:

```text
pitchwork_analysis_report.pdf
```

## Usage

```powershell
py Pitchwork_Data_Analyzer.py --db database.sqlite/database.sqlite --output reports/pitchwork_report.pdf --max-rows 15
```

Options:

- `--db`: Path to the SQLite database.
- `--output`: Destination PDF path.
- `--max-rows`: Maximum rows shown in each detail table. Minimum is 5.

## Data

The analyzer expects these SQLite tables:

- `reviews`
- `content`
- `artists`
- `genres`
- `labels`
- `years`

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
