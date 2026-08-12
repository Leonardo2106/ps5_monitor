import { useEffect, useRef } from 'react'
import Chart from 'chart.js/auto'
import type { TooltipItem } from 'chart.js'
import type { Price } from '../types/api'
import { formatBRL, formatDateTime } from '../utils'

interface PriceChartProps {
  prices: Price[]
}

export function PriceChart({ prices }: PriceChartProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (!canvasRef.current) return

    const chart = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels: prices.map((item) => formatDateTime(item.date, true)),
        datasets: [
          {
            label: 'Preço',
            data: prices.map((item) => item.price),
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.12)',
            pointRadius: prices.length > 50 ? 0 : 3,
            tension: 0.28,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context: TooltipItem<'line'>) => formatBRL(Number(context.raw)),
            },
          },
        },
        scales: {
          x: {
            ticks: { maxTicksLimit: 8, color: '#94a3b8' },
            grid: { display: false },
          },
          y: {
            ticks: {
              color: '#94a3b8',
              callback: (value: string | number) => formatBRL(Number(value)),
            },
            grid: { color: 'rgba(148, 163, 184, 0.12)' },
          },
        },
      },
    })

    return () => chart.destroy()
  }, [prices])

  if (prices.length === 0) {
    return <div className="empty-state">Nenhum preço registrado nos últimos 30 dias.</div>
  }

  return <canvas ref={canvasRef} />
}
