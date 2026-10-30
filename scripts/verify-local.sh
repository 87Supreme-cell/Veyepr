#!/usr/bin/env sh
set -eu

port="${1:-8015}"
site="$(mktemp -d)"

cleanup() {
  kill "${preview_pid:-}" >/dev/null 2>&1 || true
  rm -rf "$site"
}

trap cleanup EXIT INT TERM

mkdir -p "$site/assets"
cp src/ai_observability/static/index.html src/ai_observability/static/decision-record.html src/ai_observability/static/developer-mode.html "$site/"
cp src/ai_observability/static/metrics src/ai_observability/static/events "$site/"
cp src/ai_observability/static/styles.css src/ai_observability/static/app.js src/ai_observability/static/developer-mode.js src/ai_observability/static/mark.svg "$site/assets/"

python3 -m http.server "$port" --directory "$site" >/tmp/veyepr-local-preview.log 2>&1 &
preview_pid=$!

attempt=0
until curl --fail --silent "http://127.0.0.1:${port}/" | grep -q 'AI usage evidence'; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 15 ]; then
    echo "Local preview did not start within 30 seconds." >&2
    exit 1
  fi
  sleep 2
done

curl --fail --silent "http://127.0.0.1:${port}/assets/styles.css" | grep -q -- '--ink'
curl --fail --silent "http://127.0.0.1:${port}/decision-record.html" | grep -q 'Decision Record'
curl --fail --silent "http://127.0.0.1:${port}/developer-mode.html" | grep -q 'Developer mode'
curl --fail --silent "http://127.0.0.1:${port}/metrics" | grep -q '^veyepr_portfolio_preview 1'

python3 -m json.tool contracts/training-event.schema.json >/dev/null
python3 -m json.tool fixtures/valid-training-event.json >/dev/null

echo "Verification passed: dependency-free local preview, decision record, developer mode, and contract fixtures are available."
