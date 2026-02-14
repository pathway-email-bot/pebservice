---
description: How to check GitHub Actions CI pipeline status and errors
---

# Check CI Pipeline Status & Errors

// turbo-all

## Watch the latest pipeline run
Use this single command to find and watch the latest run — no need to fetch the ID separately:
```powershell
$runId = gh run list --workflow="deploy-service.yaml" --repo pathway-email-bot/pebservice --limit 1 --json databaseId --jq ".[0].databaseId" 2>&1; gh run watch $runId --repo pathway-email-bot/pebservice --exit-status 2>&1
```

## Re-trigger pipeline manually
```powershell
gh workflow run deploy-service.yaml --repo pathway-email-bot/pebservice 2>&1
```

## Diagnosing failures

### Step 1: Dump failed step logs to a temp file
Console output gets mangled by line wrapping. Always write to a file first:
```powershell
$runId = gh run list --workflow="deploy-service.yaml" --repo pathway-email-bot/pebservice --limit 1 --json databaseId --jq ".[0].databaseId" 2>&1; gh run view $runId --repo pathway-email-bot/pebservice --log-failed 2>&1 | Out-File c:\repos\pebservice\tmp_ci_log.txt -Encoding utf8
```

### Step 2: Find the first error and read context around it
```powershell
$lines = Get-Content c:\repos\pebservice\tmp_ci_log.txt; $idx = 0; foreach ($line in $lines) { if ($line -match "ERROR|FAILED|fatal") { $start = [Math]::Max(0, $idx - 10); $end = [Math]::Min($lines.Count - 1, $idx + 5); $lines[$start..$end] | ForEach-Object { $_ }; break }; $idx++ }
```

## Notes
- `tmp_ci_log.txt` is gitignored via the `tmp_*` pattern
- If the user pastes the error directly, prefer that — it's faster and more reliable
- Only one step fails first — focus on that one, not downstream cancellations
