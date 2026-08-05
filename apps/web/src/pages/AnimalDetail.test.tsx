import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnimalDetail } from './AnimalDetail'

const options = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'meu-token',
  organizationId: 'org-1',
}

function renderDetalhe(animalId = 'a1') {
  return render(
    <MemoryRouter initialEntries={[`/animals/${animalId}`]}>
      <Routes>
        <Route path="/animals/:animalId" element={<AnimalDetail {...options} />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnimalDetail', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    cleanup()
  })

  it('mostra a identidade do animal e declara que a localização atual não está disponível', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          animal_id: 'a1',
          sex: 'FEMALE',
          breed: 'Nelore',
          birth_date: '2024-01-01',
          birth_property_id: null,
          identifiers: [],
          saida: null,
        }),
      }),
    )

    renderDetalhe()

    expect(await screen.findByText('Nelore')).toBeInTheDocument()
    expect(screen.getByText(/não disponível nesta versão/i)).toBeInTheDocument()
  })

  it('mostra mensagem clara quando o animal não é encontrado (404)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ reason_code: 'RECURSO_NAO_ENCONTRADO', detail: 'não encontrado' }),
      }),
    )

    renderDetalhe()

    expect(await screen.findByRole('alert')).toHaveTextContent(/não encontrado/i)
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

    renderDetalhe()

    expect(await screen.findByRole('alert')).toHaveTextContent(/não tem permissão/i)
  })
})
