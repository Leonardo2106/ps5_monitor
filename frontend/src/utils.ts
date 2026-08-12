export const formatBRL = (value: number | null | undefined) =>
  value == null
    ? '—'
    : new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
      }).format(value)

export const formatDateTime = (value: string | null | undefined, short = false) => {
  if (!value) return '—'
  const date = new Date(value)
  const options: Intl.DateTimeFormatOptions = {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }
  if (!short) options.year = 'numeric'
  return new Intl.DateTimeFormat('pt-BR', options).format(date)
}

export const installmentLabel = (count: number | null, value: number | null) => {
  if (!count || value == null) return 'Não identificado'
  return `${count}x de ${formatBRL(value)} (total ${formatBRL(count * value)})`
}
