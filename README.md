# Demo Document Viewer

A small Flask app to browse documents and outputs for multiple projects:

- Auditing
- Invoicing
- Smart Judge
- Prompt Enhancer

The app reads data from the local "Use Cases" folder next to `app.py` by default, with optional environment overrides.

## Quick start (Windows, cmd.exe)

1) Ensure Python 3.10+ is installed.
2) Install dependencies:

```
pip install -r requirements.txt
```

3) Run the server:

```
set FLASK_APP=app.py
python app.py
```

4) Open http://localhost:5000 in your browser.

## Project structure

Key folders and files expected by the app:

- `Use Cases/Audit/`
	- `data/<sample_id>/*.PDF`
	- `Metadata.xlsx`
	- `final_outputs.json` (optional)
- `Use Cases/Invoicing/`
	- `data/*.pdf` (each file is a sample)
	- `PO Database.xlsx` (optional, not required by the UI)
	- `final_outputs.json` (optional)
- `Use Cases/Smart Judge/`
	- `data/<sample_id>/*.pdf`
	- `metadata.json` (required for metadata lookup)
	- `final_outputs.json` (required for listing sample IDs)
- `Use Cases/Prompt Enhancer/`
	- `data/`
- `Use Cases/ADIO/`
	- `data/<sample_id>/*.pdf` (PDFs in subfolders)
	- `company_info.xlsx` (required for company information)
- `Use Cases/Emirates NBD/`
	- `data/<sample_id>/*.pdf`
	- `invoice_data.xlsx` (required for invoice data)

By default, `Use Cases` is resolved relative to `app.py`. You can override it with an environment variable.

## Configuration

Environment variables (optional):

- `USE_CASES_DIR` — Absolute or relative path to the "Use Cases" directory.
	- Example (cmd.exe):
		```
		set USE_CASES_DIR=C:\Users\a.badie\Downloads\Audit UI\Use Cases
		```

## Selecting a project

The UI supports four projects. You can switch context via a query parameter:

- `?project=audit`
- `?project=invoicing`
- `?project=smartjudge`
- `?project=promptenhancer`

Examples:

- Main page for Audit: `http://localhost:5000/`
- Main page for Invoicing: `http://localhost:5000/?project=invoicing`
- Main page for Smart Judge: `http://localhost:5000/?project=smartjudge`
- Main page for Prompt Enhancer: `http://localhost:5000/?project=promptenhancer`

## API endpoints

All endpoints accept the optional `project` query param to select context.

- `GET /api/sample/<sample_id>`
	- Audit: returns short texts from `Metadata.xlsx` and PDFs from `data/<sample_id>/`.
	- Invoicing: treats `sample_id` as a PDF filename in `data/`; returns the single file.
	- Smart Judge: returns PDFs under `data/<sample_id>/` and empty `short_texts`.
	- ADIO: returns PDFs under `data/<sample_id>/` and empty `short_texts`.
	- Emirates NBD: returns PDFs under `data/<sample_id>/` and empty `short_texts`.

- `GET /api/sample_ids`
	- Audit: distinct `Purch.Req.` values from `Metadata.xlsx`.
	- Invoicing: unique PDF filenames (case-insensitive) under `data/`.
	- Smart Judge: `sample_id` values parsed from `final_outputs.json`.
	- ADIO: folder names in `data/` directory.
	- Emirates NBD: folder names in `data/` directory.

- `GET /api/pdf/<sample_id>/<filename>`
	- Serves a PDF file.
	- Invoicing: files are flat under `data/`; uses `<filename>` directly (falls back to `<sample_id>` if needed).
	- Other projects: files are under `data/<sample_id>/`.

- `GET /api/finalOutputs/<sample_id>`
	- Returns `detailed_analysis` and `warnings` for the given sample from `final_outputs.json` in the selected project.

- `GET /api/metadata/<sample_id>`
	- Smart Judge only: returns metadata for the sample from centralized `metadata.json`.

- `GET /api/companyInfo/<sample_id>`
	- ADIO only: returns company information for the sample from `company_info.xlsx`.

- `GET /api/invoiceData/<sample_id>`
	- Emirates NBD only: returns invoice data for the sample from `invoice_data.xlsx`.

- `GET /api/projects`
	- Lists available projects and whether required files are configured/present.

## Validation rules per project

- Audit:
	- Requires: `Use Cases/Audit/data/` and `Use Cases/Audit/Metadata.xlsx`.
	- `final_outputs.json` optional.
- Invoicing:
	- Requires: `Use Cases/Invoicing/data/`.
- Smart Judge:
	- Requires: `Use Cases/Smart Judge/data/`, `Use Cases/Smart Judge/final_outputs.json`, and `Use Cases/Smart Judge/metadata.json`.
- ADIO:
	- Requires: `Use Cases/ADIO/data/` and `Use Cases/ADIO/company_info.xlsx`.
- Emirates NBD:
	- Requires: `Use Cases/Emirates NBD/data/` and `Use Cases/Emirates NBD/invoice_data.xlsx`.

## Common issues

- 404 for PDFs: verify the file casing and location. The app handles `.pdf` and `.PDF` and deduplicates case-insensitively, but paths must exist.
- Excel errors: ensure `Metadata.xlsx` has a `Purch.Req.` column and the expected sheet.
- JSON parse errors: check `final_outputs.json` and `metadata.json` for valid JSON; the app reads Final Outputs JSON with `utf-8-sig` to tolerate BOM.
- ADIO Excel format: `company_info.xlsx` must have a `sample_id` column (or variations like 'Sample ID') and should include columns for company information (e.g., `company_name`, `reporting_period`, `abu_dhabi_company_name`, `spa_effective_date`, `term_start_date`, `financial_report_url`).
- Smart Judge metadata format: `metadata.json` should be either an array of objects with `sample_id` fields, or an object with sample IDs as keys. Each entry contains metadata for one sample.

## Development notes

- App framework: Flask
- Key file: `app.py`
- Static assets: `static/`
- HTML template: `templates/index.html`

To run with debug reload:

```
set FLASK_DEBUG=1
python app.py
```

Stop the server with Ctrl+C.

## Use Cases data (private)
- Download the dataset from the private drive:
  - [Use_Cases Drive (private)](https://gccinnovative-my.sharepoint.com/:f:/g/personal/a_badie_genorplatform_onmicrosoft_com_ext__genor_com/IgBiNXsntyr3RLSVCaQ-RZAjAQPtbQPtyyNrOQyAT5g-Nzo?e=FY37eJ)
- Extract so the structure is:
  - Use Cases/
    - Audit/
    - Invoicing/
    - Smart Judge/
    - Prompt Enhancer/
- Place the "Use Cases" folder next to app.py (default), or set the environment variable:
  - Windows (PowerShell): `$env:USE_CASES_DIR="C:\path\to\Use Cases"`
  - macOS/Linux: `export USE_CASES_DIR="/path/to/Use Cases"`
- Access is restricted; ensure recipients have permission to the private link.

