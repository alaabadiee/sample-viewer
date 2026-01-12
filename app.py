import os
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, send_file, request
import json

app = Flask(__name__)

# Resolve the base "Use Cases" directory. Allow override via env var USE_CASES_DIR.
# Defaults to a folder named "Use Cases" next to this app.py file for portability.
USE_CASES_DIR = Path(
    os.getenv("USE_CASES_DIR") or (Path(__file__).resolve().parent / "Use Cases")
).resolve()

# Default configuration (Audit project)
AUDIT_DIR = USE_CASES_DIR / "Audit"
AUDIT_DATA_DIR = AUDIT_DIR / "data"
AUDIT_EXCEL_FILE = AUDIT_DIR / "Metadata.xlsx"
AUDIT_LLM_OUTPUTS = AUDIT_DIR / "LLM_outputs.json"
AUDIT_ORCHESTRATION_URL = os.getenv("AUDIT_ORCHESTRATION_URL")

# Default configuration (Antenna project)
ANTENNA_DIR = USE_CASES_DIR / "Antenna"
ANTENNA_DATA_DIR = ANTENNA_DIR / "data"
ANTENNA_EXCEL_FILE = ANTENNA_DIR / "PO Database.xlsx"
ANTENNA_LLM_OUTPUTS = ANTENNA_DIR / "LLM_outputs.json"
ANTENNA_ORCHESTRATION_URL = os.getenv("ANTENNA_ORCHESTRATION_URL")

# Default configuration (Smart Judge project)
SMART_JUDGE_DIR = USE_CASES_DIR / "Smart Judge"
SMART_JUDGE_DATA_DIR = SMART_JUDGE_DIR / "data"
SMART_JUDGE_LLM_OUTPUTS = SMART_JUDGE_DIR / "LLM_outputs.json"
SMART_JUDGE_ORCHESTRATION_URL = os.getenv("SMART_JUDGE_ORCHESTRATION_URL")

# Project registry
PROJECTS = {
    "audit": {
        "label": "Auditing",
        "data_dir": AUDIT_DATA_DIR,
        "excel_file": AUDIT_EXCEL_FILE,
        "llm_outputs": AUDIT_LLM_OUTPUTS,
        "orchestration_url": AUDIT_ORCHESTRATION_URL,
    },
    "antenna": {
        "label": "Invoice Ingestion",
        "data_dir": ANTENNA_DATA_DIR,
        "excel_file": ANTENNA_EXCEL_FILE,
        "llm_outputs": ANTENNA_LLM_OUTPUTS,
        "orchestration_url": ANTENNA_ORCHESTRATION_URL,
    },
    "smartjudge": {
        "label": "Smart Judge",
        "data_dir": SMART_JUDGE_DATA_DIR,
        "excel_file": None,
        "llm_outputs": SMART_JUDGE_LLM_OUTPUTS,
        "orchestration_url": SMART_JUDGE_ORCHESTRATION_URL,
    },
}


def _get_project_key():
    """Resolve project from query param; default to 'audit' for backward compatibility."""
    key = (request.args.get("project") or "").strip().lower()
    return key or "audit"


def _get_project_config(project_key: str):
    """Return project configuration dict and validity flag per project rules."""
    cfg = PROJECTS.get(project_key)
    if not cfg:
        return None, False, f"Unknown project '{project_key}'. Available: {', '.join(PROJECTS.keys())}"
    data_dir: Path | None = cfg.get("data_dir")
    excel_file: Path | None = cfg.get("excel_file")
    llm_outputs: Path | None = cfg.get("llm_outputs")

    missing = []
    if project_key == "audit":
        if not data_dir or not data_dir.exists():
            missing.append("data_dir")
        if not excel_file or not Path(excel_file).exists():
            missing.append("excel_file")
        # llm_outputs optional for audit
    elif project_key == "antenna":
        # Only data_dir required
        if not data_dir or not data_dir.exists():
            missing.append("data_dir")
    elif project_key == "smartjudge":
        # LLM outputs required for sample IDs; data_dir required for serving PDFs
        if not llm_outputs or not Path(llm_outputs).exists():
            missing.append("llm_outputs")
        if not data_dir or not data_dir.exists():
            missing.append("data_dir")
    else:
        # Default strict
        if not data_dir or not data_dir.exists():
            missing.append("data_dir")
        if not excel_file or not Path(excel_file).exists():
            missing.append("excel_file")

    valid = len(missing) == 0
    return cfg, valid, (f"Missing or invalid config for project '{project_key}': {', '.join(missing)}" if missing else None)


@app.route("/")
def index():
    """Render the main page"""
    return render_template("index.html")


@app.route("/api/sample/<sample_id>")
def get_sample_data(sample_id):
    """Get PDFs and purchase requisition data for a sample ID"""
    try:
        project_key = _get_project_key()
        print(f"[DEBUG] [/api/sample] project={project_key} sample_id={sample_id}")
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400

        # For Invoice Ingestion (antenna) and Smart Judge, validation is relaxed per project rules
        if project_key not in ("antenna", "smartjudge") and not valid:
            return jsonify({"error": err}), 400

        data_dir: Path = cfg.get("data_dir") if cfg else None
        if project_key == "antenna":
            # Each PDF in data folder is a sample; sample_id is the filename
            pdf_path = data_dir / str(sample_id)
            if not pdf_path.exists() or not pdf_path.is_file():
                return jsonify({"error": "Sample (PDF) not found"}), 404
            short_texts = []
            pdfs = [str(sample_id)]
            result = {
                "sample_id": sample_id,
                "short_texts": short_texts,
                "pdfs": pdfs,
                "pdf_count": len(pdfs),
                "text_count": len(short_texts),
                "project": project_key,
            }
            print(f"[DEBUG] Returning antenna result: {result['pdf_count']} PDFs, {result['text_count']} items")
            return jsonify(result)

        if project_key == "smartjudge":
            # Smart Judge: sample IDs come from LLM outputs; PDFs live under data/<sample_id>/
            short_texts: list[str] = []
            pdf_folder = data_dir / str(sample_id)
            pdfs: list[str] = []
            if pdf_folder.exists() and pdf_folder.is_dir():
                files = [f.name for f in pdf_folder.glob("*.pdf")] + [f.name for f in pdf_folder.glob("*.PDF")]
                # Deduplicate case-insensitively and sort by lowercase for stable order
                seen = set()
                pdfs = []
                for name in sorted(files, key=lambda s: s.lower()):
                    low = name.lower()
                    if low in seen:
                        continue
                    seen.add(low)
                    pdfs.append(name)
                print(f"[DEBUG] SmartJudge found {len(pdfs)} unique PDFs in {pdf_folder}")
            else:
                print(f"[DEBUG] SmartJudge PDF folder not found: {pdf_folder}")
            result = {
                "sample_id": sample_id,
                "short_texts": short_texts,
                "pdfs": pdfs,
                "pdf_count": len(pdfs),
                "text_count": len(short_texts),
                "project": project_key,
            }
            print(f"[DEBUG] Returning smartjudge result: {result['pdf_count']} PDFs, {result['text_count']} items")
            return jsonify(result)

        excel_path = cfg["excel_file"]

        # Read Excel file
        print(f"[DEBUG] Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path)
        print(f"[DEBUG] Excel loaded. Shape: {df.shape}")

        # Filter rows for this sample ID
        print(f"[DEBUG] Filtering for sample ID: {sample_id}")
        sample_data = df[df["Purch.Req."].astype(str) == str(sample_id)]
        print(f"[DEBUG] Found {len(sample_data)} matching rows")

        if sample_data.empty:
            print(f"[DEBUG] No data found for sample ID: {sample_id}")
            return jsonify({"error": "Sample ID not found"}), 404

        # Get short texts
        short_texts = sample_data["Short Text"].tolist()
        print(f"[DEBUG] Short texts count: {len(short_texts)}")

        # Get PDFs from folder
        pdf_folder = data_dir / str(sample_id)
        pdfs = []

        if pdf_folder.exists() and pdf_folder.is_dir():
            pdfs = sorted([f.name for f in pdf_folder.glob("*.PDF")])
            print(f"[DEBUG] Found {len(pdfs)} PDFs")
        else:
            print(f"[DEBUG] PDF folder not found: {pdf_folder}")

        result = {
            "sample_id": sample_id,
            "short_texts": short_texts,
            "pdfs": pdfs,
            "pdf_count": len(pdfs),
            "text_count": len(short_texts),
            "project": project_key,
        }
        print(
            f"[DEBUG] Returning result: {result['pdf_count']} PDFs, {result['text_count']} items"
        )
        return jsonify(result)

    except Exception as e:
        print(f"[ERROR] Exception in get_sample_data: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/sample_ids")
def get_sample_ids():
    """Return distinct Purchase Requisition IDs from the Excel"""
    try:
        project_key = _get_project_key()
        print(f"[DEBUG] [/api/sample_ids] project={project_key}")
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        # For Invoice Ingestion (antenna), sample IDs are filenames in data folder; Excel not required
        if project_key == "antenna":
            data_dir: Path = cfg["data_dir"]
            if not data_dir or not data_dir.exists():
                return jsonify({"error": err or "Data directory not found"}), 400
            # Collect PDF filenames (case-insensitive)
            files = [p.name for p in data_dir.glob("*.pdf")] + [p.name for p in data_dir.glob("*.PDF")]
            # Unique and sorted case-insensitively
            seen = set()
            ids_sorted = []
            for name in sorted(files, key=lambda s: s.lower()):
                low = name.lower()
                if low in seen:
                    continue
                seen.add(low)
                ids_sorted.append(name)
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        # For Smart Judge, sample IDs come from LLM_outputs.json
        if project_key == "smartjudge":
            llm_path: Path | None = cfg.get("llm_outputs")
            if not llm_path or not llm_path.exists():
                return jsonify({"error": err or "LLM outputs file not found"}), 400
            try:
                with open(llm_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except Exception as je:
                return jsonify({"error": f"Failed to parse LLM JSON: {je}"}), 500
            ids: list[str] = []
            if isinstance(data, list):
                for entry in data:
                    sid = entry.get('sample_id') if isinstance(entry, dict) else None
                    if sid is None:
                        continue
                    sid_str = str(sid).strip()
                    if sid_str:
                        ids.append(sid_str)
            # Unique and stable sort (by length then lex to group similar)
            ids_sorted = sorted(set(ids), key=lambda s: (len(s), s))
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        if not valid:
            return jsonify({"error": err}), 400

        excel_path = cfg["excel_file"]
        df = pd.read_excel(excel_path, usecols=["Purch.Req."])
        ids = (
            df["Purch.Req."].dropna().astype(str).str.strip().unique().tolist()
        )
        # Sort for stable display
        try:
            ids_sorted = sorted(ids, key=lambda x: int(x))
        except Exception:
            ids_sorted = sorted(ids)
        return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/pdf/<sample_id>/<filename>")
def get_pdf(sample_id, filename):
    """Serve PDF file"""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if not cfg.get("data_dir"):
            return jsonify({"error": err or "Data directory not found"}), 400
        data_dir: Path = cfg["data_dir"]
        if project_key == "antenna":
            # Files are flat under data_dir; prefer filename
            pdf_path = data_dir / filename
            if not pdf_path.exists():
                # Fallback to sample_id as filename in case URL used only one segment
                pdf_path = data_dir / str(sample_id)
        else:
            pdf_path = data_dir / str(sample_id) / filename
        if pdf_path.exists():
            return send_file(pdf_path, mimetype="application/pdf")
        else:
            return jsonify({"error": "PDF not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/<sample_id>")
def get_llm_outputs(sample_id):
    """Return detailed_analysis and warnings for the given Sample ID from LLM_outputs.json"""
    try:
        project_key = _get_project_key()
        cfg, _, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        llm_path: Path | None = cfg.get("llm_outputs")
        print(f"[DEBUG] LLM lookup for Sample ID: {sample_id} project={project_key}")
        if not llm_path or not llm_path.exists():
            print(f"[ERROR] LLM file not found at: {llm_path}")
            return jsonify({"error": "LLM outputs file not found"}), 404
        # Use utf-8-sig to handle potential BOM
        try:
            with open(llm_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
        except Exception as je:
            print(f"[ERROR] Failed to parse LLM JSON: {je}")
            return jsonify({"error": f"Failed to parse LLM JSON: {je}"}), 500
        # Normalize both sides to string and strip whitespace
        pr_norm = str(sample_id).strip()
        def norm(val):
            return str(val).strip() if val is not None else None
        # Find entry by sample_id
        match = next((entry for entry in data if norm(entry.get('sample_id')) == pr_norm), None)
        print(f"[DEBUG] LLM match found: {bool(match)} with data {data}")
        
        if not match:
            return jsonify({"error": "No LLM outputs for this Sample ID"}), 404
        return jsonify({
            "sample_id": sample_id,
            "detailed_analysis": match.get('detailed_analysis'),
            "warnings": match.get('warnings'),
            "project": project_key,
        })
    except Exception as e:
        print(f"[ERROR] Exception in get_llm_outputs: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/metadata/<sample_id>")
def get_metadata(sample_id: str):
    """Return metadata for Smart Judge from metadata.json under the sample folder."""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if project_key != "smartjudge":
            return jsonify({"error": "Metadata is available only for Smart Judge"}), 400
        if not valid:
            return jsonify({"error": err}), 400
        data_dir: Path = cfg["data_dir"]
        sample_dir = data_dir / str(sample_id)
        meta_file = sample_dir / "metadata.json"
        print(f"[DEBUG] Metadata lookup for Sample ID: {sample_id} in {meta_file}")
        if not sample_dir.exists() or not sample_dir.is_dir():
            return jsonify({"error": f"Sample folder not found: {sample_dir}"}), 404
        if not meta_file.exists():
            return jsonify({"error": f"metadata.json not found in {sample_dir}"}), 404
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"[DEBUG] Metadata loaded for Sample ID: {sample_id} with data {metadata}")
        except Exception as fe:
            return jsonify({"error": f"Failed to read metadata: {fe}"}), 500
        # Return as-is; could be an object or array
        return jsonify({
            "sample_id": sample_id,
            "metadata": metadata,
            "project": project_key,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects")
def list_projects():
    """List available projects and whether they are configured."""
    result = []
    for key, cfg in PROJECTS.items():
        _, valid, err = _get_project_config(key)
        result.append({
            "key": key,
            "label": cfg.get("label", key.title()),
            "configured": valid,
            "error": err,
            "orchestration": bool(cfg.get("orchestration_url")),
        })
    return jsonify({"projects": result})


@app.route("/orchestration")
def orchestration_query():
    """Redirect to orchestration using project query param."""
    key = _get_project_key()
    return orchestration(key)


@app.route("/orchestration/<project_key>")
def orchestration(project_key: str):
    """Redirect to external orchestration URL if configured, else return a simple page."""
    cfg = PROJECTS.get(project_key)
    if not cfg:
        return jsonify({"error": f"Unknown project '{project_key}'"}), 404
    url = cfg.get("orchestration_url")
    if url:
        from flask import redirect
        return redirect(url, code=302)
    # Fallback simple page
    label = cfg.get("label", project_key.title())
    return (f"<html><body style='font-family:sans-serif;padding:1rem'>"
            f"<h3>Orchestration not configured</h3>"
            f"<p>No orchestration URL is configured for project '<strong>{label}</strong>'.</p>"
            f"<p>Set environment variable <code>{project_key.upper()}_ORCHESTRATION_URL</code> and reload the app.</p>"
            f"</body></html>")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
