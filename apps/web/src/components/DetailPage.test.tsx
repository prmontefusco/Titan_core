import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { DetailDescriptionList, DetailPageHeader, DetailSection } from './DetailPage'

describe('DetailPage components', () => {
  it('renderiza header com retorno, titulo, subtitulo, metadado e acao', () => {
    render(
      <MemoryRouter>
        <DetailPageHeader
          eyebrow="Livestock / Animal"
          title="Animal A1"
          subtitle="Identidade operacional"
          backTo="/animals"
          backLabel="Voltar para a busca"
          meta={<span>ATIVO</span>}
          actions={<button type="button">Executar</button>}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: /voltar para a busca/i })).toHaveAttribute(
      'href',
      '/animals',
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Animal A1' })).toBeInTheDocument()
    expect(screen.getByText('Identidade operacional')).toBeInTheDocument()
    expect(screen.getByText('ATIVO')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Executar' })).toBeInTheDocument()
  })

  it('renderiza secao e lista descritiva sem semantica vertical embutida', () => {
    render(
      <DetailSection title="Resumo" description="Dados expostos pelo backend.">
        <DetailDescriptionList>
          <dt>Nome</dt>
          <dd>LOTE-01</dd>
        </DetailDescriptionList>
      </DetailSection>,
    )

    expect(screen.getByRole('heading', { level: 2, name: 'Resumo' })).toBeInTheDocument()
    expect(screen.getByText('Dados expostos pelo backend.')).toBeInTheDocument()
    expect(screen.getByText('Nome')).toBeInTheDocument()
    expect(screen.getByText('LOTE-01')).toBeInTheDocument()
  })
})
