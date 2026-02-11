<template>
  <div class="list-section">
    <div class="section-header">
      <h3>Users <span class="item-count">({{ users.length }})</span></h3>
    </div>
    <div v-if="users.length > 0" class="table-container">
      <v-data-table
        :items="users"
        :headers="headers"
        :hover="true"
        @click:row="handleRowClick"
        hide-default-footer
        :items-per-page="-1"
        class="admin-table"
        dense>
        <template #item.is_staff="{ item }">
          <span class="badge" :class="item.is_staff ? 'badge-success' : 'badge-secondary'">
            {{ item.is_staff ? 'Staff' : 'User' }}
          </span>
        </template>
        <template #item.is_superuser="{ item }">
          <span class="badge" :class="item.is_superuser ? 'badge-danger' : 'badge-secondary'">
            {{ item.is_superuser ? 'Admin' : 'Regular' }}
          </span>
        </template>
        <template #item.actions="{ item }">
          <div class="action-buttons" @click.stop>
            <!-- Row click opens edit form -->
          </div>
        </template>
      </v-data-table>
    </div>
    <div v-else class="empty-state">
      <h4>No Users</h4>
      <p>Add a user to get started.</p>
      <button class="btn btn-primary btn-create-empty" @click="$emit('add-user')">
        <font-awesome-icon icon="plus"></font-awesome-icon>
        <span>Add Your First User</span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'UsersList',
  props: {
    users: {
      type: Array,
      required: true
    }
  },
  emits: ['select-user', 'add-user'],
  data() {
    return {
      headers: [
        { title: 'Username', value: 'username' },
        { title: 'Email', value: 'email' },
        { title: 'Staff', value: 'is_staff' },
        { title: 'Admin', value: 'is_superuser' },
        { title: 'Actions', value: 'actions', sortable: false }
      ]
    }
  },
  methods: {
    handleRowClick(event, { item }) {
      // v-data-table click:row passes (event, { item })
      this.$emit('select-user', event, { item })
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';
</style>
