import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageContext } from './PageContext'

describe('PageContext', () => {
  it('renderiza os itens de contexto informados', () => {
    render(
      <PageContext
        description="Escopo que altera o significado desta tela."
        items={[
          { label: 'Organization', value: 'org-1' },
          { label: 'Finalidade', value: 'market.internal' },
        ]}
      />,
    )

    expect(screen.getByRole('heading', { name: /contexto operacional/i })).toBeInTheDocument()
    expect(screen.getByText(/escopo que altera o significado desta tela/i)).toBeInTheDocument()
    expect(screen.getByText('Organization')).toBeInTheDocument()
    expect(screen.getByText('org-1')).toBeInTheDocument()
    expect(screen.getByText('Finalidade')).toBeInTheDocument()
    expect(screen.getByText('market.internal')).toBeInTheDocument()
  })
})
