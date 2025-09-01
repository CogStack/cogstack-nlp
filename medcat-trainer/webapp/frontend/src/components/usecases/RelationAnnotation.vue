<template>
  <div @click.stop.prevent @click="highlightRelation" :class="{'selected-rel': isSelected}" class="relation-annotation">
    <div class="entity" :class="startEntClass"
         @click="selectStartEnt">{{(entityRelation.start_entity.value || '_________')}}</div>
    <div class="relation">
      <select @change="relChange" v-model="relChoice">
        <option :value="rel" v-for="rel of possibleRelations" :key="rel.id">{{rel.name}}</option>
      </select>
    </div>
    <div class="entity" :class="endEntClass" @click="selectEndEnt">{{(entityRelation.end_entity.value || '_________')}}</div>
    <button class="btn btn-default clear-btn" @click="clear">
      <font-awesome-icon icon="times"></font-awesome-icon>
    </button>
  </div>
</template>

<script>
import _ from 'lodash'

export default {
  name: 'RelationAnnotation',
  props: {
    entityRelation: Object,
    possibleRelations: Array,
    selectedEnt: Object,
    selectedRelation: Object
  },
  emits: [
    'click:clearRelation',
    'click:selectRelation',
    'changed:relation'
  ],
  data () {
    return {
      relChoice: Object
    }
  },
  created () {
    this.relChoice = _.find(this.possibleRelations, v => v.id === this.entityRelation.relation) ||
      this.possibleRelations[0]
  },
  computed: {
    startEnt () {
      return this.entityRelation.start_entity
    },
    startEntClass () {
      return this.entRelClass(this.entityRelation.start_entity)
    },
    endEnt () {
      return this.entityRelation.end_entity
    },
    endEntClass () {
      return this.entRelClass(this.entityRelation.end_entity)
    },
    relation () {
      return this.entityRelation.relation
    },
    isSelected () {
      return this.selectedRelation === this.entityRelation
    }
  },
  methods: {
    clear () {
      this.$emit('click:clearRelation', this.entityRelation)
    },
    selectStartEnt () {
      this.$emit('changed:relation', this.entityRelation, 'start_entity', this.selectedEnt)
      // this.startRelClass = this.entRelClass(this.selectedEnt)
    },
    selectEndEnt () {
      this.$emit('changed:relation', this.entityRelation, 'end_entity', this.selectedEnt)
      // this.endRelClass = this.entRelClass(this.selectedEnt)
    },
    entRelClass (selectedEnt) {
      if (selectedEnt.correct) {
        return 'highlight-task-0'
      } else if (selectedEnt.deleted) {
        return 'highlight-task-1'
      } else if (selectedEnt.killed) {
        return 'highlight-task-2'
      } else if (selectedEnt.alternative) {
        return 'highlight-task-3'
      } else {
        return 'entity-default'
      }
    },
    highlightRelation () {
      this.$emit('click:selectRelation')
    },
    relChange () {
      this.$emit('changed:relation', this.entityRelation, 'relation', this.relChoice)
    }
  }
}
</script>

<style scoped lang="scss">
.relation-annotation {
  text-align: left;
  margin: 5px;
}

.entity {
  display: inline-block;
  border-radius: 3px;
  cursor: pointer;
  margin: 5px;
  padding: 2px;
}

.entity-default {
  background: lightgrey;
  border: 1px solid lightgrey;
}

.entity-default-selected {
  @extend .entity-default;
  font-weight: bold;
}

.relation {
  display: inline-block;
  font-weight: bold;

  select {
    border: 0;
    border-bottom: 1px solid #45503B;
    padding: 2px;
  }
}

.selected-rel {
  box-shadow: 0 0 5px 3px rgba(0, 0, 0, 0.2)
}

.clear-btn {
  float: right;
  cursor: pointer;
  opacity: 0.5;
  &:hover {
    opacity: 1;
  }
}
</style>
