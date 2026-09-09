import { describe, expect, it, vi } from 'vitest'
import { titanRequest, type RequestOptions } from './client'

class TestApiError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`status ${status}`)
    this.status = status
  }
}

const baseOptions: RequestOptions = {
  baseUrl: 'http://127.0.0.1:8000',
  accessToken: 'token-expirado',
  organizationId: 'org-1',
}

function erro(response: Response): Promise<Error> {
  return Promise.resolve(new TestApiError(response.status))
}

describe('titanRequest', () => {
  it('renova token em 401 e repete a requisição uma única vez', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'expirado' }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const resultado = await titanRequest<{ ok: boolean }>(
      '/v1/recurso',
      {
        ...baseOptions,
        renewAccessToken: vi.fn().mockResolvedValue('token-renovado'),
      },
      {},
      erro,
    )

    expect(resultado).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({
      Authorization: 'Bearer token-expirado',
      'X-Titan-Organization-Id': 'org-1',
    })
    expect(fetchMock.mock.calls[1][1]?.headers).toMatchObject({
      Authorization: 'Bearer token-renovado',
      'X-Titan-Organization-Id': 'org-1',
    })
  })

  it('preserva o erro 401 quando a renovação silenciosa não produz novo token', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'expirado' }), { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      titanRequest(
        '/v1/recurso',
        {
          ...baseOptions,
          renewAccessToken: vi.fn().mockResolvedValue(null),
        },
        {},
        erro,
      ),
    ).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
