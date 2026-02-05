#!/usr/bin/env bash
set -euo pipefail

RENDER_MCP_URL="https://mcp.render.com/mcp"
WORKSPACE_ID="tea-d5v4eq94tr6s739e2bh0"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found. Install Codex first."
  exit 1
fi

if [ -z "${RENDER_API_KEY:-}" ]; then
  echo "RENDER_API_KEY is not set."
  echo "Export it first, then rerun:"
  echo '  export RENDER_API_KEY="rnd_..."'
  exit 1
fi

echo "Configuring Codex MCP server 'render'..."
codex mcp remove render >/dev/null 2>&1 || true
codex mcp add render --url "${RENDER_MCP_URL}" --bearer-token-env-var RENDER_API_KEY

echo
echo "Done. Next steps:"
echo "1) Restart Codex app/session."
echo "2) In Codex chat, select workspace:"
echo "   Set my Render workspace to ${WORKSPACE_ID}"
echo "3) Verify MCP:"
echo "   codex mcp list"
