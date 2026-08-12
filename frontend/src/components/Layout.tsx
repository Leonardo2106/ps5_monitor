import type { MouseEvent, ReactNode } from 'react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '◫' },
  { to: '/products', label: 'Produtos', icon: '▣' },
  { to: '/stores', label: 'Lojas', icon: '⌂' },
  { to: '/promotions', label: 'Promoções', icon: '%' },
  { to: '/settings', label: 'Configurações', icon: '⚙' },
]

interface LayoutProps {
  children: ReactNode
  currentPath: string
  onNavigate: (to: string) => void
}

function isPlainLeftClick(event: MouseEvent<HTMLAnchorElement>) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
}

export function Layout({ children, currentPath, onNavigate }: LayoutProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">PS</span>
          <div><strong>Price Monitor</strong><small>Ofertas e cupons</small></div>
        </div>
        <nav>
          {navItems.map((item) => (
            <a
              key={item.to}
              href={item.to}
              className={currentPath === item.to ? 'nav-link active' : 'nav-link'}
              onClick={(event) => {
                if (!isPlainLeftClick(event)) return
                event.preventDefault()
                onNavigate(item.to)
              }}
            >
              <span>{item.icon}</span>{item.label}
            </a>
          ))}
        </nav>
        <div className="sidebar-footer"><span className="status-dot" /> Monitor automático</div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  )
}
