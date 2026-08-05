import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnimalSearch } from './AnimalSearch'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

describe('AnimalSearch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('mostra os animais devolvidos pelo backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            {
              animal_id: 'a1',
              sex: 'FEMALE',
              breed: 'Nelore',
              identifiers: [{ identifier_id: 'i1', type: 'OFFICIAL_SISBOV', value: 'BR9988', state: 'ACTIVE' }],
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
        <AnimalSearch {...options} />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/BR9988/)).toBeInTheDocument()
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
        <AnimalSearch {...options} />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/não tem permissão/i)
  })

  it('mostra estado vazio quando não há resultados', async () => {
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
        <AnimalSearch {...options} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/nenhum animal encontrado/i)).toBeInTheDocument()
    })
  })
})
