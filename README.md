# Sample Viewer

A small Flask app to browse documents and outputs for multiple projects:

- Auditing (default)
- Invoice Ingestion (Antenna)
- Smart Judge

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
	- `LLM_outputs.json` (optional)
- `Use Cases/Antenna/`
	- `data/*.pdf` (each file is a sample)
	- `PO Database.xlsx` (optional, not required by the UI)
	- `LLM_outputs.json` (optional)
- `Use Cases/Smart Judge/`
	- `data/<sample_id>/*.pdf`
	- `data/<sample_id>/metadata.json`
	- `LLM_outputs.json` (required for listing sample IDs)

By default, `Use Cases` is resolved relative to `app.py`. You can override it with an environment variable.

## Configuration

Environment variables (optional):

- `USE_CASES_DIR` — Absolute or relative path to the "Use Cases" directory.
	- Example (cmd.exe):
		```
		set USE_CASES_DIR=C:\Users\a.badie\Downloads\Audit UI\Use Cases
		```
- `AUDIT_ORCHESTRATION_URL` — External URL to redirect for Audit orchestration.
- `ANTENNA_ORCHESTRATION_URL` — External URL to redirect for Antenna orchestration.
- `SMART_JUDGE_ORCHESTRATION_URL` — External URL to redirect for Smart Judge orchestration.

If an orchestration URL is set, visiting `/orchestration` or `/orchestration/<project>` will redirect to it. Otherwise, a simple info page is shown.

## Selecting a project

The UI supports three projects. You can switch context via a query parameter:

- `?project=audit` (default)
- `?project=antenna`
- `?project=smartjudge`

Examples:

- Main page for Audit: `http://localhost:5000/`
- Main page for Antenna: `http://localhost:5000/?project=antenna`
- Main page for Smart Judge: `http://localhost:5000/?project=smartjudge`

## API endpoints

All endpoints accept the optional `project` query param to select context.

- `GET /api/sample/<sample_id>`
	- Audit: returns short texts from `Metadata.xlsx` and PDFs from `data/<sample_id>/`.
	- Antenna: treats `sample_id` as a PDF filename in `data/`; returns the single file.
	- Smart Judge: returns PDFs under `data/<sample_id>/` and empty `short_texts`.

- `GET /api/sample_ids`
	- Audit: distinct `Purch.Req.` values from `Metadata.xlsx`.
	- Antenna: unique PDF filenames (case-insensitive) under `data/`.
	- Smart Judge: `sample_id` values parsed from `LLM_outputs.json`.

- `GET /api/pdf/<sample_id>/<filename>`
	- Serves a PDF file.
	- Antenna: files are flat under `data/`; uses `<filename>` directly (falls back to `<sample_id>` if needed).
	- Other projects: files are under `data/<sample_id>/`.

- `GET /api/llm/<sample_id>`
	- Returns `detailed_analysis` and `warnings` for the given sample from `LLM_outputs.json` in the selected project.

- `GET /api/metadata/<sample_id>`
	- Smart Judge only: returns `metadata.json` from `data/<sample_id>/`.

- `GET /api/projects`
	- Lists available projects and whether required files are configured/present.

- `GET /orchestration` and `GET /orchestration/<project>`
	- Redirect to the project's orchestration URL if configured; otherwise show a help page.

## Validation rules per project

- Audit:
	- Requires: `Use Cases/Audit/data/` and `Use Cases/Audit/Metadata.xlsx`.
	- `LLM_outputs.json` optional.
- Antenna:
	- Requires: `Use Cases/Antenna/data/` only (Excel/LLM optional).
- Smart Judge:
	- Requires: `Use Cases/Smart Judge/data/` and `Use Cases/Smart Judge/LLM_outputs.json`.

## Common issues

- 404 for PDFs: verify the file casing and location. The app handles `.pdf` and `.PDF` and deduplicates case-insensitively, but paths must exist.
- Excel errors: ensure `Metadata.xlsx` has a `Purch.Req.` column and the expected sheet.
- JSON parse errors: check `LLM_outputs.json` and `metadata.json` for valid JSON; the app reads LLM JSON with `utf-8-sig` to tolerate BOM.

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

