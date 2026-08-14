export default function StatBar({ creators }) {
  if (!creators.length) return null

  const total = creators.length
  const withBroker = creators.filter(c => c.broker && c.broker !== '-').length
  const withContact = creators.filter(c => (c.email && c.email !== '-') || (c.phone && c.phone !== '-')).length
  const engRates = creators.map(c => parseFloat(c.engagement_rate)).filter(v => !isNaN(v))
  const avgEng = engRates.length ? (engRates.reduce((a, b) => a + b, 0) / engRates.length).toFixed(1) : '-'
  const ytCount = creators.filter(c => c.platform?.toLowerCase() === 'youtube').length
  const igCount = creators.filter(c => c.platform?.toLowerCase() === 'instagram').length

  return (
    <div className="stat-bar">
      <StatItem label="Creators" value={total} />
      <StatItem label="YouTube" value={ytCount} />
      <StatItem label="Instagram" value={igCount} />
      <StatItem label="With Broker" value={withBroker} sub={`${Math.round(withBroker / total * 100)}%`} />
      <StatItem label="With Contact" value={withContact} sub={`${Math.round(withContact / total * 100)}%`} />
      <StatItem label="Avg Engagement" value={avgEng === '-' ? '-' : `${avgEng}%`} />
    </div>
  )
}

function StatItem({ label, value, sub }) {
  return (
    <div className="stat-bar__item">
      <span className="stat-bar__label">{label}</span>
      <span className="stat-bar__value">{value}</span>
      {sub && <span className="stat-bar__sub">({sub})</span>}
    </div>
  )
}
