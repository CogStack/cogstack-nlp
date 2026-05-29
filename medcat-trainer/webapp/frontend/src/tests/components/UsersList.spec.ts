import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UsersList from '@/components/admin/UsersList.vue'

const users = [
  { id: 1, username: 'alice', email: 'alice@example.com', is_staff: true, is_superuser: false },
  { id: 2, username: 'bob', email: 'bob@example.com', is_staff: false, is_superuser: true }
]

describe('UsersList.vue', () => {
  const mountList = (props: Record<string, unknown> = {}) =>
    mount(UsersList, {
      props: { users, ...props },
      global: {
        stubs: {
          'v-data-table': {
            template: '<div class="stub-table"></div>',
            props: ['items', 'headers']
          },
          'font-awesome-icon': true
        }
      }
    })

  it('shows empty state when there are no users', () => {
    const wrapper = mountList({ users: [] })
    expect(wrapper.text()).toContain('No Users')
    expect(wrapper.text()).toContain('Add Your First User')
  })

  it('emits add-user from empty-state button', async () => {
    const wrapper = mountList({ users: [] })
    await wrapper.find('.btn-create-empty').trigger('click')
    expect(wrapper.emitted('add-user')).toBeTruthy()
  })

  it('emits select-user on row click', () => {
    const wrapper = mountList()
    const vm = wrapper.vm as {
      handleRowClick: (e: Event, payload: { item: (typeof users)[0] }) => void
    }
    const event = new Event('click')
    vm.handleRowClick(event, { item: users[1] })
    expect(wrapper.emitted('select-user')?.[0]).toEqual([event, { item: users[1] }])
  })
})
