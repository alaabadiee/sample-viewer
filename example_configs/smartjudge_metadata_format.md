# Smart Judge Metadata JSON Format

The `metadata.json` file should be placed at: `Use Cases/Smart Judge/metadata.json`

This file consolidates metadata for all samples in a single location instead of having individual `metadata.json` files in each sample folder.

## Supported Formats

The metadata file supports two formats:

### Format 1: Array of Objects (Recommended)

```json
[
  {
    "sample_id": "sample_001",
    "case_number": "CASE-2023-001",
    "filing_date": "01/15/2023",
    "court_name": "Supreme Court",
    "plaintiff": "John Doe",
    "defendant": "ABC Corporation",
    "case_type": "Civil",
    "status": "Active"
  },
  {
    "sample_id": "sample_002",
    "case_number": "CASE-2023-002",
    "filing_date": "02/20/2023",
    "court_name": "District Court",
    "plaintiff": "Jane Smith",
    "defendant": "XYZ Inc.",
    "case_type": "Commercial",
    "status": "Closed"
  }
]
```

### Format 2: Object with Sample ID Keys

```json
{
  "sample_001": {
    "case_number": "CASE-2023-001",
    "filing_date": "01/15/2023",
    "court_name": "Supreme Court",
    "plaintiff": "John Doe",
    "defendant": "ABC Corporation",
    "case_type": "Civil",
    "status": "Active"
  },
  "sample_002": {
    "case_number": "CASE-2023-002",
    "filing_date": "02/20/2023",
    "court_name": "District Court",
    "plaintiff": "Jane Smith",
    "defendant": "XYZ Inc.",
    "case_type": "Commercial",
    "status": "Closed"
  }
}
```

## Required Fields

- **sample_id**: Required when using array format. Should match the folder names in `Use Cases/Smart Judge/data/`
- When using object format, the keys should be the sample IDs

## Metadata Fields

The specific fields within each metadata entry are flexible and depend on your use case. Common fields might include:

- `case_number`: Case or docket number
- `filing_date`: Date the case was filed (dates will be formatted as MM/DD/YYYY in API responses)
- `court_name`: Name of the court
- `plaintiff`: Plaintiff name
- `defendant`: Defendant name
- `case_type`: Type or category of case
- `status`: Current status of the case
- `judge`: Assigned judge
- `description`: Case description
- Any other custom fields relevant to your project

## Migration from Individual Files

If you currently have individual `metadata.json` files in each sample folder (e.g., `Use Cases/Smart Judge/data/sample_001/metadata.json`), you'll need to:

1. Collect metadata from all individual JSON files
2. Consolidate into a single JSON file using one of the formats above
3. Place the consolidated file at `Use Cases/Smart Judge/metadata.json`
4. Delete individual `metadata.json` files from sample folders (optional, no longer used)

### Example Migration

**Old Structure (Individual Files):**
```
Use Cases/Smart Judge/
  data/
    sample_001/
      document.pdf
      metadata.json  <- Contains metadata for sample_001
    sample_002/
      document.pdf
      metadata.json  <- Contains metadata for sample_002
```

**New Structure (Single File):**
```
Use Cases/Smart Judge/
  metadata.json  <- Contains metadata for ALL samples
  data/
    sample_001/
      document.pdf
    sample_002/
      document.pdf
```

## Notes

- The app caches the metadata file for performance
- Sample IDs are matched case-sensitively and with whitespace trimming
- Empty or missing fields will return as null/None in the API
- Additional fields not displayed in the UI will still be preserved in the API response
- The API endpoint `/api/metadata/<sample_id>` will return only the metadata for the requested sample
