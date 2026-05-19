<template>
  <div class="list-section">
    <div v-if="projects.length > 0" class="table-container">
      <v-data-table
        :items="filteredProjects"
        :headers="alignedTableHeaders"
        :hover="true"
        :mobile="false"
        :items-per-page="-1"
        hide-default-footer
        @click:row="handleRowClick"
        class="admin-table"
        dense>
        <template #header.name>
          <div class="column-header">
            <button
              type="button"
              class="column-header-sort"
              :class="{ active: sortBy === 'name' }"
              title="Sort by title"
              @click="toggleSort('name')">
              Title
              <font-awesome-icon
                class="sort-icon"
                :icon="sortBy === 'name' ? (sortOrder === 'asc' ? 'sort-up' : 'sort-down') : 'sort'"
              />
            </button>
            <input
              v-model="searchQuery"
              type="search"
              class="form-control form-control-sm header-filter-input"
              placeholder="Filter…"
              aria-label="Filter by title"
              @click.stop
            />
          </div>
        </template>

        <template #header.project_status>
          <div class="column-header">
            <span class="column-header-label">Status</span>
            <select
              v-model="statusFilter"
              class="form-control form-control-sm header-filter-input"
              aria-label="Filter by project status"
              @click.stop>
              <option
                v-for="opt in statusFilterOptions"
                :key="opt.value"
                :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </template>

        <template #header.require_entity_validation>
          <div class="column-header">
            <span class="column-header-label">Mode</span>
            <select
              v-model="modeFilter"
              class="form-control form-control-sm header-filter-input"
              aria-label="Filter by annotate or validate"
              @click.stop>
              <option
                v-for="opt in modeFilterOptions"
                :key="opt.value"
                :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </template>

        <template #header.create_time>
          <button
            type="button"
            class="column-header-sort"
            :class="{ active: sortBy === 'create_time' }"
            title="Sort by create date"
            @click="toggleSort('create_time')">
            Created
            <font-awesome-icon
              class="sort-icon"
              :icon="sortBy === 'create_time' ? (sortOrder === 'asc' ? 'sort-up' : 'sort-down') : 'sort'"
            />
          </button>
        </template>

        <template #header.last_modified>
          <button
            type="button"
            class="column-header-sort"
            :class="{ active: sortBy === 'last_modified' }"
            title="Sort by last modified"
            @click="toggleSort('last_modified')">
            Modified
            <font-awesome-icon
              class="sort-icon"
              :icon="sortBy === 'last_modified' ? (sortOrder === 'asc' ? 'sort-up' : 'sort-down') : 'sort'"
            />
          </button>
        </template>

        <template #item.name="{ item }">
          <div class="project-name-cell">
            <strong class="project-name">{{ item.name }}</strong>
          </div>
        </template>
        <template #item.project_status="{ item }">
          <span class="badge" :class="getStatusClass(item.project_status)">
            {{ getStatusText(item.project_status) }}
          </span>
        </template>
        <template #item.require_entity_validation="{ item }">
          <span class="badge" :class="getModeClass(item.require_entity_validation)">
            {{ getModeText(item.require_entity_validation) }}
          </span>
        </template>
        <template #item.dataset="{ item }">
          <span>{{ getDatasetName(item.dataset) }}</span>
        </template>
        <template #item.create_time="{ item }">
          <span class="date-cell">{{ formatDate(item.create_time) }}</span>
        </template>
        <template #item.last_modified="{ item }">
          <span class="date-cell">{{ formatDate(item.last_modified) }}</span>
        </template>
        <template #item.actions="{ item }">
          <div class="action-buttons" @click.stop>
            <button
              class="btn btn-sm btn-action btn-clone"
              @click="$emit('clone-project', item)"
              :title="'Clone ' + item.name">
              <font-awesome-icon icon="copy"></font-awesome-icon>
            </button>
            <button
              class="btn btn-sm btn-action btn-reset"
              @click="$emit('confirm-reset', item)"
              :title="'Reset ' + item.name">
              <font-awesome-icon icon="undo"></font-awesome-icon>
            </button>
            <button
              class="btn btn-sm btn-action btn-delete"
              @click="$emit('confirm-delete', item)"
              :title="'Delete ' + item.name">
              <font-awesome-icon icon="trash"></font-awesome-icon>
            </button>
          </div>
        </template>

        <template #no-data>
          <div class="empty-state empty-state-filtered">
            <h4>No Matching Projects</h4>
            <p>No projects match the current filters.</p>
            <button type="button" class="btn btn-outline-primary" @click="clearFilters">
              Clear filters
            </button>
          </div>
        </template>
      </v-data-table>
    </div>

    <div v-else class="empty-state">
      <h4>No Projects Yet</h4>
      <p>You don't have any projects yet. Create one to get started!</p>
      <button class="btn btn-primary btn-create-empty" @click="$emit('create-project')">
        <font-awesome-icon icon="plus"></font-awesome-icon>
        <span>Create Your First Project</span>
      </button>
    </div>
  </div>
</template>

<script>
import {
  ALL_FILTER,
  STATUS_FILTER_OPTIONS,
  MODE_FILTER_OPTIONS,
  filterAndSortProjects
} from '@/utils/projectListFilters'

export default {
  name: 'ProjectsList',
  props: {
    projects: {
      type: Array,
      required: true
    },
    datasets: {
      type: Array,
      required: true
    }
  },
  emits: ['select-project', 'clone-project', 'confirm-reset', 'confirm-delete', 'create-project'],
  data() {
    return {
      searchQuery: '',
      debouncedSearchQuery: '',
      searchDebounceTimer: null,
      statusFilter: ALL_FILTER,
      modeFilter: ALL_FILTER,
      sortBy: 'last_modified',
      sortOrder: 'desc',
      statusFilterOptions: STATUS_FILTER_OPTIONS,
      modeFilterOptions: MODE_FILTER_OPTIONS,
      tableHeaders: [
        { title: 'Title', value: 'name', sortable: false, width: '14%' },
        {
          title: 'Description',
          value: 'description',
          sortable: false,
          headerProps: { class: 'col-hide-narrow' },
          cellProps: { class: 'col-hide-narrow' }
        },
        { title: 'Status', value: 'project_status', sortable: false, width: '5.5rem' },
        { title: 'Mode', value: 'require_entity_validation', sortable: false, width: '5rem' },
        { title: 'Dataset', value: 'dataset', sortable: false, width: '10%' },
        { title: 'Created', value: 'create_time', sortable: false, width: '5.5rem' },
        { title: 'Modified', value: 'last_modified', sortable: false, width: '6.5rem' },
        { title: 'Actions', value: 'actions', sortable: false, width: '6.5rem' }
      ]
    }
  },
  computed: {
    alignedTableHeaders() {
      return this.tableHeaders.map(h => ({ align: 'start', ...h }))
    },
    filteredProjects() {
      return filterAndSortProjects(this.projects, {
        searchQuery: this.debouncedSearchQuery,
        statusFilter: this.statusFilter,
        modeFilter: this.modeFilter,
        sortBy: this.sortBy,
        sortOrder: this.sortOrder
      })
    },
  },
  watch: {
    searchQuery(val) {
      clearTimeout(this.searchDebounceTimer)
      this.searchDebounceTimer = setTimeout(() => {
        this.debouncedSearchQuery = val
      }, 200)
    }
  },
  beforeUnmount() {
    clearTimeout(this.searchDebounceTimer)
  },
  methods: {
    toggleSort(key) {
      if (this.sortBy === key) {
        this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortBy = key
        this.sortOrder = key === 'name' ? 'asc' : 'desc'
      }
    },
    clearFilters() {
      this.searchQuery = ''
      this.debouncedSearchQuery = ''
      this.statusFilter = ALL_FILTER
      this.modeFilter = ALL_FILTER
    },
    handleRowClick(event, { item }) {
      this.$emit('select-project', event, { item })
    },
    formatDate(value) {
      if (!value) return '—'
      return new Date(value).toLocaleDateString()
    },
    getStatusClass(status) {
      const classes = {
        A: 'badge-primary',
        C: 'badge-success',
        D: 'badge-danger'
      }
      return classes[status] || 'badge-secondary'
    },
    getStatusText(status) {
      const texts = {
        A: 'Annotating',
        C: 'Complete',
        D: 'Discontinued'
      }
      return texts[status] || status
    },
    getModeClass(requireEntityValidation) {
      return requireEntityValidation ? 'badge-primary' : 'badge-secondary'
    },
    getModeText(requireEntityValidation) {
      return requireEntityValidation ? 'Annotate' : 'Validate'
    },
    getDatasetName(datasetId) {
      const dataset = this.datasets.find(ds => ds.id === datasetId)
      return dataset ? dataset.name : 'N/A'
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';
@import '@/styles/project-list-filters';

.list-section {
  display: flex;
  flex-direction: column;
  min-height: 0;

  .admin-table {
    :deep(.v-table__wrapper) {
      overflow-x: hidden;
    }

    :deep(table) {
      table-layout: fixed;
      width: 100%;
    }

    :deep(tbody tr) {
      cursor: pointer;
    }

    :deep(thead th),
    :deep(tbody td) {
      text-align: left !important;
    }

    :deep(thead th) {
      vertical-align: bottom;
      padding: 4px 6px;
      font-size: 0.8rem;
    }

    :deep(tbody td) {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 0.85rem;
      padding: 4px 6px !important;
      vertical-align: middle;
    }

    :deep(.action-buttons) {
      justify-content: flex-start;
    }

    :deep(.col-hide-narrow) {
      @media (max-width: 1200px) {
        display: none !important;
      }
    }
  }

  .project-name {
    font-size: 0.95rem;
    color: var(--color-heading);
  }

  .date-cell {
    font-size: 0.85rem;
    white-space: nowrap;
  }

  .empty-state-filtered {
    padding: 40px 20px;
    text-align: center;
  }
}
</style>
