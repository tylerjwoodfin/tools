# Local model

Cherry's primary model is `lmstudio/gemma4-26b`. LM Studio answers `400 No models loaded` when that model is not in memory, and OpenClaw records the failure as `format` and falls back to OpenAI.

This plugin loads Gemma before a turn, with a 32,768 context so a normal Cherry prompt fits. A LaunchAgent does the same at login and every 15 minutes, so the first message of the day is not the one that pays the load.

Gemma 4 thinks by default and can spend the whole reply in `reasoning_content`, which OpenClaw treats as an empty answer and falls back. Install sets `models.providers.lmstudio` model `gemma4-26b` `params.extra_body.reasoning_effort` to `none`.

If the weights on `/Volumes/2TB` are missing, it does nothing and the OpenAI fallback stays in place.
