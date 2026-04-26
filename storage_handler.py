"""
Storage handler that supports both local filesystem and Azure Blob Storage.
Switched based on AZURE_STORAGE_ACCOUNT environment variable.
"""
import os
import io
from pathlib import Path
from typing import List, BinaryIO, Optional
import tempfile
from functools import lru_cache

# Check if Azure mode is enabled
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "use-cases")
USE_AZURE = bool(AZURE_CONNECTION_STRING)

if USE_AZURE:
    from azure.storage.blob import BlobServiceClient
    
    # Initialize Azure Blob Service Client with connection string
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
    print(f"✓ Azure Blob Storage initialized: {AZURE_CONTAINER_NAME} container")
else:
    print("✓ Using local filesystem storage")
    print("WARNING: AZURE_STORAGE_CONNECTION_STRING not set!")
    print("App will look for local files in 'Use Cases' folder.")
    print("On Render, set environment variables:")
    print("  - AZURE_STORAGE_CONNECTION_STRING")
    print("  - AZURE_CONTAINER_NAME=use-cases")


def normalize_path(path: str) -> str:
    """Normalize path for Azure (forward slashes, no leading slash)."""
    return path.replace("\\", "/").lstrip("/")


def get_local_base_dir() -> Path:
    """Get local base directory for fallback."""
    return Path(os.getenv("USE_CASES_DIR") or (Path(__file__).resolve().parent / "Use Cases")).resolve()


def get_local_path(virtual_path: Path) -> Path:
    """Convert virtual path to local path for fallback."""
    if not USE_AZURE:
        return virtual_path
    # Replace virtual "Use Cases" with actual local path
    path_str = str(virtual_path)
    if path_str.startswith("Use Cases"):
        return get_local_base_dir() / path_str[10:]  # Remove "Use Cases/" or "Use Cases\\"
    return get_local_base_dir() / path_str


# Cache for blob existence checks (reduces API calls)
@lru_cache(maxsize=1000)
def _check_blob_exists(blob_path: str) -> bool:
    """Cached check if blob exists."""
    try:
        blob_client = container_client.get_blob_client(blob_path)
        blob_client.get_blob_properties()
        return True
    except:
        return False


# Cache for directory listings (reduces API calls)
@lru_cache(maxsize=100)
def _list_directory_blobs(dir_path: str) -> tuple:
    """Cached directory listing. Returns tuple for hashability."""
    try:
        blobs = []
        for blob in container_client.list_blobs(name_starts_with=dir_path):
            blobs.append(blob.name)
        return tuple(blobs)
    except:
        return tuple()


# Cache for file contents (reduces repeated downloads of PDFs/images)
@lru_cache(maxsize=50)  # Cache up to 50 files (adjust based on memory constraints)
def _get_cached_file_bytes(blob_path: str) -> bytes:
    """Download and cache file bytes from Azure. Returns immutable bytes for caching."""
    print(f"[FILE CACHE] Downloading: {blob_path}")
    blob_client = container_client.get_blob_client(blob_path)
    return blob_client.download_blob().readall()


def exists(path: Path) -> bool:
    """Check if a file or directory exists. Fallback to local if not in Azure."""
    if not USE_AZURE:
        return path.exists()
    
    # For Azure, check if blob exists
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    if not blob_path:
        return True  # Root always exists
    
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Try as a file first (cached)
    if _check_blob_exists(blob_path):
        return True
    
    # Check if it's a directory (has blobs with this prefix)
    dir_path = blob_path if blob_path.endswith("/") else blob_path + "/"
    blobs = _list_directory_blobs(dir_path)
    if len(blobs) > 0:
        return True
    
    # Fallback to local if not found in Azure
    local_path = get_local_path(path)
    return local_path.exists()


def is_file(path: Path) -> bool:
    """Check if path is a file (not directory). Fallback to local if not in Azure."""
    if not USE_AZURE:
        return path.is_file()
    
    # In Azure, if it exists and doesn't end with /, it's a file
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Use cached check
    if _check_blob_exists(blob_path):
        return True
    
    # Fallback to local
    local_path = get_local_path(path)
    return local_path.is_file()


def is_dir(path: Path) -> bool:
    """Check if path is a directory. Fallback to local if not in Azure."""
    if not USE_AZURE:
        return path.is_dir()
    
    # In Azure, check if it's a directory (has blobs with this prefix)
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Check if it's a directory (has blobs with this prefix)
    dir_path = blob_path if blob_path.endswith("/") else blob_path + "/"
    blobs = _list_directory_blobs(dir_path)
    if len(blobs) > 0:
        return True
    
    # Fallback to local
    local_path = get_local_path(path)
    return local_path.is_dir()


def list_dir(path: Path) -> List[str]:
    """List all files and directories in a directory. Fallback to local if not in Azure."""
    if not USE_AZURE:
        return [f.name for f in path.iterdir()]
    
    # For Azure, list all items (files and virtual directories) in the path
    dir_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    
    # Clean up the path - remove "Use Cases" prefix if present
    if dir_path.startswith("Use Cases/"):
        dir_path = dir_path[10:]  # Remove "Use Cases/"
    
    if dir_path and not dir_path.endswith("/"):
        dir_path += "/"
    
    # Use cached directory listing
    blobs = _list_directory_blobs(dir_path)
    
    # Extract unique immediate children (files and directories)
    children = set()
    for blob_name in blobs:
        relative = blob_name[len(dir_path):]
        if relative:
            # Get the first component (file or directory name)
            first_component = relative.split("/")[0]
            children.add(first_component)
    
    # If no results in Azure, fallback to local
    if not children:
        local_path = get_local_path(path)
        if local_path.exists() and local_path.is_dir():
            return [f.name for f in local_path.iterdir()]
    
    return sorted(children)


def glob_files(directory: Path, pattern: str) -> List[str]:
    """List files matching pattern in directory. Fallback to local if not in Azure."""
    if not USE_AZURE:
        return [f.name for f in directory.glob(pattern)]
    
    # For Azure, list blobs with prefix
    dir_path = normalize_path(str(directory).replace(str(get_base_dir()), ""))
    
    # Clean up the path - remove "Use Cases" prefix if present
    if dir_path.startswith("Use Cases/"):
        dir_path = dir_path[10:]  # Remove "Use Cases/"
    
    if dir_path and not dir_path.endswith("/"):
        dir_path += "/"
    
    results = []
    ext = pattern.replace("*", "").lower()
    
    # Use cached directory listing
    blobs = _list_directory_blobs(dir_path)
    
    for blob_name in blobs:
        # Get just the filename (no subdirectories)
        relative = blob_name[len(dir_path):]
        if "/" not in relative and relative.lower().endswith(ext):
            results.append(relative)
    
    # If no results in Azure, fallback to local
    if not results:
        local_path = get_local_path(directory)
        if local_path.exists() and local_path.is_dir():
            return [f.name for f in local_path.glob(pattern)]
    
    return results


def read_excel(path: Path, **kwargs):
    """Read Excel file and return pandas DataFrame. Fallback to local if not in Azure."""
    import pandas as pd
    
    if not USE_AZURE:
        return pd.read_excel(path, **kwargs)
    
    # For Azure, download to memory and read
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Try Azure first
    if _check_blob_exists(blob_path):
        print(f"[DEBUG] Reading Excel from Azure: {blob_path}")
        blob_client = container_client.get_blob_client(blob_path)
        stream = io.BytesIO()
        blob_client.download_blob().readinto(stream)
        stream.seek(0)
        return pd.read_excel(stream, **kwargs)
    
    # Fallback to local
    local_path = get_local_path(path)
    print(f"[DEBUG] Reading Excel from local: {local_path}")
    return pd.read_excel(local_path, **kwargs)


def read_excel_custom(path: Path, **kwargs):
    """Read Excel file without column restrictions. Fallback to local if not in Azure."""
    import pandas as pd
    
    if not USE_AZURE:
        return pd.read_excel(path, **kwargs)
    
    # For Azure, download to memory and read
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Try Azure first
    if _check_blob_exists(blob_path):
        print(f"[DEBUG] Reading Excel (custom) from Azure: {blob_path}")
        blob_client = container_client.get_blob_client(blob_path)
        stream = io.BytesIO()
        blob_client.download_blob().readinto(stream)
        stream.seek(0)
        return pd.read_excel(stream, **kwargs)
    
    # Fallback to local
    local_path = get_local_path(path)
    print(f"[DEBUG] Reading Excel (custom) from local: {local_path}")
    return pd.read_excel(local_path, **kwargs)


def read_json(path: Path):
    """Read JSON file and return parsed data. Fallback to local if not in Azure."""
    import json
    
    if not USE_AZURE:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    
    # For Azure, download and parse
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Try Azure first
    if _check_blob_exists(blob_path):
        print(f"[DEBUG] Reading JSON from Azure: {blob_path}")
        blob_client = container_client.get_blob_client(blob_path)
        content = blob_client.download_blob().readall()
        return json.loads(content.decode("utf-8-sig"))
    
    # Fallback to local
    local_path = get_local_path(path)
    print(f"[DEBUG] Reading JSON from local: {local_path}")
    with open(local_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def get_file_stream(path: Path):
    """Get file as BytesIO stream for send_file. Uses cache to avoid repeated downloads. Fallback to local if not in Azure."""
    if not USE_AZURE:
        return None  # Signal to use file path instead
    
    # For Azure, use cached bytes and create fresh stream
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    # Try Azure first
    if _check_blob_exists(blob_path):
        # Get cached bytes (or download if not cached)
        file_bytes = _get_cached_file_bytes(blob_path)
        print(f"[FILE CACHE] Serving from Azure cache: {blob_path} ({len(file_bytes)} bytes)")
        
        # Create fresh BytesIO stream from cached bytes
        stream = io.BytesIO(file_bytes)
        stream.seek(0)
        return stream
    
    # Fallback to local (return None to signal local file path should be used)
    print(f"[FALLBACK] File not in Azure, using local: {path}")
    return None


def get_file_path(path: Path) -> str:
    """Get file path for send_file. Returns local path or downloads to temp for Azure.
    DEPRECATED: Use get_file_stream() instead for better performance."""
    if not USE_AZURE:
        return str(path)
    
    # For Azure, download to temporary file (SLOW - consider using get_file_stream instead)
    blob_path = normalize_path(str(path).replace(str(get_base_dir()), ""))
    # Clean up the path - remove "Use Cases" prefix if present
    if blob_path.startswith("Use Cases/"):
        blob_path = blob_path[10:]  # Remove "Use Cases/"
    
    print(f"[DEBUG] Downloading file from: {blob_path}")
    blob_client = container_client.get_blob_client(blob_path)
    
    # Create temp file with same extension
    suffix = path.suffix
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    
    with open(temp_file.name, "wb") as f:
        blob_client.download_blob().readinto(f)
    
    return temp_file.name


def get_base_dir() -> Path:
    """Get base directory for data."""
    if USE_AZURE:
        # Return virtual path when using Azure
        return Path("Use Cases")
    else:
        # Return actual local path
        return Path(os.getenv("USE_CASES_DIR") or (Path(__file__).resolve().parent / "Use Cases")).resolve()
