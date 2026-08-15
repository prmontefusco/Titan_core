interface ContextItem {
  label: string
  value: string
}

interface PageContextProps {
  title?: string
  description?: string
  items: ContextItem[]
}

export function PageContext({
  title = 'Contexto operacional',
  description,
  items,
}: PageContextProps) {
  return (
    <section className="page-context" aria-label={title}>
      <div className="page-context-header">
        <h2 className="page-context-title">{title}</h2>
        {description && <p className="page-context-description">{description}</p>}
      </div>

      <dl className="page-context-list">
        {items.map((item) => (
          <div key={`${item.label}:${item.value}`} className="page-context-row">
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
