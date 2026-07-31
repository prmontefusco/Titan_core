import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthenticatedPrincipalRequestError, fetchAuthenticatedPrincipal } from './authentication'

describe('fetchAuthenticatedPrincipal', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('envia o Access Token como Bearer e devolve o principal', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ issuer: 'issuer', subject: 'sub-1', scopes: ['openid'] }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const principal = await fetchAuthenticatedPrincipal('http://127.0.0.1:8000', 'meu-token')

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/technical/authentication', {
      headers: { Authorization: 'Bearer meu-token' },
    })
    expect(principal).toEqual({ issuer: 'issuer', subject: 'sub-1', scopes: ['openid'] })
  })

  it('lança AuthenticatedPrincipalRequestError quando a API recusa o token', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }),
    )

    await expect(
      fetchAuthenticatedPrincipal('http://127.0.0.1:8000', 'token-invalido'),
    ).rejects.toBeInstanceOf(AuthenticatedPrincipalRequestError)
  })
})
