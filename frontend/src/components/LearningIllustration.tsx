interface LearningIllustrationProps {
  variant?: "library" | "practice";
  className?: string;
}

export function LearningIllustration({
  variant = "library",
  className = "",
}: LearningIllustrationProps) {
  if (variant === "practice") {
    return (
      <svg className={`learning-illustration ${className}`.trim()} viewBox="0 0 320 220" role="img" aria-label="Minh họa mục tiêu và danh sách luyện tập">
        <defs>
          <linearGradient id="practiceTarget" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#7C5CFC" />
            <stop offset="1" stopColor="#5146D8" />
          </linearGradient>
        </defs>
        <circle cx="124" cy="112" r="70" fill="#EEEAFE" />
        <circle cx="124" cy="112" r="54" fill="url(#practiceTarget)" />
        <circle cx="124" cy="112" r="35" fill="#F7F5FF" />
        <circle cx="124" cy="112" r="15" fill="#6658E8" />
        <path d="M54 72 128 112" stroke="#EC4899" strokeWidth="10" strokeLinecap="round" />
        <path d="m48 62 7 20 17-13" fill="#EC4899" />
        <g transform="translate(178 35) rotate(7 55 78)">
          <rect width="112" height="150" rx="18" fill="#fff" stroke="#DED9F4" />
          <path d="m22 37 7 7 13-15" fill="none" stroke="#10B981" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M54 38h34M54 73h34M54 108h34" stroke="#D8D4EA" strokeWidth="7" strokeLinecap="round" />
          <path d="m22 72 7 7 13-15M22 107l7 7 13-15" fill="none" stroke="#7C5CFC" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <path d="m286 28 5 13 13 5-13 5-5 13-5-13-13-5 13-5zM69 24l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="#F59E0B" />
      </svg>
    );
  }

  return (
    <svg className={`learning-illustration ${className}`.trim()} viewBox="0 0 360 250" role="img" aria-label="Minh họa sách học từ vựng">
      <defs>
        <linearGradient id="bookCover" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#8B6BFF" />
          <stop offset="1" stopColor="#5146D8" />
        </linearGradient>
      </defs>
      <ellipse cx="184" cy="201" rx="122" ry="25" fill="#E8E4FC" />
      <g transform="translate(86 34) rotate(-7 90 82)">
        <rect x="10" y="22" width="180" height="166" rx="28" fill="#493FC1" opacity=".2" />
        <rect width="180" height="166" rx="28" fill="url(#bookCover)" />
        <path d="M151 6v151c0 10-8 18-18 18H24" fill="none" stroke="#A998FF" strokeWidth="7" opacity=".7" />
        <text x="86" y="101" fill="#EDE9FF" fontFamily="Plus Jakarta Sans, sans-serif" fontSize="62" fontWeight="800" textAnchor="middle">Aa</text>
        <path d="M24 166h132c11 0 20 9 20 20H45c-12 0-21-9-21-20Z" fill="#fff" />
        <path d="M48 175h107" stroke="#D7D0FA" strokeWidth="4" strokeLinecap="round" />
      </g>
      <g transform="translate(248 124) rotate(10 37 35)">
        <rect width="74" height="70" rx="16" fill="#EC4899" />
        <path d="M20 24h34M20 36h28M20 48h21" stroke="#FFE5F0" strokeWidth="5" strokeLinecap="round" />
      </g>
      <path d="m108 185 11 22 24 3-18 17 5 24-22-12-22 12 5-24-18-17 24-3z" fill="#F9B933" />
      <path d="m303 32 6 15 15 6-15 6-6 15-6-15-15-6 15-6zM54 70l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" fill="#B7A8FF" />
    </svg>
  );
}
