# Validation

Per reconstructed game (W2 engine + W3 gate):

- checksum matches committed SHA-256
- official gamePk observed or reconstruction fails
- chronological sequence
- duplicate source events recorded, not double-replayed
- impossible outs/score fail closed
- no lookahead on in-progress state
- provenance on events
- postponed/cancelled are SKIPPED, not fake zero-event games
- idempotent second run: same valid/event counts
