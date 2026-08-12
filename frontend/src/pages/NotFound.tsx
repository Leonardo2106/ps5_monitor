import type { MouseEvent } from 'react'

interface NotFoundProps {
  onNavigate: (to: string) => void
}

export function NotFound({ onNavigate }: NotFoundProps) {
  function goHome(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    onNavigate('/')
  }

  return <div className="page-state"><h1>Página não encontrada</h1><a href="/" onClick={goHome}>Voltar ao dashboard</a></div>
}
