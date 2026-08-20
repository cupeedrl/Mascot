interface PenguinMarkProps {
  size?: number;
  className?: string;
  decorative?: boolean;
  variant?: "default" | "scholar" | "learning";
}

export function PenguinMark({
  size = 40,
  className = "",
  decorative = true,
  variant = "default",
}: PenguinMarkProps) {
  if (variant === "scholar" || variant === "learning") {
    return (
      <svg
        className={`penguin-mark penguin-mark-scholar${className ? ` ${className}` : ""}`}
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        role={decorative ? undefined : "img"}
        aria-hidden={decorative ? "true" : undefined}
        aria-label={decorative ? undefined : "Mascot scholar penguin"}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="mascotBadgeGradient" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
            <stop stopColor="#7565F0" />
            <stop offset="1" stopColor="#5545DC" />
          </linearGradient>
          <linearGradient id="bookCoverGradient" x1="21" y1="44" x2="43" y2="54" gradientUnits="userSpaceOnUse">
            <stop stopColor="#4F46E5" />
            <stop offset="1" stopColor="#3730A3" />
          </linearGradient>
        </defs>

        {/* Rounded badge background */}
        <rect width="64" height="64" rx="18" fill="url(#mascotBadgeGradient)" />

        {/* Penguin navy body */}
        <path
          d="M15 40C15 26.5 21.8 17.5 32 17.5s17 9 17 22.5v8A6.5 6.5 0 0 1 42.5 54.5h-21a6.5 6.5 0 0 1-6.5-6.5V40Z"
          fill="#24213F"
        />

        {/* White face and belly */}
        <path
          d="M21.5 32.5C21.5 25.5 26.2 21 32 21s10.5 4.5 10.5 11.5c0 3.2-1.2 5.9-3.2 7.7 2.9 2.4 4.7 5.9 4.7 9.8v.3c0 2.6-2.1 4.7-4.7 4.7H24.7a4.7 4.7 0 0 1-4.7-4.7V50c0-3.9 1.8-7.4 4.7-9.8a10.5 10.5 0 0 1-3.2-7.7Z"
          fill="#F8F7FF"
        />

        {/* Cheerful blushing cheeks */}
        <ellipse cx="23.5" cy="33.5" rx="2" ry="1.2" fill="#E8B4D9" opacity="0.65" />
        <ellipse cx="40.5" cy="33.5" rx="2" ry="1.2" fill="#E8B4D9" opacity="0.65" />

        {/* Expressive lively eyes with catchlights */}
        <circle cx="27" cy="30.5" r="2.2" fill="#24213F" />
        <circle cx="27.7" cy="29.8" r="0.75" fill="#FFFFFF" />
        <circle cx="37" cy="30.5" r="2.2" fill="#24213F" />
        <circle cx="37.7" cy="29.8" r="0.75" fill="#FFFFFF" />

        {/* Cheerful golden beak */}
        <path d="m32 33 4 3-4 2.5-4-2.5 4-3Z" fill="#FBBF24" />

        {/* Open Book in front */}
        <path
          d="M21 46.5 L32 44.5 L43 46.5 L43 54.5 L32 52.5 L21 54.5 Z"
          fill="url(#bookCoverGradient)"
        />
        <path
          d="M22 45.8 L31 44 L31 51.8 L22 53.4 Z"
          fill="#FFFFFF"
        />
        <path
          d="M33 44 L42 45.8 L42 53.4 L33 51.8 Z"
          fill="#FFFFFF"
        />
        {/* Book line notes */}
        <path
          d="M24 47.5h5M24 49.5h4M35 47.5h5M35 49.5h4"
          stroke="#A594F9"
          strokeWidth="0.8"
          strokeLinecap="round"
        />

        {/* Left and right wings holding the book */}
        <path d="M17 41c-2 4 1.5 8.5 5.5 7-1-3-3-5.5-5.5-7Z" fill="#24213F" />
        <path d="M47 41c2 4-1.5 8.5-5.5 7 1-3 3-5.5 5.5-7Z" fill="#24213F" />

        {/* Graduation cap / Mortarboard */}
        <path d="M26 17.5h12v3.5H26z" fill="#1C1838" />
        <path d="M17 16.5 32 10.5l15 6-15 6z" fill="#24213F" />
        <path d="M17 16.5 32 22.5l15-6" stroke="#3A3462" strokeWidth="0.8" fill="none" />
        <circle cx="32" cy="16.5" r="1.4" fill="#FBBF24" />
        {/* Golden Tassel */}
        <path d="M32 16.5 Q40.5 17.5 42.5 24.5" stroke="#FBBF24" strokeWidth="1.2" strokeLinecap="round" fill="none" />
        <circle cx="42.5" cy="25" r="1.3" fill="#F59E0B" />

        {/* Lively Sparkles */}
        <path d="M51 8.5 52.4 12 56 13.5 52.4 15 51 18.5 49.6 15 46 13.5 49.6 12Z" fill="#FDE68A" />
        <path d="M9 49.5 9.8 51.5 12 52.5 9.8 53.5 9 55.5 8.2 53.5 6 52.5 8.2 51.5Z" fill="#F8F7FF" opacity="0.85" />
      </svg>
    );
  }

  return (
    <svg
      className={`penguin-mark${className ? ` ${className}` : ""}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      role={decorative ? undefined : "img"}
      aria-hidden={decorative ? "true" : undefined}
      aria-label={decorative ? undefined : "Mascot penguin"}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect width="64" height="64" rx="18" fill="#6658E8" />
      <path d="M15 39C15 25.7 21.8 15 32 15s17 10.7 17 24v8.5A6.5 6.5 0 0 1 42.5 54h-21a6.5 6.5 0 0 1-6.5-6.5V39Z" fill="#24213F" />
      <path d="M21.5 31.5C21.5 24.6 26.2 20 32 20s10.5 4.6 10.5 11.5c0 3.2-1.2 5.9-3.2 7.7 2.9 2.4 4.7 5.9 4.7 9.8v.3c0 2.6-2.1 4.7-4.7 4.7H24.7a4.7 4.7 0 0 1-4.7-4.7V49c0-3.9 1.8-7.4 4.7-9.8a10.5 10.5 0 0 1-3.2-7.7Z" fill="#F8F7FF" />
      <circle cx="27.5" cy="30.5" r="2" fill="#24213F" />
      <circle cx="36.5" cy="30.5" r="2" fill="#24213F" />
      <path d="m32 33.2 4.2 3.2-4.2 2.4-4.2-2.4 4.2-3.2Z" fill="#C9C2FF" />
      <path d="M19.5 39.5c-3.2 1.1-5.4 3.4-6.5 6.9 3.2.3 5.8-.5 7.8-2.5" fill="#24213F" />
      <path d="M44.5 39.5c3.2 1.1 5.4 3.4 6.5 6.9-3.2.3-5.8-.5-7.8-2.5" fill="#24213F" />
      <path d="M49.5 11.7 51 15l3.3 1.5L51 18l-1.5 3.3L48 18l-3.3-1.5L48 15l1.5-3.3Z" fill="#F8F7FF" />
    </svg>
  );
}
