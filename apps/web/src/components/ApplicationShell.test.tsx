import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApplicationShell } from './ApplicationShell'

describe('ApplicationShell', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  const mockUserMenuProps = {
    displayName: 'Carlos Silva',
    email: 'carlos.silva@fazenda.com',
    subject: 'user-sub-123',
    organizationId: 'org-titan-pilot',
    roleLabel: 'Administrador',
    onSignOut: vi.fn(),
  }

  const mockNavItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/animals', label: 'Animais', icon: '🐄' },
    { path: '/admin', label: 'Fila de aprovação', icon: '📋' },
  ]

  it('renderiza a TopBar com logo, contexto da organização e avatar do usuário', () => {
    render(
      <MemoryRouter>
        <ApplicationShell
          organizationId="org-titan-pilot"
          userMenuProps={mockUserMenuProps}
          navigationItems={mockNavItems}
        >
          <div>Conteúdo Principal de Teste</div>
        </ApplicationShell>
      </MemoryRouter>,
    )

    // Logo e marcas
    expect(screen.getByAltText('Titan')).toBeInTheDocument()
    expect(screen.getByText('Titan')).toBeInTheDocument()
    expect(screen.getByText('Livestock')).toBeInTheDocument()

    // Contexto da Organização
    expect(screen.getByText('org-titan-pilot')).toBeInTheDocument()

    // Conteúdo filho
    expect(screen.getByText('Conteúdo Principal de Teste')).toBeInTheDocument()

    // Itens de navegação da sidebar
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Animais')).toBeInTheDocument()
    expect(screen.getByText('Fila de aprovação')).toBeInTheDocument()
  })

  it('abre e fecha o UserAccountMenu exibindo dados do usuário e aciona logout', () => {
    render(
      <MemoryRouter>
        <ApplicationShell
          organizationId="org-titan-pilot"
          userMenuProps={mockUserMenuProps}
          navigationItems={mockNavItems}
        >
          <div>Conteúdo</div>
        </ApplicationShell>
      </MemoryRouter>,
    )

    // Botão de avatar
    const avatarBtn = screen.getByRole('button', { name: /Menu do usuário: Carlos Silva/i })
    expect(avatarBtn).toBeInTheDocument()

    // Inicialmente fechado
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    // Clica para abrir
    fireEvent.click(avatarBtn)
    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByText('carlos.silva@fazenda.com')).toBeInTheDocument()
    expect(screen.getByText('Administrador')).toBeInTheDocument()

    // Clica no botão de sair
    const logoutBtn = screen.getByRole('menuitem', { name: /Sair da conta/i })
    fireEvent.click(logoutBtn)
    expect(mockUserMenuProps.onSignOut).toHaveBeenCalled()
  })

  it('fecha o UserAccountMenu ao pressionar a tecla Escape', () => {
    render(
      <MemoryRouter>
        <ApplicationShell
          organizationId="org-titan-pilot"
          userMenuProps={mockUserMenuProps}
          navigationItems={mockNavItems}
        >
          <div>Conteúdo</div>
        </ApplicationShell>
      </MemoryRouter>,
    )

    const avatarBtn = screen.getByRole('button', { name: /Menu do usuário: Carlos Silva/i })
    fireEvent.click(avatarBtn)
    expect(screen.getByRole('menu')).toBeInTheDocument()

    // Pressiona Escape
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
