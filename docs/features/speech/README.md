# Speech to text

A voice note in the main chat is transcribed and then routed exactly like a
typed message — the same classification, the same worklog parsing, the same
assistant tools. Voice is an input, not a parallel feature.

## The pipeline

```
Telegram voice/audio
  → download to a scratch directory
  → audio stages        (settings: speech_audio_stages)
  → transcriber         (settings: speech_provider + speech_model)
  → text stages         (settings: speech_text_stages)
  → handle_text_message (the ordinary text path)
```

Every arrow is an interface. `TranscriberInterface`, `AudioStageInterface`
and `TextStageInterface` live in `use_cases/interfaces/transcriber_interface.py`;
`TranscribeVoiceUseCase` orchestrates them and knows no provider by name.

## Swapping the backend

Set `SPEECH_PROVIDER` in `.env`. The name must exist in `TRANSCRIBERS` in
`adapters/speech/registry.py`; an unknown name raises at startup rather than
failing on the first voice message.

To add a backend:

1. Implement `TranscriberInterface` in `adapters/speech/`.
2. Add one line to `TRANSCRIBERS`.

Nothing else changes — not the handler, not the use case, not the settings
class. A local model (faster-whisper, vosk) needs only `accepts` to exclude
`oga`, and the normalisation stage already converts to 16 kHz mono WAV.

## Adding a processing stage

Implement `AudioStageInterface` or `TextStageInterface`, register it in
`AUDIO_STAGES` / `TEXT_STAGES`, and name it in `speech_audio_stages` or
`speech_text_stages`. Stages run in the order listed.

A stage that fails is **logged and skipped**, never fatal: an optional
improvement must not cost a usable recording. A stage that cannot help
should return what it was given rather than raise.

### What ships today

| Stage | Kind | Why |
|---|---|---|
| `normalise` | audio | Re-encodes to 16 kHz mono WAV via ffmpeg. Telegram sends Opus in `.oga`; not every backend takes it, and a local model generally will not. |
| `persian_digits` | text | «چهار ساعت» → «4 ساعت». Every downstream reader of a worklog looks for a number, so a spelled-out one is invisible. |
| `vocabulary` | text | Repairs team terms a hosted model has never seen. A project name that is close but wrong defeats the alias table, which matches exact strings. |

Deliberately not built yet: silence trimming, VAD, loudness normalisation,
denoising. Each is a new stage class when a real recording shows it is
needed — none is validated against this team's audio today.

## Settings

All prefixed `SPEECH_` in `.env`. See `settings/speech_settings.py` for
defaults and the reasoning behind each.

| Setting | Default | Notes |
|---|---|---|
| `SPEECH_PROVIDER` | `openai_whisper` | Must be a registered name |
| `SPEECH_MODEL` | `whisper-1` | `gpt-4o-transcribe` is better on Persian, and costs more |
| `SPEECH_LANGUAGE` | `fa` | `None` lets the model detect, which is less reliable on short clips |
| `SPEECH_MAX_SECONDS` | `600` | Refused before upload |
| `SPEECH_MAX_BYTES` | `26214400` | OpenAI's own limit |
| `SPEECH_TIMEOUT_SECONDS` | `120` | |

## ffmpeg

Installed in the Dockerfile. Without it the normalisation stage logs a
warning and passes the recording through unchanged — which the OpenAI
backend tolerates, since it accepts `.oga`, but a local backend would not.
