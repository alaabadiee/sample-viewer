import os
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, send_file, request
import json
import storage_handler as storage

app = Flask(__name__)

# Resolve the base "Use Cases" directory. Allow override via env var USE_CASES_DIR.
# Defaults to a folder named "Use Cases" next to this app.py file for portability.
# When using Azure, this returns a virtual path.
USE_CASES_DIR = storage.get_base_dir()

# Default configuration (Audit project)
AUDIT_DIR = USE_CASES_DIR / "Audit"
AUDIT_DATA_DIR = AUDIT_DIR / "data"
AUDIT_EXCEL_FILE = AUDIT_DIR / "Metadata.xlsx"
AUDIT_FINAL_OUTPUTS = AUDIT_DIR / "final_outputs.json"
AUDIT_ORCHESTRATION_URL = os.getenv("AUDIT_ORCHESTRATION_URL")

# Default configuration (Invoicing project)
INVOICING_DIR = USE_CASES_DIR / "Invoicing"
INVOICING_DATA_DIR = INVOICING_DIR / "data"
INVOICING_EXCEL_FILE = INVOICING_DIR / "PO Database.xlsx"
INVOICING_FINAL_OUTPUTS = INVOICING_DIR / "final_outputs.json"
INVOICING_ORCHESTRATION_URL = os.getenv("INVOICING_ORCHESTRATION_URL")

# Default configuration (Smart Judge project)
SMART_JUDGE_DIR = USE_CASES_DIR / "Smart Judge"
SMART_JUDGE_DATA_DIR = SMART_JUDGE_DIR / "data"
SMART_JUDGE_FINAL_OUTPUTS = SMART_JUDGE_DIR / "final_outputs.json"
SMART_JUDGE_ORCHESTRATION_URL = os.getenv("SMART_JUDGE_ORCHESTRATION_URL")

# Default configuration (Prompt Enhancer project)
PROMPT_ENHANCER_DIR = USE_CASES_DIR / "Prompt Enhancer"
PROMPT_ENHANCER_DATA_DIR = PROMPT_ENHANCER_DIR / "data"
PROMPT_ENHANCER_ORCHESTRATION_URL = os.getenv("PROMPT_ENHANCER_ORCHESTRATION_URL")

# Project registry
PROJECTS = {
    "audit": {
        "label": "Auditing",
        "data_dir": AUDIT_DATA_DIR,
        "excel_file": AUDIT_EXCEL_FILE,
        "final_outputs": AUDIT_FINAL_OUTPUTS,
        "orchestration_url": AUDIT_ORCHESTRATION_URL,
    },
    "invoicing": {
        "label": "Invoicing",
        "data_dir": INVOICING_DATA_DIR,
        "excel_file": INVOICING_EXCEL_FILE,
        "final_outputs": INVOICING_FINAL_OUTPUTS,
        "orchestration_url": INVOICING_ORCHESTRATION_URL,
    },
    "smartjudge": {
        "label": "Smart Judge",
        "data_dir": SMART_JUDGE_DATA_DIR,
        "excel_file": None,
        "final_outputs": SMART_JUDGE_FINAL_OUTPUTS,
        "orchestration_url": SMART_JUDGE_ORCHESTRATION_URL,
    },
    "promptenhancer": {
        "label": "Prompt Enhancer",
        "data_dir": PROMPT_ENHANCER_DATA_DIR,
        "excel_file": None,
        "final_outputs": None,
        "orchestration_url": PROMPT_ENHANCER_ORCHESTRATION_URL,
    },
}


def _get_project_key():
    """Resolve project from query param."""
    key = (request.args.get("project") or "").strip().lower()
    return key


def _get_project_config(project_key: str):
    """Return project configuration dict and validity flag per project rules."""
    cfg = PROJECTS.get(project_key)
    if not cfg:
        return None, False, f"Unknown project '{project_key}'. Available: {', '.join(PROJECTS.keys())}"
    data_dir: Path | None = cfg.get("data_dir")
    excel_file: Path | None = cfg.get("excel_file")
    final_outputs: Path | None = cfg.get("final_outputs")

    missing = []
    if project_key == "audit":
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
        if not excel_file or not storage.exists(Path(excel_file)):
            missing.append("excel_file")
        # final_outputs optional for audit
    elif project_key == "invoicing":
        # Only data_dir required
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
    elif project_key == "smartjudge":
        # Final outputs required for sample IDs; data_dir required for serving PDFs
        if not final_outputs or not storage.exists(Path(final_outputs)):
            missing.append("final_outputs")
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
    elif project_key == "promptenhancer":
        # Only data_dir required; images (PNGs) only
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
    else:
        # Default strict
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
        if not excel_file or not storage.exists(Path(excel_file)):
            missing.append("excel_file")

    valid = len(missing) == 0
    return cfg, valid, (f"Missing or invalid config for project '{project_key}': {', '.join(missing)}" if missing else None)


@app.route("/")
def index():
    """Render the main page"""
    return render_template("index.html")


@app.route("/api/sample/<sample_id>")
def get_sample_data(sample_id):
    """Get documents and data for a sample ID"""
    try:
        project_key = _get_project_key()
        print(f"[DEBUG] [/api/sample] project={project_key} sample_id={sample_id}")
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400

        # For Invoicing, Smart Judge, and Prompt Enhancer, validation is relaxed per project rules
        if project_key not in ("invoicing", "smartjudge", "promptenhancer") and not valid:
            return jsonify({"error": err}), 400

        data_dir: Path = cfg.get("data_dir") if cfg else None

        if project_key == "invoicing":
            # Each PDF in data folder is a sample; sample_id is the filename
            pdf_path = data_dir / str(sample_id)
            if not storage.exists(pdf_path) or not storage.is_file(pdf_path):
                return jsonify({"error": "Sample (PDF) not found"}), 404

            # Load items from Excel: match 'Sample ID' to sample_id and return 'Material Description'
            short_texts: list[str] = []
            excel_file: Path | None = cfg.get("excel_file")
            if excel_file and storage.exists(excel_file):
                try:
                    df = storage.read_excel_custom(excel_file)
                    # Normalize columns; support slight variations
                    cols = {c.strip().lower(): c for c in df.columns if isinstance(c, str)}
                    sample_col = cols.get("sample id")
                    material_col = cols.get("material description")
                    if sample_col and material_col:
                        sample_norm = str(sample_id).strip()
                        matches = df[df[sample_col].astype(str).str.strip() == sample_norm]
                        short_texts = matches[material_col].dropna().astype(str).tolist()
                        print(f"[DEBUG] Invoicing Excel match: {len(short_texts)} 'Material Description' items for Sample ID={sample_id}")
                    else:
                        print("[DEBUG] Invoicing Excel missing required columns 'Sample ID' and/or 'Material Description'")
                except Exception as xe:
                    print(f"[DEBUG] Failed to read Invoicing Excel for items: {xe}")
            else:
                print("[DEBUG] Invoicing Excel file not configured or missing; returning empty items list")

            pdfs = [str(sample_id)]
            result = {
                "sample_id": sample_id,
                "short_texts": short_texts,
                "pdfs": pdfs,
                "pdf_count": len(pdfs),
                "text_count": len(short_texts),
                "project": project_key,
            }
            print(f"[DEBUG] Returning invoicing result: {result['pdf_count']} PDFs, {result['text_count']} items")
            return jsonify(result)

        elif project_key == "promptenhancer":
            # Prompt Enhancer: sample IDs are image files; only PNGs, no items or final outputs
            img_path = data_dir / str(sample_id)
            if not storage.exists(img_path) or not storage.is_file(img_path):
                return jsonify({"error": "Sample (PNG) not found"}), 404
            pngs = [str(sample_id)]
            result = {
                "sample_id": sample_id,
                "short_texts": [],
                "pdfs": pngs,  # reuse field for viewer; front-end will render images
                "pdf_count": len(pngs),
                "text_count": 0,
                "project": project_key,
            }
            print(f"[DEBUG] Returning promptenhancer result: {result['pdf_count']} PNGs, no items")
            return jsonify(result)

        elif project_key == "smartjudge":
            # Smart Judge: sample IDs come from Final outputs; PDFs live under data/<sample_id>/
            short_texts: list[str] = []
            pdf_folder = data_dir / str(sample_id)
            pdfs: list[str] = []
            if storage.exists(pdf_folder):
                files = storage.glob_files(pdf_folder, "*.pdf") + storage.glob_files(pdf_folder, "*.PDF")
                # Deduplicate case-insensitively and sort by lowercase for stable order
                seen = set()
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

        # Default (Audit)
        excel_path = cfg["excel_file"]
        print(f"[DEBUG] Reading Excel file: {excel_path}")
        df = storage.read_excel_custom(excel_path)
        print(f"[DEBUG] Excel loaded. Shape: {df.shape}")
        print(f"[DEBUG] Filtering for sample ID: {sample_id}")
        sample_data = df[df["Purch.Req."].astype(str) == str(sample_id)]
        print(f"[DEBUG] Found {len(sample_data)} matching rows")
        if sample_data.empty:
            print(f"[DEBUG] No data found for sample ID: {sample_id}")
            return jsonify({"error": "Sample ID not found"}), 404
        short_texts = sample_data["Short Text"].tolist()
        print(f"[DEBUG] Short texts count: {len(short_texts)}")
        pdf_folder = data_dir / str(sample_id)
        pdfs = []
        if storage.exists(pdf_folder):
            pdfs = sorted(storage.glob_files(pdf_folder, "*.PDF"))
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
        print(f"[DEBUG] Returning result: {result['pdf_count']} PDFs, {result['text_count']} items")
        return jsonify(result)

    except Exception as e:
        print(f"[ERROR] Exception in get_sample_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/sample_ids")
def get_sample_ids():
    """Return list of sample IDs depending on project."""
    try:
        project_key = _get_project_key()
        print(f"[DEBUG] [/api/sample_ids] project={project_key}")
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400

        # Invoicing: use filenames in data_dir
        if project_key == "invoicing":
            data_dir: Path = cfg["data_dir"]
            if not data_dir or not storage.exists(data_dir):
                return jsonify({"error": err or "Data directory not found"}), 400
            files = storage.glob_files(data_dir, "*.pdf") + storage.glob_files(data_dir, "*.PDF")
            seen = set()
            ids_sorted = []
            for name in sorted(files, key=lambda s: s.lower()):
                low = name.lower()
                if low in seen:
                    continue
                seen.add(low)
                ids_sorted.append(name)
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        # Smart Judge: from final_outputs.json
        if project_key == "smartjudge":
            final_outputs_path: Path | None = cfg.get("final_outputs")
            if not final_outputs_path or not storage.exists(final_outputs_path):
                return jsonify({"error": err or "Final outputs file not found"}), 400
            try:
                data = storage.read_json(final_outputs_path)
            except Exception as je:
                return jsonify({"error": f"Failed to parse Final Outputs JSON: {je}"}), 500
            ids: list[str] = []
            if isinstance(data, list):
                for entry in data:
                    sid = entry.get('sample_id') if isinstance(entry, dict) else None
                    if sid is None:
                        continue
                    sid_str = str(sid).strip()
                    if sid_str:
                        ids.append(sid_str)
            ids_sorted = sorted(set(ids), key=lambda s: (len(s), s))
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        # Prompt Enhancer: PNG filenames in data_dir
        if project_key == "promptenhancer":
            data_dir: Path = cfg.get("data_dir")
            if not data_dir or not storage.exists(data_dir):
                return jsonify({"error": err or "Data directory not found"}), 400
            files = storage.glob_files(data_dir, "*.png") + storage.glob_files(data_dir, "*.PNG")
            seen = set()
            ids_sorted = []
            for name in sorted(files, key=lambda s: s.lower()):
                low = name.lower()
                if low in seen:
                    continue
                seen.add(low)
                ids_sorted.append(name)
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        # Default (Audit): from Excel
        if not valid:
            return jsonify({"error": err}), 400
        excel_path = cfg["excel_file"]
        df = storage.read_excel(excel_path, usecols=["Purch.Req."])
        ids = df["Purch.Req."].dropna().astype(str).str.strip().unique().tolist()
        try:
            ids_sorted = sorted(ids, key=lambda x: int(x))
        except Exception:
            ids_sorted = sorted(ids)
        return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/pdf/<sample_id>/<filename>")
def get_pdf(sample_id, filename):
    """Serve document file (PDF or image)."""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if not cfg.get("data_dir"):
            return jsonify({"error": err or "Data directory not found"}), 400
        data_dir: Path = cfg["data_dir"]

        if project_key == "invoicing":
            # Files are flat under data_dir; prefer filename
            doc_path = data_dir / filename
            if not storage.exists(doc_path):
                doc_path = data_dir / str(sample_id)
        elif project_key == "promptenhancer":
            # Flat files; serve PNG or image
            doc_path = data_dir / filename
        else:
            doc_path = data_dir / str(sample_id) / filename

        if not storage.exists(doc_path):
            return jsonify({"error": "Document not found"}), 404

        # Get the file stream (faster for Azure) or path (for local)
        file_stream = storage.get_file_stream(doc_path)
        ext = doc_path.suffix.lower()
        
        if file_stream:
            # Azure mode - stream directly from memory
            if ext == ".pdf":
                return send_file(file_stream, mimetype="application/pdf", download_name=filename)
            if ext in (".png", ".jpg", ".jpeg"):
                mt = "image/png" if ext == ".png" else "image/jpeg"
                return send_file(file_stream, mimetype=mt, download_name=filename)
            return send_file(file_stream, download_name=filename)
        else:
            # Local mode - use file path
            file_path = str(doc_path)
            if ext == ".pdf":
                return send_file(file_path, mimetype="application/pdf")
            if ext in (".png", ".jpg", ".jpeg"):
                mt = "image/png" if ext == ".png" else "image/jpeg"
                return send_file(file_path, mimetype=mt)
            return send_file(file_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/finalOutputs/<sample_id>")
def get_final_outputs(sample_id):
    """Return final outputs for the given Sample ID depending on project."""
    try:
        project_key = _get_project_key()
        cfg, _, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        print(f"[DEBUG] Final Outputs lookup for Sample ID: {sample_id} project={project_key}")

        # Prompt Enhancer: no Final outputs
        if project_key == 'promptenhancer':
            return jsonify({
                "sample_id": sample_id,
                "warnings": [],
                "project": project_key,
            })

        final_outputs_path: Path | None = cfg.get("final_outputs")
        if not final_outputs_path or not storage.exists(final_outputs_path):
            print(f"[ERROR] Final outputs file not found at: {final_outputs_path}")
            return jsonify({"error": "Final outputs file not found"}), 404

        try:
            data = storage.read_json(final_outputs_path)
        except Exception as je:
            print(f"[ERROR] Failed to parse Final Outputs JSON: {je}")
            return jsonify({"error": f"Failed to parse Final Outputs JSON: {je}"}), 500

        req_norm = str(sample_id).strip()
        if project_key == 'invoicing' and req_norm.lower().endswith('.pdf'):
            req_norm_base = req_norm[:-4]
        else:
            req_norm_base = req_norm

        def norm(val: object) -> str | None:
            if val is None:
                return None
            s = str(val).strip()
            return s[:-4] if s.lower().endswith('.pdf') else s

        match = None
        if isinstance(data, list):
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                sid = norm(entry.get('sample_id'))
                if sid == req_norm_base:
                    match = entry
                    break
        print(f"[DEBUG] Final Outputs match found (project={project_key}): {bool(match)}")

        if not match:
            return jsonify({"error": "No Final Outputs for this Sample ID"}), 404

        if project_key == 'invoicing':
            final_output = match.get('final_output')
            if isinstance(final_output, list):
                final_list = [str(x) for x in final_output]
            elif final_output is None:
                final_list = []
            else:
                final_list = [str(final_output)]
            return jsonify({
                "sample_id": sample_id,
                "final_output": final_list,
                "warnings": final_list,
                "project": project_key,
            })

        return jsonify({
            "sample_id": sample_id,
            "detailed_analysis": match.get('detailed_analysis'),
            "warnings": match.get('warnings'),
            "project": project_key,
        })
    except Exception as e:
        print(f"[ERROR] Exception in get_final_outputs: {e}")
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


@app.route("/api/documents")
def list_documents():
    """List documents for the active project; used by Prompt Enhancer to return PNGs without sample IDs."""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if project_key != "promptenhancer":
            return jsonify({"error": "Documents listing is only available for Prompt Enhancer"}), 400
        data_dir: Path = cfg.get("data_dir")
        if not data_dir or not data_dir.exists():
            return jsonify({"error": err or "Data directory not found"}), 400
        files = [p.name for p in data_dir.glob("*.png")] + [p.name for p in data_dir.glob("*.PNG")] + [p.name for p in data_dir.glob("*.jpg")] + [p.name for p in data_dir.glob("*.jpeg")] + [p.name for p in data_dir.glob("*.JPG")] + [p.name for p in data_dir.glob("*.JPEG")]
        # Unique and sorted case-insensitively
        seen = set()
        docs = []
        for name in sorted(files, key=lambda s: s.lower()):
            low = name.lower()
            if low in seen:
                continue
            seen.add(low)
            docs.append(name)
        return jsonify({"documents": docs, "count": len(docs), "project": project_key})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
