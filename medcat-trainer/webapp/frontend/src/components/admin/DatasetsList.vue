<template>
  <div class="list-section">
    <div class="section-header">
      <h3>Datasets <span class="item-count">({{ datasets.length }})</span></h3>
    </div>
    <div v-if="datasets.length > 0" class="table-container">
      <v-data-table
        :items="datasets"
        :headers="headers"
        :hover="true"
        @click:row="handleRowClick"
        hide-default-footer
        :items-per-page="-1"
        class="admin-table"
        dense>
        <template #item.actions="{ item }">
          <div class="action-buttons" @click.stop>
            <button
              class="btn btn-sm btn-action btn-delete"
              @click="$emit('confirm-delete-dataset', item)"
              :title="'Delete ' + item.name">
              <font-awesome-icon icon="trash"></font-awesome-icon>
            </button>
          </div>
        </template>
      </v-data-table>
    </div>
    <div v-else class="empty-state">
      <h4>No Datasets</h4>
      <p>Add a dataset to get started.</p>
      <button class="btn btn-primary btn-create-empty" @click="$emit('add-dataset')">
        <font-awesome-icon icon="plus"></font-awesome-icon>
        <span>Add Your First Dataset</span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DatasetsList',
  props: {
    datasets: {
      type: Array,
      required: true
    }
  },
  emits: ['select-dataset', 'confirm-delete-dataset', 'add-dataset'],
  data() {
    return {
      headers: [
        { title: 'Name', value: 'name' },
        { title: 'Description', value: 'description' },
        { title: 'Actions', value: 'actions', sortable: false }
      ]
    }
  },
  methods: {
    handleRowClick(event, { item }) {
      // v-data-table click:row passes (event, { item })
      this.$emit('select-dataset', event, { item })
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';
</style>
