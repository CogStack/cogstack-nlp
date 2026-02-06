<template>
  <div class="form-section">
    <div class="form-header">
      <button class="btn btn-back" @click="$emit('close')">
        <font-awesome-icon icon="arrow-left"></font-awesome-icon>
        <span>Back</span>
      </button>
      <h3>{{ editing ? 'Edit Dataset' : 'Add Dataset' }}</h3>
    </div>
    <div class="form-content">
      <form @submit.prevent="$emit('save', formData)" class="admin-form">
        <div class="form-sections-wrapper">
          <div class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Name *</label>
              <input v-model="formData.name" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Description</label>
              <textarea v-model="formData.description" class="form-control" rows="2"></textarea>
            </div>
          </div>
          <div class="form-section">
            <div class="form-group">
              <label>Original File *</label>
              <input type="file" @change="handleFileChange" accept=".csv,.xlsx" class="form-control file-input" :required="!editing" />
              <div class="schema-guide">
                <small class="form-text text-muted">
                  <strong>File Schema Requirements:</strong>
                </small>
                <ul class="schema-list">
                  <li><strong>Format:</strong> .csv or .xlsx file</li>
                  <li><strong>Required columns:</strong>
                    <ul>
                      <li><code>name</code> - A unique identifier for each document</li>
                      <li><code>text</code> - The free-text content to annotate</li>
                    </ul>
                  </li>
                  <li>Additional columns are allowed but will be ignored</li>
                </ul>
                <small class="form-text text-muted example-text">
                  <strong>Example CSV structure:</strong><br>
                  <code>name,text</code><br>
                  <code>doc001,"This is the first document to annotate."</code><br>
                  <code>doc002,"This is the second document with medical text."</code>
                </small>
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
  name: 'DatasetForm',
  props: {
    editing: {
      type: Boolean,
      default: false
    },
    dataset: {
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
        name: '',
        description: '',
        original_file: null
      }
    }
  },
  watch: {
    dataset: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.formData = {
            name: newVal.name || '',
            description: newVal.description || '',
            original_file: null
          }
        } else {
          this.resetForm()
        }
      }
    }
  },
  methods: {
    handleFileChange(event) {
      const file = event.target.files[0]
      if (file) {
        this.formData.original_file = file
      }
    },
    resetForm() {
      this.formData = {
        name: '',
        description: '',
        original_file: null
      }
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/admin.scss';

// Component-specific styles
.form-section {
  max-height: calc(100vh - 270px);
}

.admin-form {
  height: calc(100% - 70px);
}

.form-group {
  textarea.form-control {
    resize: vertical;
    min-height: 80px;
    font-family: inherit;
    line-height: 1.5;
    border-radius: 8px;
  }

  .schema-guide {
    margin-top: 12px;
    padding: 16px;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;

    .form-text {
      margin-top: 0;
      margin-bottom: 8px;
      font-weight: 500;
      opacity: 1;
      color: var(--color-heading);
    }

    .schema-list {
      margin: 8px 0 12px 0;
      padding-left: 20px;
      color: var(--color-text);
      font-size: 0.9rem;
      line-height: 1.6;

      li {
        margin-bottom: 6px;

        code {
          background: #e9ecef;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 0.85em;
          color: #d63384;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        ul {
          margin-top: 4px;
          margin-bottom: 4px;
          padding-left: 20px;
        }
      }
    }

    .example-text {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #e0e0e0;
      display: block;
      font-size: 0.85rem;
      line-height: 1.8;

      code {
        display: block;
        background: #f1f3f5;
        padding: 8px 12px;
        border-radius: 6px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 0.85em;
        color: #495057;
        margin-top: 4px;
        white-space: pre;
        overflow-x: auto;
      }
    }
  }
}
</style>
