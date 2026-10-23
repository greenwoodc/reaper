"use client";

import { useEffect, useRef, useState } from "react";
import Stepper, { STEPS } from "./Stepper";
import UploadStep from "./UploadStep";
import DownloadStep from "./DownloadStep";
import FinalizeStep from "./FinalizeStep";
import HeroBackground from "./HeroBackground";
import { btnText } from "@/lib/ui";

interface WizardProps {
  initialSlug: string | null;
  initialPlaylistName: string;
  initialStep: 1 | 2 | 3;
  onExit: () => void;
}

const STEP_DESCRIPTIONS: Record<1 | 2 | 3, string> = {
  1: "Upload an Exportify CSV (a Spotify playlist export). Reaper searches your Navidrome library for every track and sorts them into found vs. missing.",
  2: "Missing tracks get their search terms cleaned up, then Reaper downloads them via Soulseek and imports the results into your library with beets. This can take a while: downloads run one at a time in the background.",
  3: "Navidrome is rescanned to pick up the newly imported files, then Reaper creates (or updates) the Navidrome playlist with everything it found, in your chosen order.",
};

export default function Wizard({
  initialSlug,
  initialPlaylistName,
  initialStep,
  onExit,
}: WizardProps) {
  const [slug, setSlug] = useState<string | null>(initialSlug);
  const [playlistName, setPlaylistName] = useState(initialPlaylistName);
  const [step, setStep] = useState<1 | 2 | 3>(initialStep);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Move focus to the heading on entry and on every step change, so keyboard
  // and screen reader users land on the new content rather than on a button
  // that was just unmounted. (The wizard is never the initial page view,
  // so focusing on mount doesn't steal focus from a fresh page load.)
  useEffect(() => {
    headingRef.current?.focus();
  }, [step]);

  const stepLabel = STEPS.find((s) => s.id === step)?.label;

  return (
    <div className="flex w-full flex-col items-center gap-10">
      <HeroBackground />
      <div className="flex w-full">
        <button
          type="button"
          onClick={onExit}
          className={`${btnText} text-[var(--color-muted)] hover:text-[var(--color-text)]`}
        >
          ← All playlists
        </button>
      </div>

      <div className="flex max-w-xl flex-col items-center gap-2 text-center">
        <h1
          ref={headingRef}
          tabIndex={-1}
          className="break-words font-[family-name:var(--font-display)] text-3xl tracking-wide text-[var(--color-text)] focus:outline-none sm:text-4xl"
        >
          {playlistName || "New playlist"}
        </h1>
        {/* The stepper hides its labels below sm, so name the step here instead. */}
        <p className="text-xs font-semibold uppercase tracking-widest text-[var(--color-accent-text)] sm:hidden">
          Step {step} of 3 · {stepLabel}
        </p>
      </div>

      <Stepper activeStep={step} clickable={!!slug} onStepClick={setStep} />

      <p className="max-w-xl text-center text-sm text-[var(--color-muted)]">
        {STEP_DESCRIPTIONS[step]}
      </p>

      <div className="flex w-full flex-1 items-center justify-center py-8">
        {step === 1 && (
          <UploadStep
            onStarted={setPlaylistName}
            onScanned={(newSlug, newName, missingCount) => {
              setSlug(newSlug);
              setPlaylistName(newName);
              setStep(missingCount > 0 ? 2 : 3);
            }}
          />
        )}
        {step === 2 && slug && <DownloadStep slug={slug} onDone={() => setStep(3)} />}
        {step === 3 && slug && <FinalizeStep slug={slug} playlistName={playlistName} />}
      </div>
    </div>
  );
}
