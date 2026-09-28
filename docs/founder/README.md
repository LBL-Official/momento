# Founder print pack

Print **[`MOMENTO-TRADING-DESK.md`](MOMENTO-TRADING-DESK.md)** as one document.

That file is written for paper: short sections, flowcharts, tables, and a
glossary. It describes the desk as it exists in source today, including
placeholders. It does not change trading behavior.

## How to print

1. Open `docs/founder/MOMENTO-TRADING-DESK.md`.
2. Export to PDF from the editor (Print → Save as PDF), or:

```sh
# if you have pandoc
pandoc docs/founder/MOMENTO-TRADING-DESK.md -o /tmp/momento-trading-desk.pdf
```

3. Print letter, portrait, with page numbers if the exporter supports them.

Engineer-facing specs remain in [`docs/architecture/`](../architecture/).
This pack is the founder overlay: *why*, *what talks to what*, *what is live*,
*what is still a hole*.
