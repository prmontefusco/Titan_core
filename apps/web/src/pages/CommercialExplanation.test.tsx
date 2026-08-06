import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CommercialExplanation } from './CommercialExplanation'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTela(animalId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/animals/${animalId}/commercial-explanation`]}>
      <Routes>
        <Route
          path="/animals/:animalId/commercial-explanation"
          element={<CommercialExplanation {...options} />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CommercialExplanation', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('não executa nada até o operador clicar', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderTela()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('mostra a narrativa e o detalhe por mercado depois de executar', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => ({
          subject_type: 'animal',
          subject_id: 'a1',
          requested_markets: ['exportacao-estados-unidos'],
          commercial_outlook: 'PODE_VENDER',
          can_sell_to_any_requested_market: true,
          executive_summary: 'Resumo executivo.',
          narrative: 'O animal pode ser vendido para os EUA agora.',
          recommended_next_action: 'Nenhuma ação necessária.',
          markets: [
            {
              market: 'exportacao-estados-unidos',
              status: 'ELEGIVEL',
              summary: 'Elegível.',
              why: ['Todos os requisitos foram atendidos.'],
              next_action: null,
              affected_animal_ids: [],
            },
          ],
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /gerar explicação comercial/i }))

    expect(await screen.findByText(/PODE_VENDER/)).toBeInTheDocument()
    expect(screen.getByText(/pode ser vendido para os EUA agora/)).toBeInTheDocument()
    expect(screen.getByText(/Todos os requisitos foram atendidos/)).toBeInTheDocument()
  })

  it('mostra a nota de revisão humana necessária', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          reason_code: 'REVISAO_HUMANA_NECESSARIA',
          detail: 'A emissão automática foi recusada.',
          proposal_id: 'p1',
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /gerar explicação comercial/i }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/revisão humana/i)
    expect(alerta).toHaveTextContent('p1')
  })
})
