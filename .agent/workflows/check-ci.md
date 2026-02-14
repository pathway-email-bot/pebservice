---
description: How to check GitHub Actions CI pipeline status and errors
---

# Check CI Pipeline Status & Errors

## Quick status check
// turbo
```powershell
gh run list --workflow="deploy-service.yaml" --repo pathway-email-bot/pebservice --limit 3 2>&1
```

## Watch a running pipeline
// turbo
```powershell
gh run watch <RUN_ID> --repo pathway-email-bot/pebservice --exit-status 2>&1
```

## Diagnosing failures

When a run fails, follow this strategy:

### Step 1: Dump failed step logs to a temp file
Console output gets mangled by line wrapping. Always write to a file first:
// turbo
```powershell
gh run view <RUN_ID> --repo pathway-email-bot/pebservice --log-failed 2>&1 | Out-File c:\repos\pebservice\tmp_ci_log.txt -Encoding utf8
```

### Step 2: Find the first error and work backwards
A deployment has many stages — only the first failure matters. Scan for ERROR/FAILED/fatal:
// turbo
```powershell
Select-String -Path c:\repos\pebservice\tmp_ci_log.txt -Pattern "ERROR|FAILED|fatal|error:" -CaseSensitive:$false | Select-Object -First 5
```

### Step 3: Read context around the first error
// turbo
```powershell
$lines = Get-Content c:\repos\pebservice\tmp_ci_log.txt; $idx = 0; foreach ($line in $lines) { if ($line -match "ERROR|FAILED|fatal") { $start = [Math]::Max(0, $idx - 10); $lines[$start..$idx] | ForEach-Object { $_ }; break }; $idx++ }
```

### If the user pastes the error directly, prefer that — it's faster and more reliable.

## Re-trigger pipeline
// turbo
```powershell
gh workflow run deploy-service.yaml --repo pathway-email-bot/pebservice 2>&1
```

## Notes
- `tmp_ci_log.txt` is gitignored via the `tmp_*` pattern
- The `--exit-status` flag on `gh run watch` returns non-zero on failure
- Only one step fails first — focus on that one, not downstream cancellations
