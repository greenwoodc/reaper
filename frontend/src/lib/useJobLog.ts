"use client";

import { useEffect, useState } from "react";
import { getJobLog } from "./api";

const POLL_INTERVAL_MS = 1500;

/** Polls GET /api/jobs/<id>/log while enabled — used for an on-demand "view
 * log" disclosure rather than always-on, since most jobs don't need it. */
export function useJobLog(jobId: string | null, enabled: boolean): string[] {
  const [log, setLog] = useState<string[]>([]);

  useEffect(() => {
    if (!jobId || !enabled) {
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const { log: lines } = await getJobLog(jobId as string);
        if (cancelled) return;
        setLog(lines);
      } finally {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId, enabled]);

  return log;
}
