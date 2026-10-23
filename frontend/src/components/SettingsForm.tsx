"use client";

import { useEffect, useId, useState } from "react";
import Link from "next/link";
import { getSettings, updateSettings } from "@/lib/api";
import type { Settings, SettingsUpdate } from "@/lib/types";
import { btnPrimary, btnText, inputClass } from "@/lib/ui";

const FORMATS = ["mp3", "flac", "ogg", "wav", "m4a", "opus"];

const checkboxRowClass = "flex items-start gap-3 text-sm text-[var(--color-text)]";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-4 border-t border-[var(--color-border)] pt-6 first:border-t-0 first:pt-0">
      <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-accent-text)]">
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

/** Wraps a single control in a real <label>, so it gets an accessible
 * name and clicking the text focuses the input. */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-[var(--color-text)]">{label}</span>
      {children}
    </label>
  );
}

/** For a set of controls (e.g. toggle buttons) that can't share one <label>. */
function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  const id = useId();
  return (
    <div role="group" aria-labelledby={id} className="flex flex-col gap-1.5">
      <span id={id} className="text-sm font-medium text-[var(--color-text)]">
        {label}
      </span>
      {children}
    </div>
  );
}

function formatPillClass(active: boolean) {
  return `inline-flex min-h-9 cursor-pointer items-center rounded-full border px-4 text-xs font-medium transition-colors ${
    active
      ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-accent-contrast)]"
      : "border-[var(--color-control-border)] text-[var(--color-muted)] hover:border-[var(--color-accent-text)]"
  }`;
}

export default function SettingsForm() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const hintId = useId();

  const [navUrl, setNavUrl] = useState("");
  const [navUser, setNavUser] = useState("");
  const [navPassword, setNavPassword] = useState("");
  const [matchThreshold, setMatchThreshold] = useState(0.8);
  const [playlistOrder, setPlaylistOrder] = useState<"asc" | "desc">("desc");
  const [slskUser, setSlskUser] = useState("");
  const [slskPassword, setSlskPassword] = useState("");
  const [formats, setFormats] = useState<string[]>([]);
  const [prefFormat, setPrefFormat] = useState("flac");
  const [prefMinBitrate, setPrefMinBitrate] = useState("256");
  const [desperate, setDesperate] = useState(true);
  const [skipExisting, setSkipExisting] = useState(true);
  const [mediaRoot, setMediaRoot] = useState("");
  const [incomingDir, setIncomingDir] = useState("");
  const [puid, setPuid] = useState("1000");
  const [pgid, setPgid] = useState("1000");
  const [concurrentJobs, setConcurrentJobs] = useState("3");
  const [concurrentSearches, setConcurrentSearches] = useState("3");
  const [searchesPerTime, setSearchesPerTime] = useState("4");
  const [searchesRenewTime, setSearchesRenewTime] = useState("120");
  const [searchTimeout, setSearchTimeout] = useState("15000");
  const [maxStaleTime, setMaxStaleTime] = useState("15000");
  const [fastSearch, setFastSearch] = useState(false);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setSettings(s);
        setNavUrl(s.navidrome.url);
        setNavUser(s.navidrome.user);
        setMatchThreshold(s.matching.match_threshold);
        setPlaylistOrder(s.matching.playlist_order);
        setSlskUser(s.soulseek.username);
        setFormats(
          s.download.format
            .split(",")
            .map((f) => f.trim())
            .filter(Boolean),
        );
        setPrefFormat(s.download.pref_format);
        setPrefMinBitrate(s.download.pref_min_bitrate);
        setDesperate(s.download.desperate);
        setSkipExisting(s.download.skip_existing);
        setMediaRoot(s.paths.media_root);
        setIncomingDir(s.paths.incoming_dir);
        setPuid(s.paths.puid);
        setPgid(s.paths.pgid);
        setConcurrentJobs(s.advanced.concurrent_jobs);
        setConcurrentSearches(s.advanced.concurrent_searches);
        setSearchesPerTime(s.advanced.searches_per_time);
        setSearchesRenewTime(s.advanced.searches_renew_time);
        setSearchTimeout(s.advanced.search_timeout);
        setMaxStaleTime(s.advanced.max_stale_time);
        setFastSearch(s.advanced.fast_search);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load settings."));
  }, []);

  function toggleFormat(fmt: string) {
    setFormats((prev) => (prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt]));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaving(true);
    setSaved(false);

    const update: SettingsUpdate = {
      navidrome: {
        url: navUrl,
        user: navUser,
        ...(navPassword ? { password: navPassword } : {}),
      },
      matching: { match_threshold: matchThreshold, playlist_order: playlistOrder },
      soulseek: {
        username: slskUser,
        ...(slskPassword ? { password: slskPassword } : {}),
      },
      download: {
        format: formats.join(","),
        pref_format: prefFormat,
        pref_min_bitrate: Number(prefMinBitrate),
        desperate,
        skip_existing: skipExisting,
      },
      advanced: {
        concurrent_jobs: Number(concurrentJobs),
        concurrent_searches: Number(concurrentSearches),
        searches_per_time: Number(searchesPerTime),
        searches_renew_time: Number(searchesRenewTime),
        search_timeout: Number(searchTimeout),
        max_stale_time: Number(maxStaleTime),
        fast_search: fastSearch,
      },
      paths: { media_root: mediaRoot, incoming_dir: incomingDir, puid, pgid },
    };

    try {
      const updated = await updateSettings(update);
      setSettings(updated);
      setNavPassword("");
      setSlskPassword("");
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="flex w-full max-w-2xl flex-col items-center gap-4 text-center">
        <p role="alert" className="text-sm text-[var(--color-error)]">
          {loadError}
        </p>
        <Link href="/" className={`${btnText} text-[var(--color-muted)] hover:text-[var(--color-text)]`}>
          ← Back
        </Link>
      </div>
    );
  }

  if (!settings) {
    return (
      <p role="status" className="text-sm text-[var(--color-muted)]">
        Loading settings...
      </p>
    );
  }

  return (
    <form onSubmit={handleSave} className="flex w-full max-w-2xl flex-col gap-8 pb-16">
      <div className="flex items-center justify-between">
        <Link href="/" className={`${btnText} text-[var(--color-muted)] hover:text-[var(--color-text)]`}>
          ← Back
        </Link>
        <h1 className="font-[family-name:var(--font-display)] text-3xl tracking-wide text-[var(--color-accent-text)]">
          Settings
        </h1>
      </div>

      <Section title="Navidrome">
        <Field label="Server URL">
          <input
            type="url"
            value={navUrl}
            onChange={(e) => setNavUrl(e.target.value)}
            required
            placeholder="http://localhost:4533/"
            className={inputClass}
          />
        </Field>
        <Field label="Username">
          <input type="text" value={navUser} onChange={(e) => setNavUser(e.target.value)} required className={inputClass} />
        </Field>
        <Field label="Password">
          <input
            type="password"
            value={navPassword}
            onChange={(e) => setNavPassword(e.target.value)}
            placeholder={settings.navidrome.password_set ? "•••••••• (leave blank to keep)" : "Not set"}
            autoComplete="new-password"
            className={inputClass}
          />
        </Field>
      </Section>

      <Section title="Matching">
        <Field label={`Match threshold (${matchThreshold.toFixed(2)})`}>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={matchThreshold}
            onChange={(e) => setMatchThreshold(Number(e.target.value))}
            className="w-full accent-[var(--color-accent)]"
          />
        </Field>
        <Field label="Playlist order">
          <select
            value={playlistOrder}
            onChange={(e) => setPlaylistOrder(e.target.value as "asc" | "desc")}
            className={inputClass}
          >
            <option value="desc">Countdown (highest rank first, #1 last)</option>
            <option value="asc">Ascending (#1 first)</option>
          </select>
        </Field>
      </Section>

      <Section title="Soulseek">
        <Field label="Username">
          <input type="text" value={slskUser} onChange={(e) => setSlskUser(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Password">
          <input
            type="password"
            value={slskPassword}
            onChange={(e) => setSlskPassword(e.target.value)}
            placeholder={settings.soulseek.password_set ? "•••••••• (leave blank to keep)" : "Not set"}
            autoComplete="new-password"
            className={inputClass}
          />
        </Field>
      </Section>

      <Section title="Download preferences">
        <FieldGroup label="Accepted file types">
          <div className="flex flex-wrap gap-2">
            {FORMATS.map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => toggleFormat(fmt)}
                aria-pressed={formats.includes(fmt)}
                className={formatPillClass(formats.includes(fmt))}
              >
                {fmt}
              </button>
            ))}
          </div>
        </FieldGroup>
        <Field label="Preferred format">
          <select value={prefFormat} onChange={(e) => setPrefFormat(e.target.value)} className={inputClass}>
            {FORMATS.map((fmt) => (
              <option key={fmt} value={fmt}>
                {fmt}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Preferred minimum bitrate (kbps)">
          <input
            type="number"
            min={0}
            step={32}
            value={prefMinBitrate}
            onChange={(e) => setPrefMinBitrate(e.target.value)}
            className={inputClass}
          />
        </Field>
        <label className={checkboxRowClass}>
          <input
            type="checkbox"
            checked={desperate}
            onChange={(e) => setDesperate(e.target.checked)}
            className="mt-0.5 accent-[var(--color-accent)]"
          />
          <span>
            Desperate search
            <span className="block text-xs text-[var(--color-muted)]">
              Searches by title only and filters by artist afterward. Significantly improves hit rate,
              especially behind CGNAT.
            </span>
          </span>
        </label>
        <label className={checkboxRowClass}>
          <input
            type="checkbox"
            checked={skipExisting}
            onChange={(e) => setSkipExisting(e.target.checked)}
            className="mt-0.5 accent-[var(--color-accent)]"
          />
          <span>Skip tracks already present in the download folder</span>
        </label>
      </Section>

      <Section title="Media location">
        <Field label="Media root directory (host path)">
          <input
            type="text"
            value={mediaRoot}
            onChange={(e) => setMediaRoot(e.target.value)}
            placeholder="/mnt/media"
            aria-describedby={`${hintId}-media`}
            className={inputClass}
          />
        </Field>
        <p id={`${hintId}-media`} className="text-xs text-[var(--color-muted)]">
          Mounted into the Soulseek container as <code>/data</code>. Expects a <code>Music/</code> subfolder (your
          library). Changing this requires restarting the Docker container (<code>docker compose down</code> then
          re-running a download).
        </p>
        <Field label="Incoming directory (host path)">
          <input
            type="text"
            value={incomingDir}
            onChange={(e) => setIncomingDir(e.target.value)}
            placeholder={`${mediaRoot || "/mnt/media"}/incoming`}
            aria-describedby={`${hintId}-incoming`}
            className={inputClass}
          />
        </Field>
        <p id={`${hintId}-incoming`} className="text-xs text-[var(--color-muted)]">
          Staging area for fresh downloads awaiting beets import. Defaults to an <code>incoming/</code> subfolder of
          the media root above, but can point elsewhere (e.g. a faster disk). It&rsquo;s mounted into the Soulseek
          container separately from the media root.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <Field label="User ID (PUID)">
            <input
              type="text"
              inputMode="numeric"
              value={puid}
              aria-describedby={`${hintId}-ids`}
              onChange={(e) => setPuid(e.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Group ID (PGID)">
            <input
              type="text"
              inputMode="numeric"
              value={pgid}
              aria-describedby={`${hintId}-ids`}
              onChange={(e) => setPgid(e.target.value)}
              className={inputClass}
            />
          </Field>
        </div>
        <p id={`${hintId}-ids`} className="text-xs text-[var(--color-muted)]">
          Must match the owner of the folders above (check with <code>id -u</code> / <code>id -g</code> on the
          host). The Soulseek container writes files as this user so beets can read and move them afterward.
          Defaults to 1000, the first regular user on most Linux distros.
        </p>
      </Section>

      <div className="flex flex-col gap-4 border-t border-[var(--color-border)] pt-6">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
          className={`${btnText} self-start text-[var(--color-accent-text)] hover:opacity-80`}
        >
          {showAdvanced ? "Hide" : "Show"} advanced tuning
        </button>
        {showAdvanced && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Concurrent downloads">
              <input
                type="number"
                min={1}
                value={concurrentJobs}
                onChange={(e) => setConcurrentJobs(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Concurrent searches">
              <input
                type="number"
                min={1}
                value={concurrentSearches}
                onChange={(e) => setConcurrentSearches(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Searches per time window">
              <input
                type="number"
                min={1}
                value={searchesPerTime}
                onChange={(e) => setSearchesPerTime(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Search window renews after (s)">
              <input
                type="number"
                min={1}
                value={searchesRenewTime}
                onChange={(e) => setSearchesRenewTime(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Search timeout (ms)">
              <input
                type="number"
                min={1000}
                step={1000}
                value={searchTimeout}
                onChange={(e) => setSearchTimeout(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Max stale time (ms)">
              <input
                type="number"
                min={1000}
                step={1000}
                value={maxStaleTime}
                onChange={(e) => setMaxStaleTime(e.target.value)}
                className={inputClass}
              />
            </Field>
            <label className={checkboxRowClass}>
              <input
                type="checkbox"
                checked={fastSearch}
                onChange={(e) => setFastSearch(e.target.checked)}
                className="mt-0.5 accent-[var(--color-accent)]"
              />
              <span>Fast search (less thorough, quicker results)</span>
            </label>
          </div>
        )}
      </div>

      <div role="status" className="empty:hidden">
        {saveError && <p className="text-sm text-[var(--color-error)]">{saveError}</p>}
        {saved && !saveError && <p className="text-sm text-[var(--color-success)]">Settings saved.</p>}
      </div>

      <button type="submit" disabled={saving} className={`${btnPrimary} self-start`}>
        {saving ? "Saving..." : "Save settings"}
      </button>
    </form>
  );
}
