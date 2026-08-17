interface PenguinMarkProps {
  size?: number;
  className?: string;
  decorative?: boolean;
}

export function PenguinMark({
  size = 40,
  className = "",
  decorative = true,
}: PenguinMarkProps) {
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
