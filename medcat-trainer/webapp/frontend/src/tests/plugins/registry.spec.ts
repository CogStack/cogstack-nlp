import { describe, it, expect, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { clearPluginRegistry, getMenuItems, getSlotComponents, registerPlugin } from '@/plugins/registry'

const Stub = defineComponent({
  name: 'StubPlugin',
  render: () => h('span', 'stub'),
})

describe('plugins/registry', () => {
  beforeEach(() => {
    clearPluginRegistry()
  })

  it('registers menu items and slot components', () => {
    registerPlugin({
      menuItems: [{ id: 'ee', label: 'Enterprise', route: '/ee' }],
      slots: { 'home:after-projects': Stub },
    })
    expect(getMenuItems()).toHaveLength(1)
    expect(getMenuItems()[0].label).toBe('Enterprise')
    expect(getSlotComponents('home:after-projects')).toHaveLength(1)
  })

  it('clearPluginRegistry resets state', () => {
    registerPlugin({ menuItems: [{ id: 'x', label: 'X' }] })
    clearPluginRegistry()
    expect(getMenuItems()).toHaveLength(0)
    expect(getSlotComponents('home:after-projects')).toHaveLength(0)
  })
})
