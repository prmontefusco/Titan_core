import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NotFoundState,
  UnauthorizedState,
} from './AsyncStates'

describe('AsyncStates', () => {
  it('renderiza loading com semantica de status', () => {
    render(<LoadingState message="Carregando dados..." tone="compact" />)

    expect(screen.getByRole('status')).toHaveTextContent('Carregando dados...')
  })

  it('renderiza estados de alerta distintos com titulo e mensagem', () => {
    render(
      <>
        <UnauthorizedState title="Sem acesso" message="Acesso negado." />
        <ErrorState title="Falha" message="Erro inesperado." />
        <NotFoundState title="Ausente" message="Recurso não encontrado." />
        <EmptyState title="Vazio" message="Nenhum item disponível." />
      </>,
    )

    expect(screen.getByText('Sem acesso')).toBeInTheDocument()
    expect(screen.getByText('Erro inesperado.')).toBeInTheDocument()
    expect(screen.getByText('Recurso não encontrado.')).toBeInTheDocument()
    expect(screen.getByText('Nenhum item disponível.')).toBeInTheDocument()
  })
})
