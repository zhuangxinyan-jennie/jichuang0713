<script>
export default {
  onLaunch() {
    const saved = uni.getStorageSync("pc_host");
    if (!saved) {
      uni.setStorageSync("pc_host", "192.168.137.100");
    }
  },
};
</script>

<style>
page {
  background: #0a0a0a;
  color: #e8e8e8;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Microsoft YaHei", sans-serif;
}
</style>
