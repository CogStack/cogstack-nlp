import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Modal from '@/components/common/Modal.vue'

describe('Modal.vue', () => {
  it('renders header, body and footer slots', () => {
    const wrapper = mount(Modal, {
      props: { closable: true },
      slots: {
        header: '<h3>Title</h3>',
        body: '<p>Body content</p>',
        footer: '<button>OK</button>'
      },
      global: {
        stubs: { 'font-awesome-icon': true }
      }
    })

    expect(wrapper.text()).toContain('Title')
    expect(wrapper.text()).toContain('Body content')
    expect(wrapper.text()).toContain('OK')
  })

  it('shows close icon when closable', () => {
    const wrapper = mount(Modal, {
      props: { closable: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    expect(wrapper.find('.close').exists()).toBe(true)
  })

  it('hides close icon when not closable', () => {
    const wrapper = mount(Modal, {
      props: { closable: false },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    expect(wrapper.find('.close').exists()).toBe(false)
  })

  it('emits modal:close when close icon clicked', async () => {
    const wrapper = mount(Modal, {
      props: { closable: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    await wrapper.find('.close').trigger('click')
    expect(wrapper.emitted('modal:close')).toBeTruthy()
  })

  it('emits modal:close when mask clicked', async () => {
    const wrapper = mount(Modal, {
      props: { closable: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    await wrapper.find('.modal-mask').trigger('click')
    expect(wrapper.emitted('modal:close')).toBeTruthy()
  })

  it('does not close when container clicked (stop propagation)', async () => {
    const wrapper = mount(Modal, {
      props: { closable: true },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    await wrapper.find('.modal-container').trigger('click')
    expect(wrapper.emitted('modal:close')).toBeFalsy()
  })
})
