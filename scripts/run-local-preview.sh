#!/usr/bin/env sh
set -eu

port="${1:-8000}"
site="$(mktemp -d)"

cleanup() {
  rm -rf "$site"
}

trap cleanup EXIT INT TERM

mkdir -p "$site/assets"
cp src/ai_observability/static/index.html src/ai_observability/static/decision-record.html src/ai_observability/static/developer-mode.html "$site/"
cp src/ai_observability/static/metrics src/ai_observability/static/events "$site/"
cp src/ai_observability/static/styles.css src/ai_observability/static/app.js src/ai_observability/static/developer-mode.js src/ai_observability/static/mark.svg "$site/assets/"

echo "Serving the dependency-free portfolio preview at http://127.0.0.1:${port}/"
echo "Press Ctrl-C to stop."
python3 -m http.server "$port" --directory "$site" &
server_pid=$!
wait "$server_pid"
