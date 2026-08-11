#!/usr/bin/env bash
set -euo pipefail
echo "[1/3] Node: $(node -v)"
echo "[2/3] TypeScript syntax/project check (after npm ci)"
npm run typecheck
echo "[3/3] Unit + HTTP smoke tests"
npm test
echo "SMOKE TEST PASSED"
