#! /usr/bin/env bash

set -e
set -x

cd backend
VERCEL_ENV=development uv run python -c "import app.index; import json; print(json.dumps(app.index.app.openapi()))" >../openapi.json
cd ..
mv openapi.json frontend/
bun run --filter frontend generate-client
bun run lint
