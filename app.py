import os
from pathlib import Path
from functools import lru_cache

import pandas as pd
import numpy as np
from flask import Flask, jsonify, render_template, send_file, request
import json
import storage_handler as storage

app = Flask(__name__)

# In-memory cache for project data to avoid repeated downloads
_EXCEL_CACHE = {}
_JSON_CACHE = {}

USE_CASES_DIR = storage.get_base_dir()

# Default configuration (Audit project)
AUDIT_DIR = USE_CASES_DIR / "Audit"
AUDIT_DATA_DIR = AUDIT_DIR / "data"
AUDIT_EXCEL_FILE = AUDIT_DIR / "Metadata.xlsx"
AUDIT_FINAL_OUTPUTS = AUDIT_DIR / "final_outputs.json"

# Default configuration (Invoicing project)
INVOICING_DIR = USE_CASES_DIR / "Invoicing"
INVOICING_DATA_DIR = INVOICING_DIR / "data"
INVOICING_EXCEL_FILE = INVOICING_DIR / "PO Database.xlsx"
INVOICING_FINAL_OUTPUTS = INVOICING_DIR / "final_outputs.json"

# Default configuration (Smart Judge project)
SMART_JUDGE_DIR = USE_CASES_DIR / "Smart Judge"
SMART_JUDGE_DATA_DIR = SMART_JUDGE_DIR / "data"
SMART_JUDGE_FINAL_OUTPUTS = SMART_JUDGE_DIR / "final_outputs.json"
SMART_JUDGE_METADATA_FILE = SMART_JUDGE_DIR / "metadata.json"

# Default configuration (Prompt Enhancer project)
PROMPT_ENHANCER_DIR = USE_CASES_DIR / "Prompt Enhancer"
PROMPT_ENHANCER_DATA_DIR = PROMPT_ENHANCER_DIR / "data"

# Default configuration (ADIO project)
ADIO_DIR = USE_CASES_DIR / "ADIO"
ADIO_DATA_DIR = ADIO_DIR / "data"
ADIO_EXCEL_FILE = ADIO_DIR / "company_info.xlsx"

# Default configuration (Emirates NBD project)
EMIRATES_NBD_DIR = USE_CASES_DIR / "Emirates NBD"
EMIRATES_NBD_DATA_DIR = EMIRATES_NBD_DIR / "data"
EMIRATES_NBD_EXCEL_FILE = EMIRATES_NBD_DIR / "invoice_data.xlsx"

# Project registry
PROJECTS = {
    "audit": {
        "label": "Auditing",
        "data_dir": AUDIT_DATA_DIR,
        "excel_file": AUDIT_EXCEL_FILE,
        "final_outputs": AUDIT_FINAL_OUTPUTS,
    },
    "invoicing": {
        "label": "Invoicing",
        "data_dir": INVOICING_DATA_DIR,
        "excel_file": INVOICING_EXCEL_FILE,
        "final_outputs": INVOICING_FINAL_OUTPUTS,
    },
    "smartjudge": {
        "label": "Smart Judge",
        "data_dir": SMART_JUDGE_DATA_DIR,
        "excel_file": None,
        "final_outputs": SMART_JUDGE_FINAL_OUTPUTS,
        "metadata_file": SMART_JUDGE_METADATA_FILE,
    },
    "promptenhancer": {
        "label": "Prompt Enhancer",
        "data_dir": PROMPT_ENHANCER_DATA_DIR,
        "excel_file": None,
        "final_outputs": None,
    },
    "adio": {
        "label": "ADIO",
        "data_dir": ADIO_DATA_DIR,
        "excel_file": ADIO_EXCEL_FILE,
        "final_outputs": None,
    },
    "emiratesnbd": {
        "label": "Emirates NBD",
        "data_dir": EMIRATES_NBD_DATA_DIR,
        "excel_file": EMIRATES_NBD_EXCEL_FILE,
        "final_outputs": None,
    },
}


def _get_project_key():
    """Resolve project from query param."""
    key = (request.args.get("project") or "").strip().lower()
    return key


def _get_cached_excel(project_key: str, excel_path: Path):
    """Get cached Excel DataFrame or load and cache it."""
    cache_key = f"{project_key}:{excel_path}"
    if cache_key not in _EXCEL_CACHE:
        print(f"[CACHE] Loading Excel for {project_key}: {excel_path}")
        _EXCEL_CACHE[cache_key] = storage.read_excel_custom(excel_path)
    else:
        print(f"[CACHE] Using cached Excel for {project_key}")
    return _EXCEL_CACHE[cache_key]


def _get_cached_json(project_key: str, json_path: Path):
    """Get cached JSON data or load and cache it."""
    cache_key = f"{project_key}:{json_path}"
    if cache_key not in _JSON_CACHE:
        print(f"[CACHE] Loading JSON for {project_key}: {json_path}")
        _JSON_CACHE[cache_key] = storage.read_json(json_path)
    else:
        print(f"[CACHE] Using cached JSON for {project_key}")
    return _JSON_CACHE[cache_key]


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
        # Final outputs and metadata file required for sample IDs; data_dir required for serving PDFs
        if not final_outputs or not storage.exists(Path(final_outputs)):
            missing.append("final_outputs")
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
        metadata_file: Path | None = cfg.get("metadata_file")
        if not metadata_file or not storage.exists(Path(metadata_file)):
            missing.append("metadata_file")
    elif project_key == "promptenhancer":
        # Only data_dir required; images (PNGs) only
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
    elif project_key == "adio":
        # Data dir and Excel file required for company info
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
        if not excel_file or not storage.exists(Path(excel_file)):
            missing.append("excel_file")
    elif project_key == "emiratesnbd":
        # Data dir and Excel file required for invoice data
        if not data_dir or not storage.exists(data_dir):
            missing.append("data_dir")
        if not excel_file or not storage.exists(Path(excel_file)):
            missing.append("excel_file")
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

        # For Invoicing, Smart Judge, Prompt Enhancer, and Emirates NBD, validation is relaxed per project rules
        if project_key not in ("invoicing", "smartjudge", "promptenhancer", "emiratesnbd") and not valid:
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
                    df = _get_cached_excel(project_key, excel_file)
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

        elif project_key == "adio":
            # ADIO: sample IDs are folder names; PDFs live under data/<sample_id>/; no items
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
                print(f"[DEBUG] ADIO found {len(pdfs)} unique PDFs in {pdf_folder}")
            else:
                print(f"[DEBUG] ADIO PDF folder not found: {pdf_folder}")
            result = {
                "sample_id": sample_id,
                "short_texts": short_texts,
                "pdfs": pdfs,
                "pdf_count": len(pdfs),
                "text_count": len(short_texts),
                "project": project_key,
            }
            print(f"[DEBUG] Returning adio result: {result['pdf_count']} PDFs, {result['text_count']} items")
            return jsonify(result)

        elif project_key == "emiratesnbd":
            # Emirates NBD: sample IDs are folder names; PDFs live under data/<sample_id>/; no items
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
                print(f"[DEBUG] Emirates NBD found {len(pdfs)} unique PDFs in {pdf_folder}")
            else:
                print(f"[DEBUG] Emirates NBD PDF folder not found: {pdf_folder}")
            result = {
                "sample_id": sample_id,
                "short_texts": short_texts,
                "pdfs": pdfs,
                "pdf_count": len(pdfs),
                "text_count": len(short_texts),
                "project": project_key,
            }
            print(f"[DEBUG] Returning emiratesnbd result: {result['pdf_count']} PDFs, {result['text_count']} items")
            return jsonify(result)

        # Default (Audit)
        excel_path = cfg["excel_file"]
        print(f"[DEBUG] Reading Excel file: {excel_path}")
        df = _get_cached_excel(project_key, excel_path)
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
                data = _get_cached_json(project_key, final_outputs_path)
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

        # ADIO: folder names in data_dir
        if project_key == "adio":
            data_dir: Path = cfg.get("data_dir")
            if not data_dir or not storage.exists(data_dir):
                return jsonify({"error": err or "Data directory not found"}), 400
            # Get all subdirectories in the data folder
            from pathlib import Path
            ids = []
            for item in storage.list_dir(data_dir):
                item_path = data_dir / item
                if storage.is_dir(item_path):
                    ids.append(item)
            ids_sorted = sorted(ids, key=lambda s: (len(s), s))
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        # Emirates NBD: folder names in data_dir
        if project_key == "emiratesnbd":
            data_dir: Path = cfg.get("data_dir")
            if not data_dir or not storage.exists(data_dir):
                return jsonify({"error": err or "Data directory not found"}), 400
            # Get all subdirectories in the data folder
            from pathlib import Path
            ids = []
            for item in storage.list_dir(data_dir):
                item_path = data_dir / item
                if storage.is_dir(item_path):
                    ids.append(item)
            ids_sorted = sorted(ids, key=lambda s: (len(s), s))
            return jsonify({"ids": ids_sorted, "count": len(ids_sorted), "project": project_key})

        # Default (Audit): from Excel
        if not valid:
            return jsonify({"error": err}), 400
        excel_path = cfg["excel_file"]
        # Use full Excel cache and select columns after
        df = _get_cached_excel(project_key, excel_path)
        if "Purch.Req." in df.columns:
            ids = df["Purch.Req."].dropna().astype(str).str.strip().unique().tolist()
        else:
            ids = []
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
            # Local mode - use file path (either local storage or Azure fallback)
            local_path = storage.get_local_path(doc_path)
            file_path = str(local_path)
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
            data = _get_cached_json(project_key, final_outputs_path)
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
    """Return metadata for Smart Judge from centralized metadata.json file."""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if project_key != "smartjudge":
            return jsonify({"error": "Metadata is available only for Smart Judge"}), 400
        if not valid:
            return jsonify({"error": err}), 400
        
        metadata_file: Path | None = cfg.get("metadata_file")
        print(f"[DEBUG] Metadata lookup for Sample ID: {sample_id} from {metadata_file}")
        
        # Check if metadata file exists
        if not metadata_file or not storage.exists(metadata_file):
            return jsonify({"error": f"Metadata file not found"}), 404
        
        try:
            # Read the metadata file (should be an array or object with sample data)
            all_metadata = _get_cached_json(project_key, metadata_file)
            print(f"[DEBUG] Metadata file loaded")
            
            # Find metadata for this sample_id
            metadata = None
            sample_norm = str(sample_id).strip()
            
            if isinstance(all_metadata, list):
                # If it's an array, find the entry with matching sample_id
                for entry in all_metadata:
                    if isinstance(entry, dict):
                        entry_id = entry.get('sample_id')
                        if entry_id and str(entry_id).strip() == sample_norm:
                            metadata = entry
                            break
            elif isinstance(all_metadata, dict):
                # If it's an object with sample_id keys
                metadata = all_metadata.get(sample_norm) or all_metadata.get(sample_id)
            
            if metadata is None:
                return jsonify({"error": f"No metadata found for Sample ID {sample_id}"}), 404
            
            print(f"[DEBUG] Metadata loaded for Sample ID: {sample_id}")
            
        except Exception as fe:
            return jsonify({"error": f"Failed to read metadata: {fe}"}), 500
        
        # Return the metadata for this sample
        return jsonify({
            "sample_id": sample_id,
            "metadata": metadata,
            "project": project_key,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/companyInfo/<sample_id>")
def get_company_info(sample_id: str):
    """Return company information for ADIO from centralized Excel file's 'company_info.xlsx'."""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if project_key != "adio":
            return jsonify({"error": "Company info is available only for ADIO"}), 400
        
        excel_file: Path | None = cfg.get("excel_file")
        print(f"[DEBUG] Company info lookup for Sample ID: {sample_id} from {excel_file}")
        
        # Check if Excel file exists
        if not excel_file or not storage.exists(excel_file):
            return jsonify({"error": f"Company info Excel file not found"}), 404
        
        try:
            # Read the Excel file
            # Use cache for company info to avoid repeated downloads
            df_all = _get_cached_excel(project_key, excel_file)
            print(f"[DEBUG] Company info Excel loaded, shape: {df_all.shape}")
            
            # Normalize column names for comparison
            cols = {c.strip().lower(): c for c in df_all.columns if isinstance(c, str)}
            
            # Try to find sample_id column
            sample_col = None
            for candidate in ['sample_id', 'sample id', 'sampleid', 'id', 'sample']:
                if candidate in cols:
                    sample_col = cols[candidate]
                    break
            
            if sample_col is None:
                return jsonify({"error": f"Could not identify sample_id column in the Excel file"}), 404
            
            # Find the row matching the sample_id
            sample_norm = str(sample_id).strip()
            matches = df_all[df_all[sample_col].astype(str).str.strip() == sample_norm]
            
            if matches.empty:
                return jsonify({"error": f"Sample ID {sample_id} not found in company info Excel file"}), 404
            
            # Get the first matching row and convert to dict
            row = matches.iloc[0]
            
            # Build company info dict with expected fields
            company_info = {}
            for col in df_all.columns:
                col_lower = col.strip().lower()
                # Skip the sample_id column in the output
                if col_lower not in ['sample_id', 'sample id', 'sampleid', 'id', 'sample']:
                    value = row[col]
                    # Convert NaN to None for JSON serialization
                    if pd.isna(value):
                        company_info[col] = None
                    # Format dates as short format (MM/DD/YYYY)
                    elif isinstance(value, pd.Timestamp):
                        company_info[col] = value.strftime('%m/%d/%Y')
                    else:
                        company_info[col] = value
            
            print(f"[DEBUG] Company info loaded for Sample ID: {sample_id}")
            
        except Exception as fe:
            return jsonify({"error": f"Failed to read company info: {fe}"}), 500
        
        # Return the company info data
        return jsonify({
            "sample_id": sample_id,
            "data": company_info,
            "project": project_key,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/invoiceData/<sample_id>")
def get_invoice_data(sample_id: str):
    """Return invoice data for Emirates NBD from centralized Excel file's 'payment sheet'."""
    try:
        project_key = _get_project_key()
        cfg, valid, err = _get_project_config(project_key)
        if not cfg:
            return jsonify({"error": err}), 400
        if project_key != "emiratesnbd":
            return jsonify({"error": "Invoice data is available only for Emirates NBD"}), 400
        
        excel_file: Path | None = cfg.get("excel_file")
        print(f"[DEBUG] Invoice data lookup for Sample ID: {sample_id} from {excel_file}")
        
        # Check if Excel file exists
        if not excel_file or not storage.exists(excel_file):
            return jsonify({"error": f"Invoice data Excel file not found"}), 404
        
        try:
            # Read the Excel file with the specific sheet name "payment sheet"
            # Use cache for invoice data to avoid repeated downloads
            cache_key = f"{project_key}:{excel_file}:payment_sheet"
            if cache_key not in _EXCEL_CACHE:
                print(f"[CACHE] Loading Excel sheet 'payment sheet' for {project_key}: {excel_file}")
                df_all = storage.read_excel_custom(excel_file, sheet_name="payment sheet")
                _EXCEL_CACHE[cache_key] = df_all
            else:
                print(f"[CACHE] Using cached Excel sheet for {project_key}")
                df_all = _EXCEL_CACHE[cache_key]
            
            print(f"[DEBUG] Invoice Excel 'payment sheet' loaded, shape: {df_all.shape}")
            
            # Try to find which column contains the sample ID
            # Common column names to check (case-insensitive)
            sample_id_columns = ['sample_id', 'sample id', 'sampleid', 'id', 'invoice_id', 'invoice id', 'invoiceid']
            
            # Normalize column names for comparison
            cols = {c.strip().lower(): c for c in df_all.columns if isinstance(c, str)}
            sample_col = None
            
            # Try to find a matching column
            for candidate in sample_id_columns:
                if candidate in cols:
                    sample_col = cols[candidate]
                    break
            
            # If no standard column found, try to find a column where the sample_id value exists
            if sample_col is None:
                sample_norm = str(sample_id).strip()
                for col_name in df_all.columns:
                    if df_all[col_name].astype(str).str.strip().eq(sample_norm).any():
                        sample_col = col_name
                        print(f"[DEBUG] Found sample ID in column: {sample_col}")
                        break
            
            if sample_col is None:
                return jsonify({"error": f"Could not identify sample ID column in the Excel file"}), 404
            
            # Filter data for the specific sample_id
            sample_norm = str(sample_id).strip()
            df_filtered = df_all[df_all[sample_col].astype(str).str.strip() == sample_norm]
            
            print(f"[DEBUG] Filtered {len(df_filtered)} rows for Sample ID: {sample_id}")
            
            if df_filtered.empty:
                return jsonify({"error": f"No data found for Sample ID: {sample_id}"}), 404
            
            # Get the first row as a dictionary (for key-value display)
            # Replace NaN values with None for proper JSON serialization
            first_row_series = df_filtered.iloc[0]
            first_row = {}
            
            # Format values, especially dates, to be more readable and JSON serializable
            for key in first_row_series.index:
                value = first_row_series[key]
                
                # Check if value is NaN/None
                if pd.isna(value):
                    first_row[key] = None
                # Check if value is a datetime type (pandas Timestamp)
                elif isinstance(value, pd.Timestamp):
                    # Format as short date format (MM/DD/YYYY)
                    first_row[key] = value.strftime('%m/%d/%Y')
                # Convert numpy/pandas numeric types to Python native types
                elif isinstance(value, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                    first_row[key] = int(value)
                elif isinstance(value, (np.floating, np.float64, np.float32)):
                    first_row[key] = float(value)
                elif isinstance(value, np.bool_):
                    first_row[key] = bool(value)
                # Handle other numpy types with .item() method
                elif hasattr(value, 'item'):
                    try:
                        first_row[key] = value.item()
                    except (ValueError, TypeError, AttributeError):
                        first_row[key] = str(value)
                else:
                    # Regular Python types (str, int, float, bool) pass through
                    first_row[key] = value
            
            # Remove the sample ID column from the data
            if sample_col in first_row:
                del first_row[sample_col]
            
            # Get column names in order (excluding sample ID column)
            columns_ordered = [col for col in df_filtered.columns if col != sample_col]
            
            return jsonify({
                "sample_id": sample_id,
                "data": first_row,
                "columns": columns_ordered,
                "project": project_key,
            })
        except Exception as fe:
            print(f"[ERROR] Failed to read invoice Excel: {fe}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Failed to read invoice data: {fe}"}), 500
        
    except Exception as e:
        print(f"[ERROR] Exception in get_invoice_data: {e}")
        import traceback
        traceback.print_exc()
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
        if not data_dir or not storage.exists(data_dir):
            return jsonify({"error": err or "Data directory not found"}), 400
        files = storage.glob_files(data_dir, "*.png") + storage.glob_files(data_dir, "*.PNG") + storage.glob_files(data_dir, "*.jpg") + storage.glob_files(data_dir, "*.jpeg") + storage.glob_files(data_dir, "*.JPG") + storage.glob_files(data_dir, "*.JPEG")
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
