import { useCallback, useEffect, useState } from "react";
import { getDeskSettings, saveDeskSettings, type DeskSettings } from "../../api/warehouseResearch";

export function useDeskSettings() {
  const [bankrollDollars, setBankrollDollars] = useState(20000);
  const [allocationPct, setAllocationPct] = useState(5);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<DeskSettings | null>(null);

  const apply = useCallback((rec: DeskSettings) => {
    setBankrollDollars(rec.bankroll_dollars);
    setAllocationPct(rec.allocation_pct);
    setSaved(rec);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getDeskSettings()
      .then((rec) => {
        if (!cancelled) {
          apply(rec);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [apply]);

  const save = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      const rec = await saveDeskSettings({
        bankroll_dollars: bankrollDollars,
        allocation_pct: allocationPct,
      });
      apply(rec);
      return rec;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setSaving(false);
    }
  }, [allocationPct, apply, bankrollDollars]);

  return {
    bankrollDollars,
    setBankrollDollars,
    allocationPct,
    setAllocationPct,
    loaded,
    saving,
    error,
    saved,
    save,
  };
}
