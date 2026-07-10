/** Large, low-opacity watermark of the Reaper mark, fixed behind wizard
 * content so the brand stays present without competing with form text. */
export default function HeroBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 flex items-center justify-center overflow-hidden"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- fixed decorative bg, not content */}
      <img
        src="/reaper-hero.png"
        alt=""
        className="h-[130vh] w-auto max-w-none opacity-[0.07] grayscale-0"
      />
    </div>
  );
}
