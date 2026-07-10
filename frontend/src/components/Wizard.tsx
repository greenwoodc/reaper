"use client";

import { useState } from "react";
import Stepper from "./Stepper";
import UploadStep from "./UploadStep";
import DownloadStep from "./DownloadStep";
import FinalizeStep from "./FinalizeStep";
import HeroBackground from "./HeroBackground";

interface WizardProps {
  initialSlug: string | null;
  initialPlaylistName: string;
  initialStep: 1 | 2 | 3;
  onExit: () => void;
}

const STEP_DESCRIPTIONS: Record<1 | 2 | 3, string> = {
  1: "Upload an Exportify CSV (a Spotify playlist export). Reaper searches your Navidrome library for every track and sorts them into found vs. missing.",
  2: "Missing tracks get their search terms cleaned up, then Reaper downloads them via Soulseek and imports the results into your library with beets. This step can take a while — downloads happen one at a time in the background.",
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

  return (
    <div className="flex w-full flex-col items-center gap-10">
      <HeroBackground />
      <div className="flex w-full items-center justify-between">
        <button
          type="button"
          onClick={onExit}
          className="text-sm text-[var(--color-muted)] transition-colors hover:text-[var(--color-text)]"
        >
          ← All playlists
        </button>
        {playlistName && (
          <span className="text-sm font-medium text-[var(--color-text)]">{playlistName}</span>
        )}
      </div>

      <Stepper activeStep={step} clickable={!!slug} onStepClick={setStep} />

      <p className="max-w-xl text-center text-sm text-[var(--color-muted)]">
        {STEP_DESCRIPTIONS[step]}
      </p>

      <div className="flex w-full flex-1 items-center justify-center py-8">
        {step === 1 && (
          <UploadStep
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
