# Rebuilding Sunshine so NVENC works on an older driver

Use when the packaged Sunshine silently encodes with `*_vulkan` because the ffmpeg it bundles demands
a newer NVIDIA driver than the distro ships. The GPU and driver are usually fine — an independent
ffmpeg on the same box proves it.

## 0. Isolate the layer first
```bash
ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc=size=1280x720:rate=30 -frames:v 30 \
  -c:v h264_nvenc -f null -          # exit 0 = NVENC works here
```
Failure with `Driver does not support the required nvenc API version` means the driver is the
blocker and no rebuild helps. Success means the fault is Sunshine's bundled ffmpeg — continue.
Re-run this after any driver change: a userspace/kernel mismatch fails it for an unrelated reason
and sends you down the wrong layer.

## 1. Decide which build-deps tag to pin
The encoder API level comes from `nvEncodeAPI.h` inside the `LizardByte/build-deps` tag that
`third-party/build-deps` points at, and that same tag supplies the prebuilt ffmpeg — so the TAG, not
the release, decides the required driver.
```bash
# list candidate tags, newest first
curl -s "https://api.github.com/repos/LizardByte/build-deps/releases?per_page=15" | \
  python3 -c "import json,sys;[print(r['tag_name'],r['published_at'][:10]) for r in json.load(sys.stdin)]"
# verify what a tag carries: MINOR 0 == driver 595-class, MINOR 1 == needs 610+
find third-party/build-deps -name nvEncodeAPI.h -exec grep -m2 -E '(MINOR|MAJOR)_VERSION' {} \;
```
Pick the newest tag still reporting MINOR 0. Do not wait on the driver: hand-installing one is off
limits on this host, and the distro packages no 610 branch.

## 2. Get the build dependencies
Take the list from the spec in the source tree, not from a blog — `packaging/linux/copr/Sunshine.spec`
`BuildRequires:` is authoritative (cmake, qt6-qtbase-devel, qt6-qtsvg-devel, libva-devel,
pipewire-devel, libcap-devel, libdrm-devel, libevdev-devel, openssl-devel, opus-devel, glslc,
vulkan-loader-devel, numactl-devel, miniupnpc-devel, pulseaudio-libs-devel, boost-devel, nodejs-npm,
uv, ImageMagick, xorg-x11-server-Xvfb, ...). Install with the nvidia packages excluded, or the
transaction can pull a pending driver upgrade and break NVML midway through your build:
```bash
sudo dnf5 install --assumeno ...                                     # read the transaction first
sudo dnf5 install -y --exclude='nvidia-*' --exclude='libnvidia-*' ...
```

## 3. Clone at the release tag, then pin build-deps one tag back
```bash
git clone --depth 1 --branch <release-tag> --recurse-submodules --shallow-submodules \
  https://github.com/LizardByte/Sunshine.git src
cd src/third-party/build-deps
git fetch --tags --depth 1 origin <older-tag>
git checkout <older-tag>
git submodule update --init --recursive --depth 1    # brings the matching nv-codec-headers
```
The pin is not cosmetic: that submodule supplies both the headers Sunshine compiles its NVENC
support against and the ffmpeg libraries it links.

## 4. Configure — the flags that are not obvious
```bash
cmake -S src -B src/cmake-build-nvenc \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_DOCS=OFF \
  -DCUDA_FAIL_ON_MISSING=OFF \
  -DGLAD_SKIP_PIP_INSTALL=ON \
  -DPython_EXECUTABLE="$PWD/src/cmake-build-nvenc/glad-python/bin/python"
```
- **`CUDA_FAIL_ON_MISSING=OFF`.** A missing CUDA toolkit is a hard configure error by default, but
the Linux NVENC encoder does not need it: the encoder comes from ffmpeg, and without
`SUNSHINE_BUILD_CUDA` the pipewire path skips its CUDA branch and hands the encoder the generic
`avcodec_encode_device_t` (system-memory upload) — the same path a memory-buffer setup already
used. Installing the toolkit means ~2 GB from the driver repo *and* it drags driver packages into
the transaction. Escalate to `cuda-nvcc` + `cuda-cudart-devel` and rebuild with CUDA enabled only
if NVENC still will not open.
- **The two glad flags.** Configure creates `<build>/glad-python` with jinja2, then runs the
GL-loader generation with the *system* interpreter, which has no jinja2 — the build dies near 3%
with `ModuleNotFoundError: No module named 'jinja2'`. Prepare that venv yourself and point the build
at it:
```bash
uv venv --python "$(command -v python3.14 || command -v python3)" <build>/glad-python
uv pip install --python <build>/glad-python/bin/python jinja2
```

## 5. Build incrementally
Do not wipe the build directory between attempts: the glad venv lives inside it and the compile
resumes where it stopped (`FRESH=1` to force a clean build). Keep the job count modest while a
stream may be live (`-j8` on a 28-thread box) and run it `nice -n 15` so a live session keeps its
CPU.

## 6. Smoke-test without touching the running service
```bash
tmp=$(mktemp -d)
timeout 25 src/cmake-build-nvenc/sunshine "$tmp/probe.conf" >"$tmp/out.log" 2>&1
grep -E 'Found (H\.264|HEVC|AV1) encoder|Driver does not support|Could not open codec' "$tmp/out.log"
```
Pass is `Found HEVC encoder: hevc_nvenc`. No display, no session, no service restart: the encoder
probe runs against a scratch config. `Driver does not support the required nvenc API version` still
appearing means the pin did not take effect — stop and re-check step 1.

## 7. Install with a trivial rollback
Leave the packaged build installed. Put the local binary somewhere stable and point the unit at it
with a drop-in `ExecStart=` override, so reverting is deleting one file plus `daemon-reload`.
Re-apply `setcap` to whichever binary actually runs (the effective bit is file-wide, so keep it a
single clause), and after the switch read the journal for the `Found ... encoder` line instead of
trusting a successful start — the selected encoder changes silently, which is how this whole
problem stays invisible in the first place.
