# Platform prerequisites

What must be provisioned in the Databricks workspace before the first bundle deploy. These are one-time setup tasks, not per-deploy tasks.

---

## Common (AWS and Azure)

### Databricks workspace

- Unity Catalog enabled on the workspace
- A metastore attached to the workspace
- A catalog named `dataops` (or set `--var catalog=<name>` at deploy time)

### Unity Catalog objects

The deploy user (or CI service principal) needs the following grants before the first deploy:

```sql
-- Allow bundle deploy to create schemas and tables
GRANT CREATE SCHEMA ON CATALOG dataops TO `<sp-or-user>`;

-- Allow pipeline to create managed tables within the target schema
-- (granted automatically when the schema is created by the deployer)
```

UC Volumes for landing data are created as part of the CI deploy sequence (Pass 2). The external location backing those volumes must already exist.

### Service principal (prod)

A Databricks service principal is required for the `prod` target:

1. Create a service principal in the Databricks account console.
2. Grant it `CAN_MANAGE` on the `prod` pipelines and job (set automatically on first deploy when `run_as` is configured).
3. Note the **application UUID** — this is `DATABRICKS_SP_CLIENT_ID` in CI secrets.
4. Generate an OAuth M2M client secret for CI authentication (`DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`).

> The SP must own the prod pipelines for `event_log()` queries to work. See [architecture](architecture.md#key-design-decisions) and [runbook](runbook.md#event_log-access).

---

## AWS

### Unity Catalog external location

Databricks UC Volumes require an S3-backed external location:

1. Create an S3 bucket (e.g. `databricks-dataops-<env>`).
2. Create an IAM role with read/write access to the bucket and a trust policy for the Databricks AWS account.
3. Register the external location in the UC account console:
   - **URL:** `s3://<bucket>/<prefix>`
   - **Storage credential:** the IAM role ARN
4. The location must be accessible to the workspace metastore.

### Databricks CLI authentication (AWS)

Configure `~/.databrickscfg` with OAuth M2M:

```ini
[DEFAULT]
host          = https://<workspace-id>.cloud.databricks.com
client_id     = <sp-application-id>
client_secret = <sp-client-secret>
```

---

## Azure

### Unity Catalog external location

Databricks UC Volumes require an ADLS Gen2-backed external location:

1. Create an ADLS Gen2 storage account and a container (e.g. `dataops`).
2. Create an Azure service principal with `Storage Blob Data Contributor` on the container.
3. Register a storage credential in the UC account console using the SP credentials.
4. Register the external location:
   - **URL:** `abfss://<container>@<storage-account>.dfs.core.windows.net/<prefix>`
   - **Storage credential:** the Azure SP credential registered above

> Pipeline code never references `abfss://` directly. Access is through `/Volumes/...` only.

### Databricks CLI authentication (Azure)

Configure `~/.databrickscfg` with OAuth M2M:

```ini
[DEFAULT]
host          = https://adb-<workspace-id>.<region>.azuredatabricks.net
client_id     = <sp-application-id>
client_secret = <sp-client-secret>
```

Azure DevOps service connections and variable groups are covered in [CI/CD](ci-cd.md#azure-devops).

---

## Checklist

- [ ] Workspace has Unity Catalog enabled with a metastore attached
- [ ] Catalog `dataops` exists (or custom catalog name decided)
- [ ] External location registered and accessible to the workspace
- [ ] Deployer user/SP has `CREATE SCHEMA` on the catalog
- [ ] Prod SP created, application UUID noted
- [ ] CI secrets populated (see [CI/CD](ci-cd.md#secrets))
