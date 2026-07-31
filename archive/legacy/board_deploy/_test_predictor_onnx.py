import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
cmd='/usr/local/miniconda3/bin/python3 -c "import onnxruntime as ort; s=ort.InferenceSession(\'/home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx\', providers=[\'CPUExecutionProvider\']); print([i.name for i in s.get_inputs()]); print([o.name for o in s.get_outputs()])"'
print(c.exec_command(cmd,timeout=30)[1].read().decode(errors='replace'))
c.close()
