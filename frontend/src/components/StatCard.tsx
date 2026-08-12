interface StatCardProps {
  label: string
  value: string
  helper?: string
}

export function StatCard({ label, value, helper }: StatCardProps) {
  return (
    <article className="stat-card">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {helper && <small>{helper}</small>}
    </article>
  )
}
