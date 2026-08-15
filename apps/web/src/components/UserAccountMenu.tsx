import { useEffect, useRef, useState } from 'react'

export interface UserAccountMenuProps {
  displayName: string
  email?: string
  subject: string
  organizationId: string
  roleLabel: string
  onSignOut: () => void
}

export function UserAccountMenu({
  displayName,
  email,
  subject,
  organizationId,
  roleLabel,
  onSignOut,
}: UserAccountMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const toggleMenu = () => setIsOpen((prev) => !prev)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false)
        buttonRef.current?.focus()
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleKeyDown)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  // Iniciais do nome ou do subject
  const initials = (displayName || subject || 'U')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="user-account-container" ref={menuRef}>
      <button
        ref={buttonRef}
        type="button"
        className="user-avatar-button"
        onClick={toggleMenu}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label={`Menu do usuário: ${displayName || subject}`}
      >
        <span className="user-avatar-initials">{initials}</span>
      </button>

      {isOpen && (
        <div className="user-account-dropdown" role="menu" aria-label="Opções de conta">
          <div className="user-dropdown-header">
            <div className="user-dropdown-avatar">{initials}</div>
            <div className="user-dropdown-info">
              <strong className="user-dropdown-name">{displayName || subject}</strong>
              {email && <span className="user-dropdown-email">{email}</span>}
              <div className="user-dropdown-badge">
                <span className="role-tag">{roleLabel}</span>
              </div>
            </div>
          </div>

          <div className="user-dropdown-details">
            <div className="detail-row">
              <span className="detail-label">Organização</span>
              <code className="detail-value">{organizationId}</code>
            </div>
            <div className="detail-row">
              <span className="detail-label">ID de Usuário</span>
              <span className="detail-value detail-truncate" title={subject}>
                {subject}
              </span>
            </div>
          </div>

          <div className="user-dropdown-provider-note">
            <small>
              Gerenciamento de credenciais e senha delegado ao provedor OIDC seguro da organização.
            </small>
          </div>

          <div className="user-dropdown-footer">
            <button
              type="button"
              className="user-logout-button"
              onClick={() => {
                setIsOpen(false)
                onSignOut()
              }}
              role="menuitem"
            >
              Sair da conta
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
