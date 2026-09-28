# Systimo governance (transition loop)

```text
Ballhog → Positman     QUERY
TK Ultra → Positman    QUERY
Positman → Drevo       QUERY
Positman → Jump        QUERY (WRITE DENY)
Drevo → Jump           QUERY (WRITE DENY)
Positman → Systimo     WRITE (artifact / observability)
Drevo → Systimo        WRITE (artifact / observability)
Orchestra → Systimo    QUERY
Orchestra → Vital      CONTROL DENY
```

Write/control default deny except the listed audit appends.
