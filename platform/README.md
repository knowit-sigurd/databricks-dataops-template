# Platform bundle

Separate Databricks Asset Bundle managing the persistent UC schemas that the data product targets use. Platform-team owned — deployed independently from the data product bundle.

## What it manages

| Resource | Catalog | Schema | `prevent_destroy` |
|---|---|---|---|
| `dev_schema` | `${var.catalog}` | `dev` | true |
| `prod_schema` | `${var.catalog}` | `prod` | true |

Landing volumes (`customers_raw`, `orders_raw`) are managed by the data product bundle. A real platform team would typically extend this bundle to cover volumes too — see [Extending to volumes](#extending-to-volumes).

## Why a separate bundle

The data product bundle is deployed on every PR and every push to main. Keeping lifecycle-protected infrastructure in the same bundle as the data product creates two risks:

- `bundle destroy` on the data product bundle would attempt to delete persistent schemas, taking downstream tables with them
- Granting a CI service principal `bundle destroy` rights implicitly grants it schema deletion rights

A separate bundle with `lifecycle.prevent_destroy: true` makes accidental schema deletion structurally impossible. `bundle destroy` on this bundle is blocked:

```
Error: terraform plan failed:
  dev_schema: lifecycle prevent_destroy is set, destroy is not allowed
```

## Who owns this

The platform team (or whoever manages the workspace infrastructure). The data product team deploys the data product bundle; they do not have deploy rights to the platform bundle.

## Greenfield bootstrap

Run once before the first data product deploy:

```bash
cd platform

# Deploy dev schema
databricks bundle deploy -t dev

# Deploy prod schema
databricks bundle deploy -t prod
```

The data product bundle can then be deployed against schemas that already exist.

## Brownfield adoption (bundle deployment bind)

If `dev` and `prod` schemas already exist (created manually or by a previous deploy), use `bind` to transfer ownership to this bundle without destroying and recreating them:

```bash
cd platform

# Bind existing dev schema
databricks bundle deployment bind dev_schema <existing-schema-id> -t dev

# Bind existing prod schema
databricks bundle deployment bind prod_schema <existing-schema-id> -t prod
```

Find the schema ID in the UC account console or via:

```bash
databricks schemas get --full-name <catalog>.dev
databricks schemas get --full-name <catalog>.prod
```

After binding, the schemas are under platform bundle management — `prevent_destroy` is enforced from the next `bundle deploy` onwards.

## Extending to volumes

To bring landing volumes under platform management, add them to `platform/databricks.yml`:

```yaml
resources:
  volumes:
    dev_customers_raw:
      catalog_name: ${var.catalog}
      schema_name: dev
      name: customers_raw
      volume_type: MANAGED
      lifecycle:
        prevent_destroy: true
```

Then remove the corresponding volume declarations from the data product bundle's `resources/volumes.yml`, and use `bundle deployment bind` to adopt any volumes that already exist. Do not let two bundles declare the same UC resource.
