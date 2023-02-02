<template lang="pug">
  .columns.is-vcentered
    b-rate(:custom-text="rateText" size="is-medium" :disabled="disabled" @change="rateProduct")
</template>

<script>
export default {
  props: {
    item: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      disabled: false,
    }
  },
  computed: {
    rateText() {
      return `Rate this product (Average rating: ${
        this.item.metadata.rating || 0
      })`
    },
  },
  methods: {
    rateProduct(rating) {
      this.disabled = true
      this.$axios
        .post(`/products/${this.item.id}/rate`, { rating })
        .then((r) => {
          this.$store.commit("product/SET_PRODUCTS", [r.data])
        })
    },
  },
}
</script>
