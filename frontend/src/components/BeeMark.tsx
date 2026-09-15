interface BeeMarkProps {
  size?: number;
  className?: string;
  decorative?: boolean;
  variant?: "default" | "scholar" | "learning" | "hero";
}

const mascotAssetByVariant = {
  default: "/mascot/bee-mark.png",
  scholar: "/mascot/bee-learning.png",
  learning: "/mascot/bee-learning.png",
  hero: "/mascot/bee-hero.png",
} as const;

export function BeeMark({
  size = 40,
  className = "",
  decorative = true,
  variant = "default",
}: BeeMarkProps) {
  const isLearning = variant !== "default";
  const isHero = variant === "hero";

  return (
    <img
      className={`bee-mark bee-mark-side${isLearning ? " bee-mark-learning" : ""}${isHero ? " bee-mark-hero" : ""}${className ? ` ${className}` : ""}`}
      src={mascotAssetByVariant[variant]}
      width={size}
      height={size}
      alt={decorative ? "" : "Mascot bee learning from a book"}
      aria-hidden={decorative ? "true" : undefined}
    />
  );
}
