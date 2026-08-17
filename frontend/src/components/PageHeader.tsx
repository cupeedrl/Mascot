import type { ComponentType, ReactNode } from "react";

interface PageHeaderProps {
  eyebrow: string;
  title: ReactNode;
  description: string;
  icon?: ComponentType<{ size?: number; strokeWidth?: number }>;
  aside?: ReactNode;
  className?: string;
  titleId?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  icon: Icon,
  aside,
  className = "",
  titleId,
}: PageHeaderProps) {
  return (
    <header className={`page-header ${className}`.trim()}>
      <div className="page-header-copy">
        <div className="page-header-eyebrow">
          {Icon && <span className="page-header-icon"><Icon size={19} strokeWidth={2} /></span>}
          <span>{eyebrow}</span>
        </div>
        <h1 id={titleId}>{title}</h1>
        <p>{description}</p>
      </div>
      {aside && <div className="page-header-aside">{aside}</div>}
    </header>
  );
}
