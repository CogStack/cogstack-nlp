import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  UNAUTHORIZED_EVENT,
  handleUnauthorized,
  resetUnauthorizedGuard,
  registerUnauthorizedInterceptor
} from '@/httpAuth'
import EventBus from '@/event-bus'

// Minimal axios-like stub capturing the registered response interceptor handlers.
const makeHttpStub = () => {
  const handlers: {
    onFulfilled?: (resp: unknown) => unknown
    onRejected?: (error: unknown) => unknown
  } = {}
  return {
    handlers,
    defaults: { headers: { common: { Authorization: 'Token abc' } as Record<string, string> } },
    interceptors: {
      response: {
        use: (onFulfilled: (resp: unknown) => unknown, onRejected: (error: unknown) => unknown) => {
          handlers.onFulfilled = onFulfilled
          handlers.onRejected = onRejected
          return 1
        }
      }
    }
  }
}

describe('httpAuth unauthorized handling', () => {
  beforeEach(() => {
    resetUnauthorizedGuard()
    // Seed auth cookies as if the user were logged in.
    for (const c of ['api-token', 'username', 'admin', 'user-id']) {
      document.cookie = `${c}=value; path=/`
    }
  })

  afterEach(() => {
    EventBus.$off(UNAUTHORIZED_EVENT)
  })

  it('clears auth state and emits the unauthorized event', () => {
    const http = makeHttpStub()
    const onEvent = vi.fn()
    EventBus.$on(UNAUTHORIZED_EVENT, onEvent)

    handleUnauthorized(http as never)

    expect(http.defaults.headers.common['Authorization']).toBeUndefined()
    expect(document.cookie).not.toContain('api-token=value')
    expect(document.cookie).not.toContain('username=value')
    expect(onEvent).toHaveBeenCalledTimes(1)
  })

  it('only prompts once for a burst of 401s until the guard is reset', () => {
    const http = makeHttpStub()
    const onEvent = vi.fn()
    EventBus.$on(UNAUTHORIZED_EVENT, onEvent)

    handleUnauthorized(http as never)
    handleUnauthorized(http as never)
    handleUnauthorized(http as never)
    expect(onEvent).toHaveBeenCalledTimes(1)

    resetUnauthorizedGuard()
    handleUnauthorized(http as never)
    expect(onEvent).toHaveBeenCalledTimes(2)
  })

  it('interceptor triggers the handler on a 401 response and re-rejects', async () => {
    const http = makeHttpStub()
    registerUnauthorizedInterceptor(http as never)
    const onEvent = vi.fn()
    EventBus.$on(UNAUTHORIZED_EVENT, onEvent)

    const error = { response: { status: 401 } }
    await expect(http.handlers.onRejected!(error)).rejects.toBe(error)
    expect(onEvent).toHaveBeenCalledTimes(1)
  })

  it('interceptor ignores non-401 errors', async () => {
    const http = makeHttpStub()
    registerUnauthorizedInterceptor(http as never)
    const onEvent = vi.fn()
    EventBus.$on(UNAUTHORIZED_EVENT, onEvent)

    const error = { response: { status: 500 } }
    await expect(http.handlers.onRejected!(error)).rejects.toBe(error)
    expect(onEvent).not.toHaveBeenCalled()
    // A successful response passes through untouched.
    expect(http.handlers.onFulfilled!({ ok: true })).toEqual({ ok: true })
  })
})
