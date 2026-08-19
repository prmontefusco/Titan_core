import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

interface DetailPageHeaderProps {
  eyebrow: string
  title: string
  subtitle?: string
  backTo?: string
  backLabel?: string
  meta?: ReactNode
  actions?: ReactNode
}

interface DetailSectionProps {
  title: string
  description?: string
  children: ReactNode
}

interface DetailDescriptionListProps {
  children: ReactNode
}

export function DetailPageHeader({
  eyebrow,
  title,
  subtitle,
  backTo,
  backLabel,
  meta,
  actions,
}: DetailPageHeaderProps) {
  return (
    <header className="detail-page-header">
      {backTo && backLabel && (
        <Link to={backTo} className="detail-back-link">
          &larr; {backLabel}
        </Link>
      )}

      <div className="detail-header-main">
        <div>
          <p className="detail-eyebrow">{eyebrow}</p>
          <h1 className="detail-title">{title}</h1>
          {subtitle && <p className="detail-subtitle">{subtitle}</p>}
        </div>
        {meta && <div className="detail-header-meta">{meta}</div>}
      </div>

      {actions && <div className="detail-header-actions">{actions}</div>}
    </header>
  )
}

export function DetailSection({ title, description, children }: DetailSectionProps) {
  return (
    <section className="detail-section" aria-labelledby={titleToId(title)}>
      <div className="detail-section-header">
        <h2 id={titleToId(title)}>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      <div className="detail-section-body">{children}</div>
    </section>
  )
}

export function DetailDescriptionList({ children }: DetailDescriptionListProps) {
  return <dl className="detail-description-list">{children}</dl>
}

function titleToId(title: string) {
  return `section-${title.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-')}`
}
