# Meeting-Recording Transcription in a Bare Container

Session-tested 2026-09-05: Teams meeting recording (MP4, 16.3 min, ~11.7 MB)
in a docker backend with NO ffmpeg/ffprobe, no torch, no sudo (uid 1000,
Debian-based python:3.11 image, pip only). Everything below installs as
`pip3 install` — no system packages needed.

## Working stack: faster-whisper (CPU, int8)

```
pip3 install faster-whisper        # pulls ctranslate2 + onnxruntime
```

- **Audio decode is built in** — `from faster_whisper.audio import
  decode_audio; a = decode_audio(mp4_path, sampling_rate=16000)` handles the
  MP4 without ffmpeg. Returns a float32 numpy array; slice it directly for
  partial transcription (`a[start*16000 : end*16000]`), no need to save/load.
- **Run in background** (`terminal(background=true, notify=true)`), then
  `process_manage(action='wait')`. Small model, 16-min audio: model load ~45 s
  (mostly HF download) + ~110 s transcription; write segments to JSON with
  periodic `flush=True` progress prints.
- **Settings that worked**: `language='en'`, `vad_filter=True`,
  `beam_size=5`. For re-passes over a slice use
  `condition_on_previous_text=False` to stop hallucination loops on silence.
- **Bugs to dodge**: (1) `json` is NOT auto-imported in `python3 -c` one-liners
  — import it or the run dies after minutes of transcribing; (2) `blkid: not
  found` on stderr is harmless ffmpeg-bridge noise.

## Silence gaps are usually real

Sparse output around a timestamp does not mean the model failed. This call had
a 5-minute stretch where a participant was stuck at immigration — re-passing
that span with the *medium* model recovered only two short lines and confirmed
true dead air. Always re-transcribe a suspicious gap with a bigger model and
VAD before treating it as a tooling failure; report it as
*[HH:MM – HH:MM — audio dead air]* rather than padding or dropping it.

## Merging re-passes

Keep the original JSON plus per-gap re-pass JSONs; merge by filtering the
original to exclude the re-passed span, concatenating, sorting on `start`, and
re-checking coverage (max inter-segment gap < ~20 s → full coverage).

## Speaker labels

faster-whisper gives no diarization. Labels like "**DG:**" must be marked
**inferred from context** in the deliverable header — do not present them as
fact. Quoting ASR text verbatim with `[corrections]` in brackets (e.g. "part to
production" → "path to production", "POV" → "proof of value") preserves audit
ability against the recording.

## Deliverable pair convention

`transcript.md` (timestamped lines `[mm:ss] **Speaker:** text`, header with
source filename, duration, method, caveats) + `summary.md` (purpose, key
decisions, action-items table with owners/dates, open questions, and a
call-item → doc-page cross-reference table when the meeting names product
features).

## See also

- `references/verification.md` — structural HTML verification and host-path
delivery.