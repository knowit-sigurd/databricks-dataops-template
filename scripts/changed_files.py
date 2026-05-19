"""
Determine whether a Databricks deploy is needed based on changed files in a PR.

Prints "true"  → deploy is needed (at least one non-docs file changed)
Prints "false" → all changes are docs-only, deploy can be skipped

Usage (from CI or Makefile):
    CI_PROVIDER=github PR_NUMBER=<n> GITHUB_REPOSITORY=<owner/repo> GITHUB_TOKEN=<token> \\
        uv run python scripts/changed_files.py

Supported providers: github
Pass 3 addition: ado (Azure DevOps)
"""

import fnmatch
import json
import os
import sys
import urllib.request

# Mirror the docs-only definition from CLAUDE.md.
# Extending this list is the only change needed to adjust skip behaviour.
DOCS_ONLY_PATTERNS = [
    "docs/**",
    "README.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
]


def is_docs_only(changed_files: list[str]) -> bool:
    if not changed_files:
        # No files reported — default to deploy to avoid silently skipping real changes.
        return False
    return all(
        any(fnmatch.fnmatch(path, pattern) for pattern in DOCS_ONLY_PATTERNS)
        for path in changed_files
    )


def get_changed_files_github() -> list[str]:
    repo = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ.get("GITHUB_TOKEN", "")

    files: list[str] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
            f"?per_page=100&page={page}"
        )
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read())

        if not batch:
            break
        files.extend(item["filename"] for item in batch)
        if len(batch) < 100:
            break
        page += 1

    return files


def main() -> None:
    provider = os.environ.get("CI_PROVIDER", "")

    if provider == "github":
        changed = get_changed_files_github()
    else:
        raise NotImplementedError(
            f"CI_PROVIDER={provider!r} is not supported. "
            "Supported: github. ADO provider is planned for Pass 3."
        )

    print("false" if is_docs_only(changed) else "true")


if __name__ == "__main__":
    main()
