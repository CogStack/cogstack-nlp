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
      <form @submit.prevent="handleSubmit" class="admin-form">
        <div class="form-sections-wrapper">
          <div class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Username *</label>
              <input
                v-model="formData.username"
                type="text"
                name="username"
                data-field="username"
                class="form-control"
                :class="{ 'is-invalid': validationErrors.username }"
                required
                @invalid="handleInvalid($event)"
                @input="clearValidationError('username')"
              />
              <small v-if="validationErrors.username" class="form-text text-danger">{{ validationErrors.username }}</small>
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
      },
      validationErrors: {}
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
        // Clear validation errors when user changes
        this.validationErrors = {}
      }
    },
    'formData.username'() {
      // Clear error when user starts typing
      if (this.validationErrors.username) {
        delete this.validationErrors.username
      }
    }
  },
  methods: {
    handleInvalid(event) {
      event.preventDefault()
      const field = event.target
      const fieldName = field.name || field.getAttribute('data-field')
      if (fieldName && this.validationErrors[fieldName]) {
        field.setCustomValidity(this.validationErrors[fieldName])
      }
    },
    clearValidationError(fieldName) {
      if (this.validationErrors[fieldName]) {
        delete this.validationErrors[fieldName]
        const field = this.$el?.querySelector(`[data-field="${fieldName}"], [name="${fieldName}"]`)
        if (field) {
          field.setCustomValidity('')
          field.classList.remove('is-invalid')
        }
      }
    },
    validateForm() {
      this.validationErrors = {}
      let isValid = true

      if (!this.formData.username || this.formData.username.trim() === '') {
        this.validationErrors.username = 'Username is required'
        isValid = false
      }

      // Set HTML5 validation messages
      if (!isValid) {
        this.$nextTick(() => {
          Object.keys(this.validationErrors).forEach(fieldName => {
            const field = this.$el?.querySelector(`[data-field="${fieldName}"], [name="${fieldName}"]`)
            if (field && this.validationErrors[fieldName]) {
              field.setCustomValidity(this.validationErrors[fieldName])
              field.classList.add('is-invalid')
            }
          })
        })
      }

      return isValid
    },
    handleSubmit() {
      if (this.validateForm()) {
        this.$emit('save', this.formData)
      } else {
        this.$toast?.error('Please fix the validation errors before saving')
      }
    },
    resetForm() {
      this.formData = {
        username: '',
        email: '',
        password: '',
        is_staff: false,
        is_superuser: false
      }
      this.validationErrors = {}
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


</style>
