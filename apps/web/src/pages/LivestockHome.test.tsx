import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { LivestockHome } from './LivestockHome'

describe('LivestockHome', () => {
  afterEach(() => {
    cleanup()
  })

  it('apresenta a entrada operacional Livestock com atalhos reais e Organization ativa', () => {
    render(
      <MemoryRouter>
        <LivestockHome kind="PRODUTOR" organizationId="org-piloto" />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: /Livestock/i })).toBeInTheDocument()
    expect(screen.getByText('org-piloto')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Buscar animal/i })).toHaveAttribute(
      'href',
      '/animals',
    )
    expect(screen.getByRole('link', { name: /Buscar lote/i })).toHaveAttribute('href', '/lots')
    expect(screen.getByRole('link', { name: /Regras de mercado/i })).toHaveAttribute(
      'href',
      '/rule-governance',
    )
  })
})
