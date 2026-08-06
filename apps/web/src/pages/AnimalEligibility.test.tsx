import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnimalEligibility } from './AnimalEligibility'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderTela(animalId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/animals/${animalId}/eligibility`]}>
      <Routes>
        <Route path="/animals/:animalId/eligibility" element={<AnimalEligibility {...options} />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnimalEligibility', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('não executa nada até o operador clicar em Executar', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    renderTela()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('mostra o resultado depois de executar', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => ({
          animal_id: 'a1',
          result: 'APROVADA',
          outcome: 'ELEGIVEL',
          evaluation_id: 'ev1',
          decision_id: 'dec1',
          dossier_id: 'dos1',
          knowledge_cutoff: '2026-08-05T00:00:00Z',
          knowledge_limitations: [],
          reasons: [],
          governed_rule: null,
        }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /executar elegibilidade/i }))

    expect(await screen.findByText('APROVADA')).toBeInTheDocument()
    expect(screen.getByText('ELEGIVEL')).toBeInTheDocument()
  })

  it('mostra a nota de revisão humana necessária com o proposal_id', async () => {
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
    fireEvent.click(screen.getByRole('button', { name: /executar elegibilidade/i }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/revisão humana/i)
    expect(alerta).toHaveTextContent('p1')
  })

  it('mostra erro genérico sem crashar em outras falhas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ reason_code: 'RECURSO_NAO_ENCONTRADO', detail: 'não encontrado' }),
      }),
    )

    renderTela()
    fireEvent.click(screen.getByRole('button', { name: /executar elegibilidade/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/não encontrado/i)
  })
})
