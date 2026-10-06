# Teknovashop Product Pipeline

Teknovashop uses the backend as the canonical product authority.

## Rule

A new product is **never added to the frontend catalog manually**.

The product lifecycle is:

```
dedicated builder
  -> model contract
  -> commercial metadata
  -> engineering
  -> geometry QA
  -> visual_qa
  -> Studio asset approval
  -> production
```

Forge V2 and the public catalog consume `/catalog/products`. A new backend
product therefore appears in V2 Lab without editing `data/models.ts`.

## Stages

### engineering

The product may be generated, parameterized and tested in Forge V2 Lab. It is
not a public catalog product.

Requirements:

- registered builder
- canonical defaults
- canonical variant
- valid extents
- non-empty STL
- watertight mesh
- variant changes geometry
- minimum product envelope

### visual_qa

Geometry has passed engineering review. Product presentation, camera, material,
marketing render and visual correspondence are being approved.

### production

The product may appear in the public catalog.

Additional requirements:

- approved Studio marketing asset
- `visual_source = studio_asset`
- stable product version
- geometry/STL gate still passes

## Adding product 73

1. Create a **dedicated builder** under `apps/stl-service/models/`.
2. Add one canonical contract to `model_contracts.py`.
3. Add its commercial metadata to `product_catalog.py` with
   `stage = "engineering"`.
4. Run:

```bash
python product_release.py <slug>
pytest -q
```

5. The product appears automatically in Forge V2 -> Lab.
6. Improve/validate the product geometry.
7. Move it to `visual_qa`.
8. Approve its Studio render.
9. Promote metadata to `production` and set a stable version.
10. CI must pass before merge.

## What must not happen

- Do not add another product list to the frontend.
- Do not mark engineering geometry as production to make the catalog look full.
- Do not use a prettier renderer to hide weak geometry.
- Do not promote a product without a dedicated visual asset and STL QA.

The catalog can grow to hundreds of products without changing the frontend
registry because product discovery is canonical and server-driven.
