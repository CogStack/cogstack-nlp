<template>
  <div class="list-section">
    <div class="section-header">
      <h3>Model Packs <span class="item-count">({{ modelPacks.length }})</span></h3>
    </div>
    <div v-if="modelPacks.length > 0" class="table-container">
      <v-data-table
        :items="modelPacks"
        :headers="headers"
        :hover="true"
        @click:row="handleRowClick"
        hide-default-footer
        :items-per-page="-1"
        class="admin-table"
        dense>
        <template #item.concept_db="{ item }">
          <span>{{ getConceptDbName(item.concept_db) }}</span>
        </template>
        <template #item.vocab="{ item }">
          <span>{{ getVocabName(item.vocab) }}</span>
        </template>
        <template #item.actions="{ item }">
          <div class="action-buttons" @click.stop>
            <button class="btn btn-sm btn-action btn-delete" @click="$emit('confirm-delete-model-pack', item)" title="Delete">
              <font-awesome-icon icon="trash"></font-awesome-icon>
            </button>
          </div>
        </template>
      </v-data-table>
    </div>
    <div v-else class="empty-state">
      <h4>No Model Packs</h4>
      <p>Add a model pack to get started.</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ModelPacksList',
  props: {
    modelPacks: {
      type: Array,
      required: true
    },
    conceptDbs: {
      type: Array,
      required: true
    },
    vocabs: {
      type: Array,
      required: true
    }
  },
  emits: ['select-model-pack', 'confirm-delete-model-pack'],
  data() {
    return {
      headers: [
        { title: 'Name', value: 'name' },
        { title: 'Concept DB', value: 'concept_db' },
        { title: 'Vocabulary', value: 'vocab' },
        { title: 'Actions', value: 'actions', sortable: false }
      ]
    }
  },
  methods: {
    handleRowClick(event, { item }) {
      // v-data-table click:row passes (event, { item })
      this.$emit('select-model-pack', event, { item })
    },
    getConceptDbName(conceptDbId) {
      if (!conceptDbId) return 'N/A'
      const cdb = this.conceptDbs.find(c => c.id === (typeof conceptDbId === 'object' ? conceptDbId.id : conceptDbId))
      return cdb ? cdb.name : 'N/A'
    },
    getVocabName(vocabId) {
      if (!vocabId) return 'N/A'
      const vocab = this.vocabs.find(v => v.id === (typeof vocabId === 'object' ? vocabId.id : vocabId))
      return vocab ? vocab.name : 'N/A'
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

    &.btn-delete {
      color: #dc3545;
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
