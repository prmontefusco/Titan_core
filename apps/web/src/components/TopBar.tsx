import titanLogo from '../assets/titan-bode.png'
import { UserAccountMenu, type UserAccountMenuProps } from './UserAccountMenu'

export interface TopBarProps {
  organizationId: string
  userMenuProps: UserAccountMenuProps
  onToggleSidebar?: () => void
  isSidebarOpen?: boolean
}

export function TopBar({
  organizationId,
  userMenuProps,
  onToggleSidebar,
  isSidebarOpen,
}: TopBarProps) {
  return (
    <header className="app-topbar" role="banner">
      <div className="topbar-left">
        {onToggleSidebar && (
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={onToggleSidebar}
            aria-label={isSidebarOpen ? 'Fechar menu de navegação' : 'Abrir menu de navegação'}
            aria-expanded={isSidebarOpen}
          >
            <span className="hamburger-icon" aria-hidden="true">
              {isSidebarOpen ? '✕' : '☰'}
            </span>
          </button>
        )}

        <div className="topbar-brand">
          <img
            src={titanLogo}
            alt="Titan"
            width={36}
            height={36}
            className="topbar-brand-logo"
          />
          <div className="topbar-brand-text">
            <span className="brand-title">Titan</span>
            <span className="brand-module">Livestock</span>
          </div>
        </div>
      </div>

      <div className="topbar-center">
        <div className="org-context-pill" title={`Organização ativa: ${organizationId}`}>
          <span className="org-context-label">Org:</span>
          <code className="org-context-id">{organizationId}</code>
        </div>
      </div>

      <div className="topbar-right">
        <UserAccountMenu {...userMenuProps} />
      </div>
    </header>
  )
}
