#!/usr/bin/env bash
set -euo pipefail
mkdir -p .artifacts/device-fixture/results/android
adb logcat -c
(cd apps/client && ./node_modules/.bin/expo prebuild --platform android --no-install)
(cd apps/client && ./node_modules/.bin/expo run:android --variant release) > .artifacts/device-fixture/results/android/expo-run.log 2>&1 &
expo_pid=$!
passed=0
for i in $(seq 1 120); do
  device_logs="$(adb logcat -d -s ReactNativeJS:V ReactNative:V AndroidRuntime:E 2>/dev/null || true)"
  metro_logs="$(cat .artifacts/device-fixture/results/android/expo-run.log 2>/dev/null || true)"
  logs="${device_logs}\n${metro_logs}"
  if echo "$logs" | grep -q "SPATIAL_DEVICE_TEST_RESULT:PASS"; then
    printf "%s\n%s\n" "$device_logs" "$metro_logs" > .artifacts/device-fixture/results/android/logcat.txt
    passed=1
    break
  fi
  if echo "$logs" | grep -Eqi "SPATIAL_DEVICE_TEST_RESULT:FAIL|Could not load|Cannot read property .* of undefined|TypeError:|SPATIAL_DEVICE_BOUNDARY_ERROR"; then
    echo "$device_logs" > .artifacts/device-fixture/results/android/logcat.txt
    adb logcat -d > .artifacts/device-fixture/results/android/logcat-full.txt || true
    adb shell screencap -p /sdcard/allpha-spatial-failure.png || true
    adb pull /sdcard/allpha-spatial-failure.png .artifacts/device-fixture/results/android/failure.png || true
    cat .artifacts/device-fixture/results/android/expo-run.log
    cat .artifacts/device-fixture/results/android/logcat-full.txt
    exit 1
  fi
  if ! kill -0 "$expo_pid" 2>/dev/null; then
    echo "Expo process exited before renderer PASS"
    cat .artifacts/device-fixture/results/android/expo-run.log
    adb logcat -d > .artifacts/device-fixture/results/android/logcat-full.txt
    exit 1
  fi
  sleep 3
done
if [ "$passed" -ne 1 ]; then
  adb logcat -d > .artifacts/device-fixture/results/android/logcat-full.txt
  echo "Native renderer did not report PASS within 6 minutes"
  cat .artifacts/device-fixture/results/android/expo-run.log
  exit 1
fi
adb shell screencap -p /sdcard/allpha-spatial-render.png
adb pull /sdcard/allpha-spatial-render.png .artifacts/device-fixture/results/android/render.png
python3 - <<'PY'
import json, struct
from pathlib import Path
root=Path(".artifacts/device-fixture/results/android")
log=(root/"logcat.txt").read_text(errors="replace")
image=(root/"render.png").read_bytes()
if "SPATIAL_DEVICE_TEST_RESULT:PASS" not in log:
    raise SystemExit("Android PASS marker missing from retained log")
if len(image)<1024 or image[:8]!=b"\x89PNG\r\n\x1a\n" or image[12:16]!=b"IHDR":
    raise SystemExit("Android screenshot is missing, too small, or not a valid PNG")
width,height=struct.unpack(">II",image[16:24])
if width<320 or height<320:
    raise SystemExit(f"Android screenshot dimensions too small: {width}x{height}")
print(json.dumps({"platform":"android-emulator","runtime":"PASS","screenshot":"PASS","width":width,"height":height,"bytes":len(image)}))
PY
