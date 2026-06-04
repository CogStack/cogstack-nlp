import { describe, it, expect, vi } from 'vitest'
import EventBus from '@/event-bus'

describe('event-bus', () => {
  it('emits and receives events', () => {
    const handler = vi.fn()
    EventBus.$on('test:event', handler)
    EventBus.$emit('test:event', 'payload')
    expect(handler).toHaveBeenCalledWith('payload')
    EventBus.$off('test:event', handler)
  })

  it('stops receiving after $off', () => {
    const handler = vi.fn()
    EventBus.$on('test:off', handler)
    EventBus.$off('test:off', handler)
    EventBus.$emit('test:off')
    expect(handler).not.toHaveBeenCalled()
  })

  it('supports multiple listeners on the same event', () => {
    const h1 = vi.fn()
    const h2 = vi.fn()
    EventBus.$on('multi', h1)
    EventBus.$on('multi', h2)
    EventBus.$emit('multi', 42)
    expect(h1).toHaveBeenCalledWith(42)
    expect(h2).toHaveBeenCalledWith(42)
    EventBus.$off('multi', h1)
    EventBus.$off('multi', h2)
  })
})
