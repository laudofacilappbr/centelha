#!/usr/bin/env bash
# Roda dentro do container "app" de ci/docker-compose.yml.
set -euo pipefail
cd /app
echo "== dependências (pub get, lockfile)"
flutter pub get --enforce-lockfile
echo "== traduções (gen-l10n)"
flutter gen-l10n
echo "== formatação (dart format)"
dart format --output=none --set-exit-if-changed lib test
echo "== análise (flutter analyze)"
flutter analyze
echo "== testes (flutter test)"
flutter test
