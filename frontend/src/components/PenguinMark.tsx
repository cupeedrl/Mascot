import { useId } from "react";

interface PenguinMarkProps {
  size?: number;
  className?: string;
  decorative?: boolean;
  variant?: "default" | "scholar" | "learning";
}

// Below this size the mark drops fine details and enlarges the penguin so it stays legible.
const DETAIL_MIN_SIZE = 48;
const COMPACT_TRANSFORM = "translate(32 58) scale(1.12) translate(-32 -58)";

const INK = "#2F2674";
const CAP = "#1B1640";
const FACE = "#FFFFFF";
const BEAK = "#6658E8";
const ACCENT = "#A89DF7";
const HIGHLIGHT = "#F1EFFF";
const TASSEL = "#EBE8FF";
const CAP_TRIM = "#F7C948";
const PENCIL_BODY = "#F7C948";
const PENCIL_FERRULE = "#FFF3D0";
const PENCIL_WOOD = "#FFE3AE";
const PENCIL_ERASER = "#E8705F";
const BOOK_COVER = "#2F7FD1";
const BOOK_LINE = "#8DB8EA";

export function PenguinMark({
  size = 40,
  className = "",
  decorative = true,
  variant = "default",
}: PenguinMarkProps) {
  const gradientId = `penguin-badge-${useId().replace(/:/g, "")}`;
  const isScholar = variant === "scholar" || variant === "learning";
  const detailed = size >= DETAIL_MIN_SIZE;
  const svgProps = {
    className: `penguin-mark${isScholar ? " penguin-mark-scholar" : ""}${detailed ? "" : " penguin-mark-compact"}${className ? ` ${className}` : ""}`,
    width: size,
    height: size,
    viewBox: "0 0 64 64",
    fill: "none",
    role: decorative ? undefined : "img",
    "aria-hidden": decorative ? ("true" as const) : undefined,
    xmlns: "http://www.w3.org/2000/svg",
  };

  const artwork = (
    <>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6658E8" />
          <stop offset="1" stopColor="#5044C8" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${gradientId})`} />

      <g transform={detailed ? undefined : COMPACT_TRANSFORM}>
        {/* Flippers, body and the two-lobed face of the same penguin in every variant */}
        <path d="M15.5 38.5C12 41 10.8 45.5 12.2 49c3-.4 5.2-2.9 5.8-6.4Z" fill={INK} />
        {detailed ? (
          <path d="M46.4 38.6c2.6-2.6 6.4-4.6 8.3-3 1.9 1.6.2 5.2-2.6 7.8-1.7 1.5-3.6 2.4-4.8 2Z" fill={INK} />
        ) : (
          <path d="M48.5 38.5C52 41 53.2 45.5 51.8 49c-3-.4-5.2-2.9-5.8-6.4Z" fill={INK} />
        )}
        <path d="M32 12C20.8 12 14.5 21.6 14.5 33v11c0 6.6 5.4 12 12 12h11c6.6 0 12-5.4 12-12V33C49.5 21.6 43.2 12 32 12Z" fill={INK} />
        <path
          d="M32 22.2c-4.6-3.6-12-1.6-12 5.6 0 3.3 1.5 5.8 3.6 7.3-2.4 2.4-3.9 5.8-3.9 9.6 0 5.6 4 9.3 9.6 9.3h5.4c5.6 0 9.6-3.7 9.6-9.3 0-3.8-1.5-7.2-3.9-9.6 2.1-1.5 3.6-4 3.6-7.3 0-7.2-7.4-9.2-12-5.6Z"
          fill={FACE}
        />
        <circle cx="26.8" cy="29" r="2.5" fill={INK} />
        <circle cx="37.2" cy="29" r="2.5" fill={INK} />
        {detailed && (
          <>
            <circle cx="27.6" cy="28.1" r="0.85" fill={FACE} />
            <circle cx="38" cy="28.1" r="0.85" fill={FACE} />
            <ellipse cx="23.2" cy="33.6" rx="2.2" ry="1.3" fill={ACCENT} opacity="0.45" />
            <ellipse cx="40.8" cy="33.6" rx="2.2" ry="1.3" fill={ACCENT} opacity="0.45" />
          </>
        )}
        <path d="M28.9 32.3c1.9-1.3 4.3-1.3 6.2 0-.8 2-1.9 3.4-3.1 3.4s-2.3-1.4-3.1-3.4Z" fill={BEAK} />

        {/* Every variant wears the graduation cap so the mascot looks the same across the app.
            The gold trim is thicker on compact renders so it survives at 24-40px. */}
        <g transform="translate(0 -2.2) rotate(-9 32 15.2)">
          {/* Crown first, then the board on top, so the cap reads as a real mortarboard. */}
          <path d="M24.4 14.6h15.2v6.4c0 2.3-3.4 3.4-7.6 3.4s-7.6-1.1-7.6-3.4Z" fill="#241E52" />
          <path
            d="M24.4 20.6c0 2.3 3.4 3.4 7.6 3.4s7.6-1.1 7.6-3.4"
            fill="none"
            stroke={CAP_TRIM}
            strokeWidth={detailed ? 1.1 : 1.6}
            strokeLinecap="round"
          />
          <path d="M16.5 15.2 32 9l15.5 6.2L32 21.4Z" fill={CAP} stroke={CAP_TRIM} strokeWidth={detailed ? 1.3 : 1.9} strokeLinejoin="round" />
          <path d="M32 15.2c5.6.4 9.6 2.6 11 7.6" stroke={TASSEL} strokeWidth={detailed ? 1.1 : 1.5} strokeLinecap="round" />
          <circle cx="43.2" cy="23.4" r={detailed ? 1.5 : 1.8} fill={TASSEL} />
        </g>

        {detailed && (
          <>
            <path d="M20.5 45.4 32 43.3l11.5 2.1v8.2L32 51.5l-11.5 2.1Z" fill={BOOK_COVER} />
            <path d="M21.6 45.1 31 43.4v7.1l-9.4 1.7Z" fill={FACE} />
            <path d="M33 43.4l9.4 1.7v6.8L33 50.5Z" fill={FACE} />
            <path d="M23.8 46.8h5M23.8 48.8h4M35.2 46.8h5M35.2 48.8h4" stroke={BOOK_LINE} strokeWidth="0.9" strokeLinecap="round" />
            <path d="M50.5 34.5 51.6 37.1l2.6 1.1-2.6 1.1-1.1 2.6-1.1-2.6-2.6-1.1 2.6-1.1Z" fill={HIGHLIGHT} />

            {/* Pencil held in the raised flipper; the flipper tip is drawn last so it grips the barrel. */}
            <g transform="translate(48 44.2) rotate(-58)">
              <rect x="-3.4" width="3.4" height="4.6" rx="1.2" fill={PENCIL_ERASER} />
              <rect width="13" height="4.6" rx="1" fill={PENCIL_BODY} />
              <rect x="10.4" width="1.8" height="4.6" fill={PENCIL_FERRULE} />
              <path d="M13 0 18.4 2.3 13 4.6Z" fill={PENCIL_WOOD} />
              <path d="M16.6 1.5 18.4 2.3 16.6 3.1Z" fill={INK} />
            </g>
            <path d="M50.4 37.4c1.9-.6 3.8.4 4.3 2 .5 1.7-.6 3.3-2.5 3.7-1.6.3-3-.5-3.4-1.9-.4-1.5.4-3.2 1.6-3.8Z" fill={INK} />
          </>
        )}
      </g>
    </>
  );

  if (isScholar) {
    return (
      <svg {...svgProps} aria-label={decorative ? undefined : "Mascot scholar penguin"}>
        {artwork}
      </svg>
    );
  }

  return (
    <svg {...svgProps} aria-label={decorative ? undefined : "Mascot penguin"}>
      {artwork}
    </svg>
  );
}
