function downsample(input, fromRate, toRate = 16000) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const output = new Float32Array(Math.round(input.length / ratio));
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(input.length, Math.floor((index + 1) * ratio));
    let sum = 0;
    for (let sample = start; sample < end; sample += 1) sum += input[sample];
    output[index] = sum / Math.max(1, end - start);
  }
  return output;
}

export async function startPcmCapture(onFrame) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  source.connect(processor);
  processor.connect(context.destination);
  processor.onaudioprocess = (event) => {
    const mono = event.inputBuffer.getChannelData(0);
    onFrame(downsample(mono, context.sampleRate));
  };

  return () => {
    processor.onaudioprocess = null;
    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    void context.close();
  };
}

export async function scanJoinCode() {
  const module = await import("@capacitor-mlkit/barcode-scanning");
  const { BarcodeScanner } = module;
  const permission = await BarcodeScanner.requestPermissions();
  if (permission.camera !== "granted") throw new Error("未授予相机权限");
  const result = await BarcodeScanner.scan();
  const code = result.barcodes && result.barcodes[0];
  if (!code || !code.rawValue) throw new Error("未识别到连接二维码");
  return code.rawValue;
}
