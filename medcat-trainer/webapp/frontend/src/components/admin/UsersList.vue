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
        @click:row="$emit('select-user', $event)"
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
            <button class="btn btn-sm btn-action btn-edit" @click="$emit('edit-user', item)" title="Edit">
              <font-awesome-icon icon="edit"></font-awesome-icon>
            </button>
          </div>
        </template>
      </v-data-table>
    </div>
    <div v-else class="empty-state">
      <h4>No Users</h4>
      <p>Add a user to get started.</p>
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
  emits: ['select-user', 'edit-user'],
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
  }
}
</script>

<style scoped lang="scss">
.list-section {
  .section-header {
    margin-bottom: 20px;

    h3 {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--color-heading);
      margin: 0;
    }

    .item-count {
      font-weight: 400;
      color: var(--color-text-secondary);
      font-size: 1rem;
    }
  }

  .table-container {
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    overflow: hidden;
  }

  .action-buttons {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
  }

  .btn-action {
    padding: 4px 8px;
    border: none;
    background: transparent;
    cursor: pointer;
    transition: all 0.2s ease;
    border-radius: 4px;

    &:hover {
      background: rgba(0, 0, 0, 0.05);
    }

    &.btn-edit {
      color: #0d6efd;
    }
  }

  .empty-state {
    text-align: center;
    padding: 60px 20px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);

    h4 {
      font-size: 1.25rem;
      color: var(--color-heading);
      margin-bottom: 8px;
    }

    p {
      color: var(--color-text-secondary);
      margin-bottom: 20px;
    }
  }
}
</style>
