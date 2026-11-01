import { useEffect, useRef } from 'react'

const PALETTE = ['#C9C2E3', '#8B7CC7', '#5A3B8C', '#B7A9E4']

/**
 * Procedural Sanctumly neural orb, visually aligned with the native iOS and
 * Android Canvas implementations. It intentionally uses vector drawing
 * rather than a sprite sheet so it stays crisp and can react to microphone
 * input at any display density.
 */
export default function NeuralOrb({ state = 'idle', audioLevelRef = null }) {
  const canvasRef = useRef(null)
  const stateRef = useRef(state)
  const fallbackLevelRef = useRef(0)
  const levelRef = audioLevelRef || fallbackLevelRef

  useEffect(() => { stateRef.current = state }, [state])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const context = canvas.getContext('2d', { alpha: true })
    if (!context) return undefined

    let width = 0
    let height = 0
    let pixelRatio = 1
    let frame = 0
    let disposed = false
    let reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      width = Math.max(1, rect.width)
      height = Math.max(1, rect.height)
      pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.round(width * pixelRatio)
      canvas.height = Math.round(height * pixelRatio)
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      draw(0)
    }

    const draw = (clockSeconds) => {
      if (!context || !width || !height) return
      const ctx = context
      const currentState = stateRef.current
      const mic = currentState === 'listening' ? levelRef.current : 0
      const speed = currentState === 'listening' ? 1.08
        : currentState === 'speaking' ? 0.86
          : currentState === 'thinking' ? 0.62 : 0.48
      const time = clockSeconds * speed
      const pulse = currentState === 'listening'
        ? 1 + mic * 0.075 + Math.sin(time * 1.4) * 0.008
        : currentState === 'speaking'
          ? 1 + Math.sin(time * 1.9) * 0.035
          : 1 + Math.sin(time * (currentState === 'thinking' ? 1.25 : 0.8)) * (currentState === 'thinking' ? 0.018 : 0.012)

      ctx.clearRect(0, 0, width, height)
      ctx.save()
      ctx.translate(width / 2, height / 2)
      ctx.scale(pulse, pulse)
      const size = Math.min(width, height)
      const radius = size * 0.47

      // Soft halo and restrained dimensional sphere, matching native clients.
      const aura = ctx.createRadialGradient(-radius * 0.23, -radius * 0.27, 2, 0, 0, radius * 1.25)
      aura.addColorStop(0, 'rgba(139,124,199,0.40)')
      aura.addColorStop(0.48, 'rgba(90,59,140,0.22)')
      aura.addColorStop(1, 'rgba(90,59,140,0)')
      ctx.fillStyle = aura
      ctx.beginPath(); ctx.arc(0, 0, radius * 1.24, 0, Math.PI * 2); ctx.fill()

      ctx.save()
      ctx.beginPath(); ctx.arc(0, 0, radius * 0.96, 0, Math.PI * 2); ctx.clip()
      const sphere = ctx.createRadialGradient(-radius * 0.2, -radius * 0.29, radius * 0.04, 0, 0, radius * 1.08)
      sphere.addColorStop(0, 'rgba(58,43,91,0.97)')
      sphere.addColorStop(0.62, 'rgba(34,25,57,0.96)')
      sphere.addColorStop(1, 'rgba(19,14,34,0.99)')
      ctx.fillStyle = sphere
      ctx.beginPath(); ctx.arc(0, 0, radius * 0.96, 0, Math.PI * 2); ctx.fill()

      const glow = ctx.createRadialGradient(-radius * 0.2 + Math.sin(time * 0.2) * 5, -radius * 0.22 + Math.cos(time * 0.18) * 5, 1, 0, 0, radius * 0.95)
      glow.addColorStop(0, `rgba(201,194,227,${0.12 + mic * 0.1})`)
      glow.addColorStop(0.46, 'rgba(139,124,199,0.12)')
      glow.addColorStop(1, 'rgba(90,59,140,0)')
      ctx.fillStyle = glow
      ctx.beginPath(); ctx.arc(0, 0, radius * 0.96, 0, Math.PI * 2); ctx.fill()

      // Three fine orbital traces.
      for (let ring = 0; ring < 3; ring += 1) {
        const inset = size * (0.075 + ring * 0.045)
        ctx.save()
        ctx.rotate(time * (ring % 2 === 0 ? 0.025 : -0.018) + ring * 0.8)
        ctx.setLineDash([size * 0.010, size * 0.024])
        ctx.lineWidth = Math.max(0.55, size * 0.0024)
        ctx.strokeStyle = `rgba(201,194,227,${0.15 - ring * 0.035})`
        ctx.beginPath()
        ctx.ellipse(0, 0, radius - inset * 0.35, radius * 0.91 - inset * 0.35, 0, 0, Math.PI * 2)
        ctx.stroke()
        ctx.restore()
      }

      // Interlaced neural pathways and their travelling connection nodes.
      const radiusX = size * 0.405
      const radiusY = size * 0.395
      for (let strand = 0; strand < 13; strand += 1) {
        const strandPhase = strand * 0.47
        ctx.beginPath()
        for (let step = 0; step <= 150; step += 1) {
          const fraction = step / 150
          const angle = fraction * Math.PI * 2
          const phase = time + strandPhase
          const radial = 0.72
            + 0.15 * Math.sin(angle * 2.8 + phase * 0.9)
            + 0.075 * Math.cos(angle * 4.2 - phase * 0.55)
            + mic * 0.045 * Math.sin(angle * 5 + phase)
          const nx = Math.cos(angle + strandPhase * 0.31 + phase * 0.15) * radial
            + 0.12 * Math.sin(angle * 2 + phase + strandPhase)
          const ny = Math.sin(angle * (1.05 + (strand % 4) * 0.12) + phase * 0.38 + strandPhase) * 0.72
            + 0.13 * Math.cos(angle * 2.5 - phase * 0.7 + strandPhase)
          const x = nx * radiusX
          const y = ny * radiusY
          if (step === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)

          if (step > 0 && step < 150 && step % 25 === 0) {
            const nodeRadius = ((step + strand) % 3 === 0 ? 2.2 : 1.35) * (size / 290)
            const color = PALETTE[(strand + step / 25) % PALETTE.length]
            ctx.save()
            ctx.shadowColor = color
            ctx.shadowBlur = size * 0.018
            ctx.fillStyle = color
            ctx.globalAlpha = 0.78
            ctx.beginPath(); ctx.arc(x, y, nodeRadius, 0, Math.PI * 2); ctx.fill()
            ctx.restore()
          }
        }
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        ctx.lineWidth = (strand % 4 === 0 ? 1.45 : 0.75) * (size / 290)
        ctx.strokeStyle = PALETTE[strand % PALETTE.length]
        ctx.globalAlpha = strand % 3 === 0 ? 0.9 : 0.48
        ctx.stroke()
        ctx.globalAlpha = 1
      }
      ctx.restore() // sphere clip

      // Rotating outer trace and luminous central nucleus.
      ctx.save()
      ctx.rotate(time * 0.12)
      const ringGradient = typeof ctx.createConicGradient === 'function'
        ? ctx.createConicGradient(time * 0.25, 0, 0)
        : ctx.createLinearGradient(-radius, -radius, radius, radius)
      ringGradient.addColorStop(0, 'rgba(201,194,227,0.88)')
      ringGradient.addColorStop(0.34, 'rgba(139,124,199,0.42)')
      ringGradient.addColorStop(0.68, 'rgba(183,169,228,0.78)')
      ringGradient.addColorStop(1, 'rgba(201,194,227,0.88)')
      ctx.strokeStyle = ringGradient
      ctx.lineWidth = Math.max(0.8, size * 0.004)
      ctx.beginPath(); ctx.arc(0, 0, radius * 0.975, 0, Math.PI * 2); ctx.stroke()
      ctx.restore()

      const nucleus = ctx.createRadialGradient(0, 0, 1, 0, 0, size * 0.23)
      nucleus.addColorStop(0, `rgba(255,255,255,${0.66 + mic * 0.14})`)
      nucleus.addColorStop(0.28, 'rgba(201,194,227,0.48)')
      nucleus.addColorStop(0.62, 'rgba(139,124,199,0.12)')
      nucleus.addColorStop(1, 'rgba(139,124,199,0)')
      ctx.fillStyle = nucleus
      ctx.beginPath(); ctx.arc(0, 0, size * 0.23, 0, Math.PI * 2); ctx.fill()

      ctx.strokeStyle = 'rgba(201,194,227,0.46)'
      ctx.lineWidth = Math.max(0.65, size * 0.0025)
      ctx.beginPath(); ctx.arc(0, 0, size * 0.159, 0, Math.PI * 2); ctx.stroke()
      ctx.restore()
    }

    const start = performance.now()
    const tick = (now) => {
      if (disposed) return
      const seconds = reducedMotion ? 0.8 : (now - start) / 1000
      draw(seconds)
      if (!reducedMotion) frame = window.requestAnimationFrame(tick)
    }

    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    observer?.observe(canvas)
    resize()
    if (!reducedMotion) frame = window.requestAnimationFrame(tick)

    const motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const onMotionChange = (event) => {
      reducedMotion = event.matches
      if (frame) window.cancelAnimationFrame(frame)
      if (!reducedMotion) frame = window.requestAnimationFrame(tick)
      else draw(0.8)
    }
    motionQuery?.addEventListener?.('change', onMotionChange)

    return () => {
      disposed = true
      if (frame) window.cancelAnimationFrame(frame)
      observer?.disconnect()
      motionQuery?.removeEventListener?.('change', onMotionChange)
    }
  }, [])

  return <canvas ref={canvasRef} className="neural-orb-canvas" aria-hidden="true" />
}
