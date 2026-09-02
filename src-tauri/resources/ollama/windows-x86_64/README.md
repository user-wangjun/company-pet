# Bundled Ollama runtime

This directory is populated by `scripts/prepare-ollama-runtime.mjs` during a
Windows x64 Tauri bundle. The build hook downloads the pinned official
standalone Ollama archive and verifies its SHA-256 before adding it to the
installer resources.

The executable and runtime libraries are intentionally not committed to the
repository. A released installer contains them, starts `ollama.exe serve`
automatically on a private loopback port, and stores model files in the
application data directory.

Ollama is distributed under the MIT license; the pinned runtime is copied
unchanged from the official release. Models downloaded at runtime are
third-party artifacts and keep their own model-specific licenses.
