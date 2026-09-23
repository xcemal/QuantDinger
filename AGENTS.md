# Codex project notes

This is the saved local Codex project for the running QuantDinger installation.
Use this repository root (`/Users/cemal/Documents/pc/QuantDinger`) when the user
selects the QuantDinger project in a new task. The similarly named folder under
`/Users/cemal/Documents/Codex/` is a Codex task workspace, not this repository.

## Local Docker installation

- The Compose project name is `quantdinger`; the live stack is defined by
  `docker-compose.yml` plus `docker-compose.build.yml`.
- Check `docker info` before using Docker. If the daemon is unavailable, ask the
  user to start Docker Desktop/Colima before trying Compose operations.
- `bash tools/quantdinger-start.sh` starts the local stack and health-checks it.
  `bash tools/quantdinger-stop.sh` stops it while preserving database volumes.
- Backend source is copied into the image at build time, not bind-mounted.
  After backend source changes, rebuild and recreate the backend and worker
  services with the Compose files above. `backend.env` is bind-mounted; never
  print or expose its contents.
- The default frontend image is prebuilt from GHCR. Local `QuantDinger-Vue`
  source is built through `docker-compose.build.yml` when present.
- Do not use `docker compose down -v`, delete volumes, or run live trades unless
  the user explicitly asks for that specific action.

