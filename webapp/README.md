# ReqRE Web App

Browser UI for stepping through ReqRE rule execution and previewing the current
assembled model as GLB.

## Run

From the repository root:

```bash
.venv/bin/python -m webapp.server
```

Then open <http://127.0.0.1:8080/>.

Optional environment variables:

```bash
REQRE_WEB_HOST=127.0.0.1
REQRE_WEB_PORT=8080
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
REQRE_COMPUTE_URL=http://localhost:6500/
REQRE_DEMO_CONFIG=scripts/demo.config.json
```

## Workflow

1. Click **Reset From Gaphor** to clear Neo4j and import the same configured
   Gaphor requirement files as `scripts/demo.py`.
2. Choose a JSON rule from the menu and click **Apply Selected Rule**.
3. The backend applies the rule through `rule_to_cypher`, assembles the current
   graph through the existing GH assembly code, exports a GLB, and the browser
   reloads the preview.
4. Use **Demo Shortcuts** for grouped operations that mirror the scripted demo,
   such as D1 stage, D2 module growth, Kappe, foundations, and Fahrbahn.

Generated GLB files are written to `webapp/static/models/` and ignored by Git.

## Notes

- This app intentionally has no frontend build step.
- The GLB viewer uses `<model-viewer>` from a CDN.
- Rule execution and preview generation still require the same local services as
  the demo: Neo4j credentials, Gaphor runtime support for `.gaphor` files, and
  Rhino Compute for GH evaluation.
