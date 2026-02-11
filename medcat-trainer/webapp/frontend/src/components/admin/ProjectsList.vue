<template>
  <div class="project-list-section">
    <div class="section-header">
      <h3>
        Your Projects
        <span class="project-count">({{ projects.length }})</span>
      </h3>
    </div>

    <div v-if="projects.length > 0" class="projects-table-container">
      <v-data-table
        :items="projects"
        :headers="tableHeaders"
        :hover="true"
        @click:row="handleRowClick"
        hide-default-footer
        :items-per-page="-1"
        class="projects-table"
        item-class="project-row"
        dense>
        <template #item.name="{ item }">
          <div class="project-name-cell">
            <strong class="project-name">{{ item.name }}</strong>
          </div>
        </template>
        <template #item.status="{ item }">
          <span class="badge" :class="getStatusClass(item.project_status)">
            {{ getStatusText(item.project_status) }}
          </span>
        </template>
        <template #item.dataset="{ item }">
          <span class="dataset-name">{{ getDatasetName(item.dataset) }}</span>
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
      </v-data-table>
    </div>

    <div v-else class="no-projects">
      <div class="empty-state">
        <h4>No Projects Yet</h4>
        <p>You don't have any projects yet. Create one to get started!</p>
        <button class="btn btn-primary btn-create-empty" @click="$emit('create-project')">
          <font-awesome-icon icon="plus"></font-awesome-icon>
          <span>Create Your First Project</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
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
      tableHeaders: [
        { title: 'Name', value: 'name' },
        { title: 'Description', value: 'description' },
        { title: 'Status', value: 'status' },
        { title: 'Dataset', value: 'dataset' },
        { title: 'Actions', value: 'actions', sortable: false }
      ]
    }
  },
  methods: {
    handleRowClick(event, { item }) {
      // v-data-table click:row passes (event, { item })
      this.$emit('select-project', event, { item })
    },
    getStatusClass(status) {
      const classes = {
        'A': 'badge-primary',
        'C': 'badge-success',
        'D': 'badge-danger'
      }
      return classes[status] || 'badge-secondary'
    },
    getStatusText(status) {
      const texts = {
        'A': 'Annotating',
        'C': 'Complete',
        'D': 'Discontinued'
      }
      return texts[status] || status
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

// Component-specific styles
.project-list-section {
  background: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

  .section-header {
    padding-bottom: 12px;
    border-bottom: 1px solid var(--color-border);

    h3 {
      font-size: 1.3rem;
    }
  }

  .projects-table-container {
    overflow-x: auto;
  }

  .projects-table {
    :deep(.project-row) {
      cursor: pointer;
      transition: background-color 0.2s ease;

      &:hover {
        background-color: #f8f9fa;
      }
    }
  }

  .project-name-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .project-name {
    font-size: 0.95rem;
    color: var(--color-heading);
  }

  .project-description {
    font-size: 0.85rem;
    color: var(--color-text-secondary);
    opacity: 0.8;
  }

  .dataset-name {
    font-size: 0.9rem;
    color: var(--color-text);
  }

  .no-projects {
    padding: 60px 20px;
    text-align: center;
  }
}
</style>
