export interface DetailRow {
  label: string
  value: string | null | undefined
}

export function DetailSection({ className = '', rows, title }: { className?: string; rows: DetailRow[]; title: string }) {
  const visibleRows = rows.filter((row) => hasValue(row.value))

  if (visibleRows.length === 0) {
    return null
  }

  return (
    <section className={`detail-section ${className}`.trim()} aria-label={title}>
      <h3>{title}</h3>
      <dl className="detail-list">
        {visibleRows.map((row) => (
          <div className="detail-row" key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function hasValue(value: string | null | undefined) {
  return value !== null && value !== undefined && value.trim().length > 0
}
