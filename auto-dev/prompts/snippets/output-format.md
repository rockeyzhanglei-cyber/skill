## Completion Signal

When task is complete, write a completion marker to:
```
{DOCS_DIR}/{STAGE_ID}-done.json
```

File content format:
```json
{
  "status": "success|failed",
  "summary": "One-line summary of work completed",
  "output_files": ["path/to/file1", "path/to/file2"]
}
```

When status=failed, additionally include `error_message` field.

### Verify stage extension

For the **verify** stage, the done JSON must also include:
```json
{
  "status": "success|failed",
  "verdict": "pass|warn|fail",
  "summary": "One-line summary",
  "output_files": ["verify-report.md"]
}
```

- `pass`: All features implemented, no critical issues
- `warn`: All features implemented, minor issues exist
- `fail`: Missing features or unfixed critical issues
