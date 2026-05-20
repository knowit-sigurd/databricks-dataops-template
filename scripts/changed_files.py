"""
Determine whether a Databricks deploy is needed based on changed files in a PR.

Prints "true"  → deploy is needed (at least one non-docs file changed)
Prints "false" → all changes are docs-only, deploy can be skipped

Usage (from CI or Makefile):
    # GitHub Actions
    CI_PROVIDER=github PR_NUMBER=<n> GITHUB_REPOSITORY=<owner/repo> GITHUB_TOKEN=<token> \\
        uv run python scripts/changed_files.py

    # Azure DevOps (env vars are injected automatically by ADO)
    CI_PROVIDER=azure_devops uv run python scripts/changed_files.py

Supported providers: github, azure_devops
"""

import base64
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


def get_changed_files_ado() -> list[str]:
    collection_uri = os.environ.get("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI")
    project = os.environ.get("SYSTEM_TEAMPROJECT")
    repo_id = os.environ.get("BUILD_REPOSITORY_ID")
    pr_id = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")

    if not all([collection_uri, project, repo_id, pr_id]):
        # Not running inside an ADO pipeline — fall back to local git diff.
        result = os.popen("git diff --name-only origin/main...HEAD").read()
        return [f for f in result.splitlines() if f]

    url = (
        f"{collection_uri.rstrip('/')}/{project}/_apis/git/repositories"
        f"/{repo_id}/pullRequests/{pr_id}/iterations?api-version=7.1"
    )
    token = os.environ.get("SYSTEM_ACCESSTOKEN", "")
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        encoded = base64.b64encode(f":{token}".encode()).decode()
        req.add_header("Authorization", f"Basic {encoded}")

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    files: set[str] = set()
    for iteration in data.get("value", []):
        iter_id = iteration["id"]
        changes_url = (
            f"{collection_uri.rstrip('/')}/{project}/_apis/git/repositories"
            f"/{repo_id}/pullRequests/{pr_id}/iterations/{iter_id}/changes"
            f"?api-version=7.1"
        )
        changes_req = urllib.request.Request(changes_url)
        changes_req.add_header("Accept", "application/json")
        if token:
            changes_req.add_header("Authorization", f"Basic {encoded}")
        with urllib.request.urlopen(changes_req) as resp:
            changes_data = json.loads(resp.read())
        for change in changes_data.get("changeEntries", []):
            path = change.get("item", {}).get("path", "")
            if path.startswith("/"):
                path = path[1:]
            if path:
                files.add(path)

    return list(files)


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
    elif provider == "azure_devops":
        changed = get_changed_files_ado()
    else:
        raise NotImplementedError(
            f"CI_PROVIDER={provider!r} is not supported. "
            "Supported: github, azure_devops."
        )

    print("false" if is_docs_only(changed) else "true")


if __name__ == "__main__":
    main()
