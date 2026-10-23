import Image from "next/image";

/** Large, low-opacity watermark of the Reaper mark, fixed behind wizard
 * content so the brand stays present without competing with form text.
 * next/image (not a raw <img>) so the 619 KB source PNG is served as a
 * resized WebP/AVIF, and shares a cache entry with the dashboard hero. */
export default function HeroBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 flex items-center justify-center overflow-hidden"
    >
      <Image
        src="/reaper-hero.png"
        alt=""
        width={643}
        height={668}
        sizes="130vh"
        className="h-[130vh] w-auto max-w-none opacity-[0.07]"
      />
    </div>
  );
}
