#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABRICKS_CONFIG_PROFILE:-}" || -z "${DATABRICKS_WAREHOUSE_ID:-}" ]]; then
  cat <<'MSG'

Databricks remote-read setup is optional, but not fully configured.

To run examples that read Unity Catalog remotely, set these in your devcontainer
environment or terminal:

  export DATABRICKS_CONFIG_PROFILE=<profile>
  export DATABRICKS_WAREHOUSE_ID=<warehouse-id>

Check mounted auth profiles with:

  databricks auth profiles

The workspace host is read from the selected Databricks auth profile.

MSG
fi
