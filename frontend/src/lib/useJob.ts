"use client";

import { useEffect, useState } from "react";
import { getJob } from "./api";
import type { Job } from "./types";

const POLL_INTERVAL_MS = 1000;

/** Polls GET /api/jobs/<id> while the job is queued/running; stops once
 * it reaches a terminal (done/error) or paused (awaiting_confirmation) state. */
export function useJob(jobId: string | null): Job | null {
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const j = await getJob(jobId as string);
        if (cancelled) return;
        setJob(j);
        if (j.status === "queued" || j.status === "running") {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS * 2);
      }
    }

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return jobId ? job : null;
}
