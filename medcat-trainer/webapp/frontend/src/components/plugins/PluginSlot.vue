<template>
  <template v-for="(comp, index) in components" :key="`${name}-${index}`">
    <component :is="comp" v-bind="$attrs" />
  </template>
</template>

<script>
import { getSlotComponents } from '@/plugins/registry'

export default {
  name: 'PluginSlot',
  inheritAttrs: false,
  props: {
    name: {
      type: String,
      required: true
    }
  },
  computed: {
    components () {
      return getSlotComponents(this.name)
    }
  }
}
</script>
