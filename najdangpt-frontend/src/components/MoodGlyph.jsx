const moodColors = {
  1: '#FD6E6E',
  2: '#C78B9A',
  3: '#C9C2E3',
  4: '#8B7CC7',
  5: '#FD6E6E',
}

/** Five weather-inspired mood symbols matching the native iOS Wellness scale. */
export default function MoodGlyph({ score, size = 28, color, className = '' }) {
  const tint = color || moodColors[score] || moodColors[3]
  const common = {
    fill: 'none',
    stroke: tint,
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }
  const cloud = 'M6.5 18.1h10.8a4.2 4.2 0 0 0 .2-8.4 5.3 5.3 0 0 0-10.2-1.4 4.9 4.9 0 0 0-.8 9.8Z'

  return (
    <svg
      className={`mood-glyph ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label={['', 'Awful', 'Bad', 'Okay', 'Good', 'Great'][score] || 'Mood'}
      focusable="false"
    >
      {score === 3 && <>
        <circle cx="17.3" cy="6.6" r="3.2" {...common} />
        <path d="M17.3 1.6v1.3M17.3 10.3v1.1M12.4 6.6h1.2M21 6.6h1.2" {...common} />
      </>}
      {score === 4 && <>
        <circle cx="12" cy="8.2" r="3.6" {...common} />
        <path d="M12 1.8v1.2M12 13.4v1.1M2.2 8.2h2.1M19.7 8.2h2.1M5.2 16.2h13.6M7 19h10" {...common} />
      </>}
      {score === 5 && <>
        <circle cx="12" cy="12" r="4" {...common} />
        <path d="M12 1.7v2.1M12 20.2v2.1M1.7 12h2.1M20.2 12h2.1M4.7 4.7l1.5 1.5M17.8 17.8l1.5 1.5M19.3 4.7l-1.5 1.5M6.2 17.8l-1.5 1.5" {...common} />
      </>}
      {(score === 1 || score === 2 || score === 3) && (
        <path d={cloud} stroke={tint} fill={tint} fillOpacity="0.12" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {score === 1 && <path d="m8.1 20-1 2M13 20l-1 2M17.9 20l-1 2" {...common} />}
    </svg>
  )
}

export { moodColors }
