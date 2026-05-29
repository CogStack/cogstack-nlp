import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import NavBar from '@/components/common/NavBar.vue'

const ents = [
  { id: 1, value: 'a' },
  { id: 2, value: 'b' },
  { id: 3, value: 'c' }
]

describe('NavBar.vue', () => {
  beforeEach(() => {
    vi.spyOn(window, 'addEventListener')
    vi.spyOn(window, 'removeEventListener')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('disables back on first entity and next on last', () => {
    const wrapper = mount(NavBar, {
      props: { ents, currentEnt: ents[0], useEnts: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    const buttons = wrapper.findAll('button')
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].attributes('disabled')).toBeUndefined()
  })

  it('enables both buttons for middle entity', () => {
    const wrapper = mount(NavBar, {
      props: { ents, currentEnt: ents[1], useEnts: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    const buttons = wrapper.findAll('button')
    expect(buttons[0].attributes('disabled')).toBeUndefined()
    expect(buttons[1].attributes('disabled')).toBeUndefined()
  })

  it('emits select:next when next clicked', async () => {
    const wrapper = mount(NavBar, {
      props: { ents, currentEnt: ents[0], useEnts: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('select:next')).toBeTruthy()
  })

  it('emits select:back when back clicked', async () => {
    const wrapper = mount(NavBar, {
      props: { ents, currentEnt: ents[2], useEnts: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.emitted('select:back')).toBeTruthy()
  })

  it('uses nextBtnDisabled when useEnts is false', () => {
    const wrapper = mount(NavBar, {
      props: {
        useEnts: false,
        nextBtnDisabled: true,
        backBtnDisabled: false
      },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    const buttons = wrapper.findAll('button')
    expect(buttons[1].attributes('disabled')).toBeDefined()
    expect(buttons[0].attributes('disabled')).toBeUndefined()
  })

  it('registers keyup listener on mount', () => {
    mount(NavBar, {
      props: { ents, currentEnt: ents[1], useEnts: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    expect(window.addEventListener).toHaveBeenCalledWith('keyup', expect.any(Function))
  })
})
