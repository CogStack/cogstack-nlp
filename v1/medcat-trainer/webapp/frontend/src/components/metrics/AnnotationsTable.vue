<template>
  <v-data-table :items="items"
                :headers="headers"
                :hover="true"
                hide-default-footer
                :items-per-page="-1">
    <template #item.status="{ item }">
      <div id="status" :class="textColorClass(item.status)">
        {{ item.status }}
        <font-awesome-icon
          icon="check-circle"
          v-if="['Correct', 'Manually Added', 'Alternative'].includes(item.status)">
        </font-awesome-icon>
        <font-awesome-icon
          icon="times-circle"
          v-if="['Incorrect', 'Terminated', 'Irrelevant'].includes(item.status)">
        </font-awesome-icon>
      </div>
    </template>
  </v-data-table>
</template>

<script>
export default {
  name: 'AnnotationsTable',
  props: {
    items: {
      type: Array,
      required: true
    },
  },
  data () {
    return {
      headers: [
          { value: 'project', title: 'Project'},
          { value: 'document_name', title: 'Doc. Name' },
          { value: 'id', title: 'Annotation Id' },
          { value: 'user', title: 'User' },
          { value: 'cui', title: 'CUI' },
          { value: 'concept_name', title: 'Concept' },
          { value: 'value', title: 'text' },
          { value: 'status', title: 'Status' }
      ]
    }
  },
  methods: {
    textColorClass(status) {
      return {
        'task-color-text-0': status === 'Correct' || status === 'Manually Added',
        'task-color-text-1': status === 'Incorrect',
        'task-color-text-2': status === 'Terminated',
        'task-color-text-3': status === 'Alternative',
        'task-color-text-4': status === 'Irrelevant'
      }
    },
  }
}
</script>

<style scoped>

</style>