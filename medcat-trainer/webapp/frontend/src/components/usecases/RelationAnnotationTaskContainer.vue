<template>
  <div @mousedown.stop class="relation-extraction-container">
    <div class="title title-padding">Relation Annotations
      <button class="btn btn-default add-rel-btn" @click="addNewRelation">
        <font-awesome-icon icon="plus"></font-awesome-icon>
      </button>
    </div>

    <div class="relation-list">
      <relation-annotation v-for="(rel, idx) of entityRelations" :key="idx" :entity-relation="rel"
                           :possible-relations="relations" :selected-ent="selectedEntity"
                           :selected-relation="currRelation" @click:clearRelation="removeRelation" @change:relationEdit="editRelation"
                           @click:selectRelation="selectedRelation(rel, idx)" @changed:relation="relationChanged"
      ></relation-annotation>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import RelationAnnotation from '@/components/usecases/RelationAnnotation.vue'

export default {
  name: 'RelationAnnotationTaskContainer',
  components: { RelationAnnotation },
  props: {
    selectedEntity: Object,
    availableRelations: Array,
    projectId: {
      required: true,
      type: Number
    },
    documentId: {
      required: true
    },
    currRelation: Object
  },
  emits: [
      'selected:relation'
  ],
  data () {
    return {
      relations: {},
      entityRelations: []
    }
  },
  created () {
    this.$http.get(`/api/relations/?id__in=${this.availableRelations}`).then(resp => {
      this.relations = resp.data.results.map(r => {
        return {
          name: r.label,
          id: r.id
        }
      })
      this.fetchEntityRelations()
    })
  },
  watch: {
    documentId () {
      this.fetchEntityRelations()
    }
  },
  methods: {
    fetchEntityRelations () {
      const url = `/api/entity-relations/?project=${this.projectId}&document=${this.documentId}`
      this.$http.get(url).then(resp => {
        this.entityRelations = resp.data.results
        const entIds = _.flatten(this.entityRelations.map(rel => {
          return [rel.start_entity, rel.end_entity]
        }))
        this.$http.get(`/api/annotated-entities/?id__in=${entIds.join(',')}`).then(resp => {
          for (const rel of this.entityRelations) {
            rel.start_entity = resp.data.results.filter(e => e.id === rel.start_entity)[0]
            rel.end_entity = resp.data.results.filter(e => e.id === rel.end_entity)[0]
            rel.relation = this.relations.filter(r => r.id === rel.relation)[0]
          }
        })
      })
    },
    addNewRelation () {
      this.entityRelations.push({
        user: Number(this.$cookies.get('user-id')),
        project: Number(this.projectId),
        document: Number(this.documentId),
        relation: this.relations[0],
        start_entity: {},
        end_entity: {},
        validated: false
      })
    },
    removeRelation (rel) {
      if (rel.id) {
        this.$http.delete(`/api/entity-relations/${rel.id}/`)
      }
      this.entityRelations.splice(this.entityRelations.indexOf(rel), 1)
    },
    editRelation (rel) {
      if (rel.start_entity.value && rel.end_entity.value && rel.relation) {
        rel.validated = true
        const payload = { ...rel }
        payload.start_entity = payload.start_entity.id
        payload.end_entity = payload.end_entity.id
        payload.relation = payload.relation.id
        if (rel.id) {
          this.$http.put(`/api/entity-relations/${rel.id}/`, payload)
        } else {
          this.$http.post(`/api/entity-relations/`, payload).then(resp => {
            rel.id = resp.data.id
          })
        }
      }
    },
    selectedRelation (rel) {
      this.$emit('selected:relation', rel)
    },
    relationChanged (rel, prop, val) {
      rel[prop] = val
      // this.$set(rel, prop, val)
      this.editRelation(rel)
    }
  }
}

</script>

<style scoped lang="scss">
.relation-extraction-container {
  max-height: 500px;
  overflow-y: auto;
}

.title-padding {
  padding: 5px 5px 5px 15px;
}

.add-rel-btn {
  float: right;
}

.relation-list {
  width: 100%;
  overflow-y: auto;
}
</style>
