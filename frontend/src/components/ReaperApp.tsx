"use client";

import { useState } from "react";
import PlaylistDashboard from "./PlaylistDashboard";
import Wizard from "./Wizard";

type View =
  | { mode: "dashboard" }
  | { mode: "wizard"; slug: string | null; playlistName: string; step: 1 | 2 | 3 };

export default function ReaperApp() {
  const [view, setView] = useState<View>({ mode: "dashboard" });

  if (view.mode === "wizard") {
    return (
      <Wizard
        initialSlug={view.slug}
        initialPlaylistName={view.playlistName}
        initialStep={view.step}
        onExit={() => setView({ mode: "dashboard" })}
      />
    );
  }

  return (
    <PlaylistDashboard
      onSelect={(slug, playlistName, step) => setView({ mode: "wizard", slug, playlistName, step })}
      onNew={() => setView({ mode: "wizard", slug: null, playlistName: "", step: 1 })}
    />
  );
}
