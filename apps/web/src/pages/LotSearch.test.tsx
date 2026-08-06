import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LotSearch } from './LotSearch'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('LotSearch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('mostra os lotes devolvidos pelo backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            {
              lot_id: 'l1',
              property_id: 'p1',
              code: 'LOTE-01',
              name: 'Lote de engorda',
              lot_type: 'ENGORDA',
              status: 'ATIVO',
            },
          ],
          limit: 20,
          offset: 0,
          has_more: false,
        }),
      }),
    )

    render(
      <MemoryRouter>
        <LotSearch {...options} />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/LOTE-01/)).toBeInTheDocument()
  })

  it('mostra mensagem clara quando falta permissão (403)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ reason_code: 'PERMISSAO_AUSENTE', detail: 'sem permissão' }),
      }),
    )

    render(
      <MemoryRouter>
        <LotSearch {...options} />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/não tem permissão/i)
  })

  it('mostra estado vazio quando não há lotes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], limit: 20, offset: 0, has_more: false }),
      }),
    )

    render(
      <MemoryRouter>
        <LotSearch {...options} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/nenhum lote encontrado/i)).toBeInTheDocument()
    })
  })
})
