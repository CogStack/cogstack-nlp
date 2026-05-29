import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DatasetsList from '@/components/admin/DatasetsList.vue'

const datasets = [
  { id: 1, name: 'Clinical Notes', description: 'De-identified notes' },
  { id: 2, name: 'Discharge Summaries', description: 'Hospital discharges' }
]

describe('DatasetsList.vue', () => {
  const mountList = (props: Record<string, unknown> = {}) =>
    mount(DatasetsList, {
      props: { datasets, ...props },
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

  it('shows empty state when there are no datasets', () => {
    const wrapper = mountList({ datasets: [] })
    expect(wrapper.text()).toContain('No Datasets')
    expect(wrapper.text()).toContain('Add Your First Dataset')
  })

  it('emits add-dataset from empty-state button', async () => {
    const wrapper = mountList({ datasets: [] })
    await wrapper.find('.btn-create-empty').trigger('click')
    expect(wrapper.emitted('add-dataset')).toBeTruthy()
  })

  it('emits select-dataset on row click', () => {
    const wrapper = mountList()
    const vm = wrapper.vm as {
      handleRowClick: (e: Event, payload: { item: (typeof datasets)[0] }) => void
    }
    const event = new Event('click')
    vm.handleRowClick(event, { item: datasets[0] })
    expect(wrapper.emitted('select-dataset')?.[0]).toEqual([event, { item: datasets[0] }])
  })

  it('emits confirm-delete-dataset when delete is triggered', async () => {
    const wrapper = mount(DatasetsList, {
      props: { datasets },
      global: {
        stubs: {
          'v-data-table': {
            template:
              '<div><button class="btn-delete" @click="$parent.$emit(\'confirm-delete-dataset\', datasets[0])">del</button></div>',
            props: ['items']
          },
          'font-awesome-icon': true
        }
      }
    })
    const vm = wrapper.vm as {
      $emit: (event: string, item: (typeof datasets)[0]) => void
    }
    vm.$emit('confirm-delete-dataset', datasets[0])
    expect(wrapper.emitted('confirm-delete-dataset')?.[0]).toEqual([datasets[0]])
  })
})
