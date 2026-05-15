<template>
  <div class="list-section">
    <div v-if="projects.length > 0" class="table-container">
      <v-data-table
        :items="projects"
        :headers="tableHeaders"
        :hover="true"
        @click:row="handleRowClick"
        hide-default-footer
        :items-per-page="-1"
        class="admin-table"
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
          <span>{{ getDatasetName(item.dataset) }}</span>
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

.list-section {
  .admin-table {
    :deep(tbody tr) {
      cursor: pointer;
    }
  }

  .project-name {
    font-size: 0.95rem;
    color: var(--color-heading);
  }
}
</style>
