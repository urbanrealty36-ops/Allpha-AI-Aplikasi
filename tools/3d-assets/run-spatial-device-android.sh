#!/usr/bin/env bash
set -euo pipefail
mkdir -p .artifacts/device-fixture/results/android
adb wait-for-device
# Build is deliberately performed before the emulator is booted. A full native
# release build can take >10 minutes and otherwise leaves the emulator unstable.
apk="apps/client/android/app/build/outputs/apk/release/app-release.apk"
if [ ! -f "$apk" ]; then
  echo "Prebuilt release APK is missing: $apk"
  exit 1
fi
installed=0
for attempt in 1 2 3; do
  adb wait-for-device
  if adb install -r -d --user 0 "$apk"; then installed=1; break; fi
  echo "APK install attempt $attempt failed; restarting adb server and waiting for emulator"
  adb kill-server || true
  adb start-server
  sleep 5
done
if [ "$installed" -ne 1 ]; then
  adb logcat -d > .artifacts/device-fixture/results/android/logcat-full.txt || true
  exit 1
fi
adb logcat -c
adb shell monkey -p com.allpha.universe 1
passed=0
for i in $(seq 1 900); do
  device_logs="$(adb logcat -d -s ReactNativeJS:V ReactNative:V AndroidRuntime:E 2>/dev/null || true)"
  if [[ "$device_logs" == *"SPATIAL_DEVICE_TEST_RESULT:PASS"* ]]; then
    printf "%s\n" "$device_logs" > .artifacts/device-fixture/results/android/logcat.txt
    passed=1
    break
  fi
  if grep -Eqi "SPATIAL_DEVICE_TEST_RESULT:FAIL|Could not load|Cannot read property .* of undefined|TypeError:|SPATIAL_DEVICE_BOUNDARY_ERROR" <<< "$device_logs"; then
    printf "%s\n" "$device_logs" > .artifacts/device-fixture/results/android/logcat.txt
    adb logcat -d > .artifacts/device-fixture/results/android/logcat-full.txt || true
    adb shell screencap -p /sdcard/allpha-spatial-failure.png || true
    adb pull /sdcard/allpha-spatial-failure.png .artifacts/device-fixture/results/android/failure.png || true
    exit 1
  fi
  sleep 3
done
if [ "$passed" -ne 1 ]; then
  adb logcat -d > .artifacts/device-fixture/results/android/logcat-full.txt || true
  echo "Native renderer did not report PASS within 45 minutes"
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
