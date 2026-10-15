#!/usr/bin/env bash
# Publica un APK nuevo (lo mismo que la página /subir de la landing).
#
#   APK_UPLOAD_KEY=... deploy/upload-apk.sh ruta/app.apk 1.0.1 "Notas opcionales"
set -euo pipefail

APK="$1"; VERSION="$2"; NOTES="${3:-}"
API="${API_URL:-https://matricalcapi.quantis.site}"
: "${APK_UPLOAD_KEY:?Define APK_UPLOAD_KEY}"

curl -fS --progress-bar -X POST "$API/api/apk" \
  -H "X-Upload-Key: $APK_UPLOAD_KEY" \
  -F "file=@$APK" -F "version=$VERSION" -F "notes=$NOTES"
echo
