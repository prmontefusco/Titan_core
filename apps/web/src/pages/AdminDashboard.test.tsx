import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AdminDashboard } from './AdminDashboard'
import * as entityTypeRequestsApi from '../api/entityTypeRequests'

vi.mock('../api/entityTypeRequests', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/entityTypeRequests')>()
  return {
    ...actual,
    listPendingRequests: vi.fn(),
  }
})

describe('AdminDashboard', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  const defaultProps = {
    baseUrl: 'http://localhost:8000',
    accessToken: 'mock-token',
    organizationId: 'org-test-123',
  }

  it('exibe estado de carregamento e depois a contagem real de pedidos pendentes', async () => {
    vi.mocked(entityTypeRequestsApi.listPendingRequests).mockResolvedValueOnce([
      {
        request_id: 'req-1',
        organization_id: 'org-test-123',
        requested_kind: 'PRODUTOR',
        status: 'PENDENTE',
        requested_at: '2026-08-14T10:00:00Z',
        decided_at: null,
        decision_reason: null,
      },
      {
        request_id: 'req-2',
        organization_id: 'org-test-123',
        requested_kind: 'VETERINARIO',
        status: 'PENDENTE',
        requested_at: '2026-08-14T11:00:00Z',
        decided_at: null,
        decision_reason: null,
      },
    ])

    render(
      <MemoryRouter>
        <AdminDashboard {...defaultProps} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Visão geral de acessos')).toBeInTheDocument()

    // Loading inicial
    expect(screen.getByText(/Consultando solicitações pendentes/i)).toBeInTheDocument()

    // Aguarda carregar
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument()
      expect(screen.getByText('pedidos pendentes')).toBeInTheDocument()
    })

    // Lista de tipos
    expect(screen.getByText(/Produtor/i)).toBeInTheDocument()
    expect(screen.getByText(/Veterinário/i)).toBeInTheDocument()

    expect(screen.queryByText('Regras de Mercado')).not.toBeInTheDocument()
  })

  it('exibe mensagem quando não há pedidos pendentes', async () => {
    vi.mocked(entityTypeRequestsApi.listPendingRequests).mockResolvedValueOnce([])

    render(
      <MemoryRouter>
        <AdminDashboard {...defaultProps} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('0')).toBeInTheDocument()
      expect(screen.getByText(/Nenhuma solicitação aguardando decisão/i)).toBeInTheDocument()
    })
  })

  it('exibe aviso apropriado quando o usuário não tem permissão para a fila (403)', async () => {
    vi.mocked(entityTypeRequestsApi.listPendingRequests).mockRejectedValueOnce(
      new entityTypeRequestsApi.EntityTypeRequestApiError(403, 'Acesso negado'),
    )

    render(
      <MemoryRouter>
        <AdminDashboard {...defaultProps} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByText(/Não autorizado a consultar solicitações de acesso nesta Organization/i),
      ).toBeInTheDocument()
    })
  })

  it('exibe erro de backend sem convertê-lo em estado vazio', async () => {
    vi.mocked(entityTypeRequestsApi.listPendingRequests).mockRejectedValueOnce(
      new entityTypeRequestsApi.EntityTypeRequestApiError(500, 'FALHA_INTERNA', 'Falha temporária'),
    )

    render(<MemoryRouter><AdminDashboard {...defaultProps} /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Falha temporária')
      expect(screen.queryByText(/Nenhuma solicitação aguardando decisão/i)).not.toBeInTheDocument()
    })
  })
})
