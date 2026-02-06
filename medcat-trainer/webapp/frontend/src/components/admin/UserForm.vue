<template>
  <div class="form-section">
    <div class="form-header">
      <button class="btn btn-back" @click="$emit('close')">
        <font-awesome-icon icon="arrow-left"></font-awesome-icon>
        <span>Back</span>
      </button>
      <h3>{{ editing ? 'Edit User' : 'Add User' }}</h3>
    </div>
    <div class="form-content">
      <form @submit.prevent="$emit('save', formData)" class="admin-form">
        <div class="form-sections-wrapper">
          <div class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Username *</label>
              <input v-model="formData.username" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Email</label>
              <input v-model="formData.email" type="email" class="form-control" />
            </div>
            <div v-if="!editing" class="form-group">
              <label>Password</label>
              <input v-model="formData.password" type="password" class="form-control" />
              <small class="form-text text-muted">Note: Password cannot be set via API. Users should set their password through password reset or Django admin.</small>
            </div>
          </div>
          <div class="form-section">
            <div class="checkbox-grid">
              <div class="form-group checkbox-group">
                <label class="checkbox-label">
                  <input v-model="formData.is_staff" type="checkbox" class="checkbox-input" />
                  <span class="checkbox-text">Staff</span>
                </label>
              </div>
              <div class="form-group checkbox-group">
                <label class="checkbox-label">
                  <input v-model="formData.is_superuser" type="checkbox" class="checkbox-input" />
                  <span class="checkbox-text">Superuser (Admin)</span>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-secondary" @click="$emit('close')">Cancel</button>
          <button type="submit" class="btn btn-primary" :disabled="saving">
            <font-awesome-icon v-if="saving" icon="spinner" spin></font-awesome-icon>
            <span>{{ saving ? 'Saving...' : 'Save' }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
export default {
  name: 'UserForm',
  props: {
    editing: {
      type: Boolean,
      default: false
    },
    user: {
      type: Object,
      default: null
    },
    saving: {
      type: Boolean,
      default: false
    }
  },
  emits: ['close', 'save'],
  data() {
    return {
      formData: {
        username: '',
        email: '',
        password: '',
        is_staff: false,
        is_superuser: false
      }
    }
  },
  watch: {
    user: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.formData = {
            username: newVal.username || '',
            email: newVal.email || '',
            password: '',
            is_staff: newVal.is_staff || false,
            is_superuser: newVal.is_superuser || false
          }
        } else {
          this.resetForm()
        }
      }
    }
  },
  methods: {
    resetForm() {
      this.formData = {
        username: '',
        email: '',
        password: '',
        is_staff: false,
        is_superuser: false
      }
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';

// Component-specific overrides
.form-section {
  max-height: calc(100vh - 270px);
}

.admin-form {
  height: calc(100% - 70px);
}

</style>
