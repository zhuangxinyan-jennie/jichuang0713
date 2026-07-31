mergeInto(LibraryManager.library, {
  XiongdaNotifyNavArrived: function (payloadPtr) {
    var payload = UTF8ToString(payloadPtr);
    if (typeof window !== "undefined" && typeof window.xiongdaOnNavArrived === "function") {
      try {
        window.xiongdaOnNavArrived(payload);
      } catch (e) {
        console.error("[XiongdaNavCallback]", e);
      }
    }
  },
});
