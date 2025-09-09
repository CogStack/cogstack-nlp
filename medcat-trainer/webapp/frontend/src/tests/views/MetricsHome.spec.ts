import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import MetricsHome from '@/views/MetricsHome.vue'

const mockReports = [
  {
    report_id: 1,
    report_name: 'Test Report',
    created_user: 'user1',
    create_time: '2025-09-09T12:00:00Z',
    projects: ['p1', 'p2'],
    status: 'pending',
    cleanup: false
  }
]

const mockProjects = {
  p1: { name: 'Project One' },
  p2: { name: 'Project Two' }
}

describe('MetricsHome.vue', () => {
  let mockGet
  beforeEach(() => {
    mockGet = vi.fn((url) => {
      if (url === '/api/metrics-job/') {
        return Promise.resolve({ data: { reports: mockReports } })
      }
      if (url === '/api/project-annotate-entities/p1/') {
        return Promise.resolve({ data: mockProjects.p1 })
      }
      if (url === '/api/project-annotate-entities/p2/') {
        return Promise.resolve({ data: mockProjects.p2 })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('calls /api/metrics-job/ when created', async () => {
    mount(MetricsHome, {
      global: {
        mocks: { $http: { get: mockGet } },
        stubs: ['v-data-table', 'v-overlay', 'v-progress-circular', 'modal', 'font-awesome-icon', 'router-link']
      }
    })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/api/metrics-job/')
  })

  it('fetches projects after reports are loaded', async () => {
    mount(MetricsHome, {
      global: {
        mocks: { $http: { get: mockGet } },
        stubs: ['v-data-table', 'v-overlay', 'v-progress-circular', 'modal', 'font-awesome-icon', 'router-link']
      }
    })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/api/project-annotate-entities/p1/')
    expect(mockGet).toHaveBeenCalledWith('/api/project-annotate-entities/p2/')
  })

  it('renders correct table headers', async () => {
    const wrapper = mount(MetricsHome, {
      global: {
        mocks: { $http: { get: mockGet } },
        stubs: ['v-data-table', 'v-overlay', 'v-progress-circular', 'modal', 'font-awesome-icon', 'router-link']
      }
    })
    await flushPromises()
    const headers = wrapper.vm.reports.headers.map(h => h.title)
    expect(headers).toEqual([
      'ID',
      'Report Name',
      'Created User',
      'Create Time',
      'Projects',
      'Status',
      'Remove'
    ])
  })
})
