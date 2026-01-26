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
          </div>
          <div v-if="!editing" class="form-section">
            <div class="form-group">
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
@import '@/styles/variables.scss';

.form-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 200px);
  min-height: auto;
}

.form-header {
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(135deg, $primary 0%, darken($primary, 10%) 100%);
  color: white;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  border-radius: 12px 12px 0 0;

  .btn-back {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: white;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(255, 255, 255, 0.3);
    }
  }

  h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }
}

.form-content {
  flex: 1;
  overflow: hidden;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}

.admin-form {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;

  .form-sections-wrapper {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    min-height: 0;
    padding: 20px;
    background: #f8f9fa;
  }

  .form-actions {
    margin-top: auto;
    flex-shrink: 0;
    padding: 20px;
    border-top: 1px solid var(--color-border);
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    background: var(--color-background-light);
  }
}

.form-section {
  margin-bottom: 24px;
  padding: 20px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  flex-shrink: 0;

  h4 {
    margin-bottom: 16px;
    margin-top: 0;
    color: var(--color-heading);
    font-size: 1.05rem;
    font-weight: 600;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f0f0;
  }

  &.form-section-horizontal {
    .form-row {
      display: flex;
      gap: 20px;
      align-items: flex-end;
      flex-wrap: wrap;
    }
  }
}

.form-group {
  margin-bottom: 16px;
  flex: 1;
  min-width: 200px;

  label {
    display: block;
    margin-bottom: 6px;
    font-weight: 500;
    color: var(--color-heading);
    font-size: 0.9rem;
  }

  .form-control {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #d0d0d0;
    border-radius: 8px;
    font-size: 0.9rem;
    transition: all 0.2s ease;
    background: white;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02);

    &:hover {
      border-color: #b0b0b0;
    }

    &:focus {
      outline: none;
      border-color: $primary;
      box-shadow: 0 0 0 3px rgba(0, 114, 206, 0.1), inset 0 1px 2px rgba(0, 0, 0, 0.02);
    }
  }

  .form-text {
    display: block;
    margin-top: 6px;
    font-size: 0.85rem;
    color: var(--color-text);
    opacity: 0.7;
  }
}

.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 8px;
}

.checkbox-group {
  margin-bottom: 12px;

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    padding: 8px 0;
    transition: all 0.2s ease;
    margin-bottom: 0;
    min-height: 36px;

    &:hover {
      opacity: 0.8;
    }

    .checkbox-input {
      margin: 0;
      width: 18px;
      height: 18px;
      cursor: pointer;
      accent-color: $primary;
      flex-shrink: 0;
      border: 1px solid #d0d0d0;
      border-radius: 3px;
    }

    .checkbox-text {
      flex: 1;
      font-weight: 400;
      color: var(--color-text);
      font-size: 0.9rem;
      line-height: 1.4;
    }
  }
}
</style>
