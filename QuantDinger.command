#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

choice="$(osascript <<'APPLESCRIPT'
try
  set response to display dialog "QuantDinger" with title "QuantDinger" buttons {"Kapat", "Başlat"} default button "Başlat" cancel button "Kapat"
  button returned of response
on error
  return "Kapat"
end try
APPLESCRIPT
)"

case "$choice" in
  Başlat)
    if "$ROOT_DIR/tools/quantdinger-start.sh"; then
      open "http://127.0.0.1:18080"
      osascript -e 'display notification "QuantDinger hazır: http://127.0.0.1:18080" with title "QuantDinger"'
    else
      osascript -e 'display alert "QuantDinger başlatılamadı" message "Terminal penceresindeki hata mesajını kontrol edin." as critical'
      exit 1
    fi
    ;;
  Kapat)
    if "$ROOT_DIR/tools/quantdinger-stop.sh"; then
      osascript -e 'display notification "QuantDinger kapatıldı; veriler korundu." with title "QuantDinger"'
    else
      osascript -e 'display alert "QuantDinger kapatılamadı" message "Terminal penceresindeki hata mesajını kontrol edin." as critical'
      exit 1
    fi
    ;;
esac
