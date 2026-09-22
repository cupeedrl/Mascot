interface LearningIllustrationProps {
  variant?: "library" | "practice" | "vocabulary" | "review";
  className?: string;
}

export function LearningIllustration({
  variant = "library",
  className = "",
}: LearningIllustrationProps) {
  if (variant === "vocabulary") {
    return (
      <svg className={`learning-illustration ${className}`.trim()} viewBox="0 0 320 220" role="img" aria-label="Minh họa bộ thẻ từ vựng cá nhân">
        <defs>
          <linearGradient id="vocabularyCard" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#8177F0" />
            <stop offset="1" stopColor="#5044C8" />
          </linearGradient>
        </defs>
        <ellipse cx="162" cy="188" rx="112" ry="20" fill="#EBE8FF" />
        <g transform="translate(44 60) rotate(-11 86 58)">
          <rect width="172" height="116" rx="20" fill="#fff" stroke="#E6E2F0" />
          <path d="M28 40h60M28 60h94M28 80h46" stroke="#D7D2E6" strokeWidth="7" strokeLinecap="round" />
        </g>
        <g transform="translate(74 44) rotate(6 86 58)">
          <rect width="172" height="116" rx="20" fill="url(#vocabularyCard)" />
          <text x="34" y="74" fill="#EDE9FF" fontFamily="Plus Jakarta Sans, sans-serif" fontSize="44" fontWeight="800">Aa</text>
          <path d="M104 44h44M104 62h34" stroke="#C9C2FF" strokeWidth="7" strokeLinecap="round" />
          <path d="M132 0h26v44l-13-10-13 10Z" fill="#D9542B" />
        </g>
        <path d="m40 44 5 13 13 5-13 5-5 13-5-13-13-5 13-5z" fill="#F7C948" />
        <path d="m276 96 4 11 11 4-11 4-4 11-4-11-11-4 11-4z" fill="#A89DF7" />
        <g transform="translate(212 150) rotate(-12)">
          <rect x="-8" width="8" height="11" rx="3" fill="#F09A8C" />
          <rect x="-2" width="4" height="11" fill="#E6E2F0" />
          <rect x="2" width="46" height="11" rx="2" fill="#E2673C" />
          <rect x="38" width="4" height="11" fill="#F7C948" />
          <path d="M48 0 62 5.5 48 11Z" fill="#FFE3AE" />
          <path d="M57 3 62 5.5 57 8Z" fill="#2F2674" />
        </g>
      </svg>
    );
  }

  if (variant === "review") {
    return (
      <svg className={`learning-illustration ${className}`.trim()} viewBox="0 0 320 220" role="img" aria-label="Minh họa vòng ôn tập ngắt quãng">
        <defs>
          <linearGradient id="reviewLoop" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#8177F0" />
            <stop offset="1" stopColor="#5044C8" />
          </linearGradient>
        </defs>
        <circle cx="148" cy="110" r="78" fill="#EEECFF" />
        <path d="M148 46a64 64 0 1 1-52 27" fill="none" stroke="url(#reviewLoop)" strokeWidth="15" strokeLinecap="round" />
        <path d="M148 32 168 48 146 62Z" fill="#6658E8" />
        <g transform="translate(96 72) rotate(-6 52 38)">
          <rect width="104" height="76" rx="16" fill="#fff" stroke="#E6E2F0" />
          <path d="M22 28h60M22 44h40" stroke="#D7D2E6" strokeWidth="7" strokeLinecap="round" />
          <path d="m22 58 7 7 13-15" fill="none" stroke="#228764" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <g transform="translate(228 120)">
          <circle cx="26" cy="26" r="26" fill="#fff" stroke="#E6E2F0" />
          <circle cx="26" cy="26" r="20" fill="#FFF6D9" />
          <path d="M26 14v13l9 5" stroke="#A86808" strokeWidth="4.5" strokeLinecap="round" fill="none" />
        </g>
        <path d="m58 150 5 13 13 5-13 5-5 13-5-13-13-5 13-5z" fill="#F7C948" />
        <path d="m252 48 4 11 11 4-11 4-4 11-4-11-11-4 11-4z" fill="#A89DF7" />
      </svg>
    );
  }

  if (variant === "practice") {
    return (
      <svg className={`learning-illustration ${className}`.trim()} viewBox="0 0 320 220" role="img" aria-label="Minh họa mục tiêu và danh sách luyện tập">
        <defs>
          <linearGradient id="practiceTarget" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#7A6DF0" />
            <stop offset="1" stopColor="#5044C8" />
          </linearGradient>
        </defs>
        <circle cx="124" cy="112" r="70" fill="#EEECFF" />
        <circle cx="124" cy="112" r="54" fill="url(#practiceTarget)" />
        <circle cx="124" cy="112" r="35" fill="#F7F5FF" />
        <circle cx="124" cy="112" r="15" fill="#F7C948" />
        <path d="M54 72 128 112" stroke="#2F2674" strokeWidth="10" strokeLinecap="round" />
        <path d="m48 62 7 20 17-13" fill="#2F2674" />
        <g transform="translate(178 35) rotate(7 55 78)">
          <rect width="112" height="150" rx="18" fill="#fff" stroke="#E6E2F0" />
          <path d="m22 37 7 7 13-15" fill="none" stroke="#228764" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M54 38h34M54 73h34M54 108h34" stroke="#D7D2E6" strokeWidth="7" strokeLinecap="round" />
          <path d="m22 72 7 7 13-15M22 107l7 7 13-15" fill="none" stroke="#6658E8" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        </g>
        <path d="m286 28 5 13 13 5-13 5-5 13-5-13-13-5 13-5zM69 24l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="#F7C948" />
        {/* Pencil: a small warm accent so the scene reads as "doing", not just "reading". */}
        <g transform="translate(150 186) rotate(-14)">
          <rect x="-9" width="9" height="13" rx="3.5" fill="#F09A8C" />
          <rect x="-2" width="5" height="13" fill="#E6E2F0" />
          <rect x="2" width="60" height="13" rx="2" fill="#E2673C" />
          <rect x="50" width="5" height="13" fill="#F7C948" />
          <path d="M62 0 78 6.5 62 13Z" fill="#FFE3AE" />
          <path d="M72.5 3.7 78 6.5 72.5 9.3Z" fill="#2F2674" />
        </g>
      </svg>
    );
  }

  return (
    <svg className={`learning-illustration ${className}`.trim()} viewBox="0 0 360 250" role="img" aria-label="Minh họa sách học từ vựng">
      <defs>
        <linearGradient id="bookCover" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#8177F0" />
          <stop offset="1" stopColor="#5044C8" />
        </linearGradient>
      </defs>
      <ellipse cx="184" cy="201" rx="122" ry="25" fill="#EBE8FF" />
      <g transform="translate(86 34) rotate(-7 90 82)">
        <rect x="10" y="22" width="180" height="166" rx="28" fill="#5044C8" opacity=".2" />
        <rect width="180" height="166" rx="28" fill="url(#bookCover)" />
        <path d="M151 6v151c0 10-8 18-18 18H24" fill="none" stroke="#A89DF7" strokeWidth="7" opacity=".7" />
        <text x="86" y="101" fill="#EDE9FF" fontFamily="Plus Jakarta Sans, sans-serif" fontSize="62" fontWeight="800" textAnchor="middle">Aa</text>
        <path d="M24 166h132c11 0 20 9 20 20H45c-12 0-21-9-21-20Z" fill="#fff" />
        <path d="M48 175h107" stroke="#D7D0FA" strokeWidth="4" strokeLinecap="round" />
      </g>
      <g transform="translate(248 124) rotate(10 37 35)">
        <rect width="74" height="70" rx="16" fill="#2F7FD1" />
        <path d="M20 24h34M20 36h28M20 48h21" stroke="#E9F3FD" strokeWidth="5" strokeLinecap="round" />
      </g>
      <path d="m108 185 11 22 24 3-18 17 5 24-22-12-22 12 5-24-18-17 24-3z" fill="#F7C948" />
      <path d="m303 32 6 15 15 6-15 6-6 15-6-15-15-6 15-6zM54 70l4 10 10 4-10 4-4 10-4-10-10-4 10-4z" fill="#A89DF7" />
      {/* Pencil: a small warm accent so the scene reads as "doing", not just "reading". */}
      <g transform="translate(232 204) rotate(-10)">
        <rect x="-9" width="9" height="13" rx="3.5" fill="#F09A8C" />
        <rect x="-2" width="5" height="13" fill="#E6E2F0" />
        <rect x="2" width="58" height="13" rx="2" fill="#E2673C" />
        <rect x="48" width="5" height="13" fill="#F7C948" />
        <path d="M60 0 76 6.5 60 13Z" fill="#FFE3AE" />
        <path d="M70.5 3.7 76 6.5 70.5 9.3Z" fill="#2F2674" />
      </g>
    </svg>
  );
}
