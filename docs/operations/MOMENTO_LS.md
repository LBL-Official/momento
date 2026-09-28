# Momento LS

Direct observe of `momento-live.service`. Not Vital. Not Jump. Not ROLLER.
Not the System Maintenance product UI — that is Systimo `:5193`.

```text
browser :5181
  → Momento LS API :8792
  → read-only SSM
  → i-0f0849d5829476c31
  → momento-live.service
```

HTTP 200 is not RUNNING. Process up is not authorization.

## Surfaces

| Piece | Path / port |
|---|---|
| Dashboard | `frontend/momento-ls` `:5181` |
| API | `ROLLER/scripts/ls_api.py` `:8792` |
| Inspect | `ROLLER/roller/ls/` |

Routes: `/health`, `/observe`, `/snapshot`. No `/vital/*`. No submit.

## Run

```text
python3 ROLLER/scripts/ls_api.py
cd frontend/momento-ls && npm run dev
```

Open `http://127.0.0.1:5181`.

## Do not

- Import Vital UI or `/vital/*`.
- Set `VITAL_AWS_CONTROL`.
- Restart or write `momento-live.service`.
- Edit persist.
- Change FIRST01 / 80/81/83/89.
- Invent fills, $0, or RUNNING from an unread host.
