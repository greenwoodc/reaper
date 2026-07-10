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
