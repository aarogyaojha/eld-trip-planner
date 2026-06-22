import { useEffect, useState } from 'react'

const DURATION_MS = 700

export default function useCountUp(targetValue) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    if (targetValue == null || Number.isNaN(targetValue)) {
      setValue(0)
      return
    }
    let frame
    const start = performance.now()
    const from = 0

    function tick(now) {
      const progress = Math.min((now - start) / DURATION_MS, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(from + (targetValue - from) * eased)
      if (progress < 1) {
        frame = requestAnimationFrame(tick)
      } else {
        setValue(targetValue)
      }
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [targetValue])

  return value
}
