# Momento Research Console

Internal research control plane. Not the public website. Not a trading UI.

The console submits experiment specifications to `momento-research-api`.
Statistical work stays in the Rust research engine.

## Local

From the repository root:

```sh
./scripts/dev-research.sh
```

Or in two terminals:

```sh
MOMENTO_RESEARCH_TOKEN=momento-local cargo run -p momento-research-api
cd frontend/research-console && npm install && npm run dev
```

Open `http://127.0.0.1:5173`. Default token: `momento-local`
(`x-research-token` / `MOMENTO_RESEARCH_TOKEN`).

CLI and dashboard share the same engine:

```sh
./target/release/momento-research-b1 --search-83-exhaustive --first-exact-83
./target/release/momento-research-b1 --run-experiment path/to/experiment.json
```
