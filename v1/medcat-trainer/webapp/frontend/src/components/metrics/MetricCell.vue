<template>
  <div class="perf-progress">
    <v-progress-linear
        :model-value="value"
        :color="color"
        :background-color="backgroundColor"
        :height="height"
        :max="1.0">
      <span :class="{'good-perf': value > threshold}">
        {{ value.toFixed(decimals) }}
      </span>
    </v-progress-linear>
  </div>
</template>

<script>
export default {
  name: 'MetricCell',
  props: {
    value: {
      type: Number,
      required: true
    },
    color: {
      type: String,
      default: '#32AB60'
    },
    backgroundColor: {
      type: String,
      default: '#46B480'
    },
    height: {
      type: [String, Number],
      default: '30px'
    },
    threshold: {
      type: Number,
      default: 0.4
    },
    decimals: {
      type: Number,
      default: 2
    }
  }
}
</script>

<style scoped>
.perf-progress {
  width: 100%;
}

.good-perf {
  color: #E5EBEA;
}
</style>