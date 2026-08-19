export default function StarDisplay({ stars, color = "text-amber-500" }) {
  const s = Math.round(stars || 0)
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} className={i <= s ? color : "text-gray-200"}>★</span>
      ))}
    </div>
  )
}
