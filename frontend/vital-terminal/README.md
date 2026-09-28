# Vital Terminal

Separate dashboard instance for Momento algorithmic execution.

```text
ROLLER / SuperASI / Jump   →  frontend/roller-terminal  :5179
Vital                      →  frontend/vital-terminal   :5180
API                        →  ROLLER/scripts/terminal_api.py :8791
```

Jump calls Vital over `/vital/*`. This UI is not a product tab inside ROLLER.

```bash
npm install
npm run dev
```

Opens `http://127.0.0.1:5180`. The browser never submits Kalshi orders.

The dashboard talks to `/vital/*` on `:8791`. The API CORS list includes
`http://127.0.0.1:5180`. Jump remains a client: it calls that API and
opens this origin.
