<template>
  <div class="form-section">
    <div class="form-header">
      <button class="btn btn-back" @click="$emit('close')">
        <font-awesome-icon icon="arrow-left"></font-awesome-icon>
        <span>Back</span>
      </button>
      <h3>{{ editing ? 'Edit Model Pack' : 'Add Model Pack' }}</h3>
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
              <label>Model Pack File *</label>
              <input type="file" @change="handleFileChange" accept=".zip" class="form-control file-input" :required="!editing" />
              <small class="form-text text-muted">Upload a .zip file containing the model pack</small>
            </div>
          </div>
          <div class="form-section form-section-horizontal">
            <div class="form-group">
              <label>Concept DB</label>
              <select v-model="formData.concept_db" class="form-control">
                <option :value="null">None</option>
                <option v-for="cdb in conceptDbs" :key="cdb.id" :value="cdb.id">{{ cdb.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>Vocabulary</label>
              <select v-model="formData.vocab" class="form-control">
                <option :value="null">None</option>
                <option v-for="vocab in vocabs" :key="vocab.id" :value="vocab.id">{{ vocab.name }}</option>
              </select>
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
  name: 'ModelPackForm',
  props: {
    editing: {
      type: Boolean,
      default: false
    },
    modelPack: {
      type: Object,
      default: null
    },
    conceptDbs: {
      type: Array,
      required: true
    },
    vocabs: {
      type: Array,
      required: true
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
        model_pack: null,
        concept_db: null,
        vocab: null
      }
    }
  },
  watch: {
    modelPack: {
      immediate: true,
      handler(newVal) {
        if (newVal) {
          this.formData = {
            name: newVal.name || '',
            model_pack: null,
            concept_db: newVal.concept_db || null,
            vocab: newVal.vocab || null
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
        this.formData.model_pack = file
      }
    },
    resetForm() {
      this.formData = {
        name: '',
        model_pack: null,
        concept_db: null,
        vocab: null
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

input[type="file"].form-control,
.file-input {
  padding: 8px;
  cursor: pointer;
  border: 1px solid #d0d0d0;
  border-radius: 8px;
  background: white;
  display: block;
  width: 100%;
  min-height: 38px;

  &:hover {
    border-color: #b0b0b0;
  }

  &::file-selector-button {
    padding: 6px 14px;
    margin-right: 12px;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    background: #f8f9fa;
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 0.85rem;
    display: inline-block;
    visibility: visible;
    opacity: 1;

    &:hover {
      background: #e9ecef;
      border-color: #b0b0b0;
    }
  }
}
</style>
