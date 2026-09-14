import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetaAnnotationTask from '@/components/usecases/MetaAnnotationTask.vue'

const task = {
  id: 1,
  name: 'Temporality',
  description: 'When the concept occurred',
  options: [
    { id: 10, name: 'Current' },
    { id: 11, name: 'Historical' }
  ],
  value: 10,
  validated: true,
  predicted_value: null,
  acc: 0.9
}

describe('MetaAnnotationTask.vue', () => {
  it('renders the task name, description and option buttons', () => {
    const wrapper = mount(MetaAnnotationTask, { props: { task } })

    expect(wrapper.text()).toContain('Temporality')
    expect(wrapper.text()).toContain('When the concept occurred')
    const buttons = wrapper.findAll('button.task-value')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toContain('Current')
    expect(buttons[1].text()).toContain('Historical')
  })

  it('emits select:metaAnno when an option is clicked', async () => {
    const wrapper = mount(MetaAnnotationTask, { props: { task } })

    await wrapper.findAll('button.task-value')[1].trigger('click')

    expect(wrapper.emitted('select:metaAnno')[0]).toEqual([task, task.options[1]])
  })
})
