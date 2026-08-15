import { NavLink } from 'react-router-dom'

export interface NavigationItem {
  path: string
  label: string
  icon?: string
  badge?: string | number
}

export interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  items: NavigationItem[]
}

export function Sidebar({ isOpen, onClose, items }: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="sidebar-backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`app-sidebar ${isOpen ? 'is-open' : ''}`}
        aria-label="Navegação Principal"
      >
        <nav className="sidebar-nav">
          <ul className="sidebar-menu-list">
            {items.map((item) => (
              <li key={item.path} className="sidebar-menu-item">
                <NavLink
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) =>
                    `sidebar-nav-link ${isActive ? 'is-active' : ''}`
                  }
                  onClick={() => {
                    if (window.innerWidth < 768) {
                      onClose()
                    }
                  }}
                >
                  {item.icon && (
                    <span className="sidebar-nav-icon" aria-hidden="true">
                      {item.icon}
                    </span>
                  )}
                  <span className="sidebar-nav-label">{item.label}</span>
                  {item.badge !== undefined && (
                    <span className="sidebar-nav-badge">{item.badge}</span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    </>
  )
}
