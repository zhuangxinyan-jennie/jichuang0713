import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
cmds=[
 'find /home/HwHiAiUser/pre_on_board_tmp -name "*predictor*" 2>/dev/null',
 'grep -r predictor /home/HwHiAiUser/pre_on_board_tmp/board_deploy 2>/dev/null | head -15',
 'source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null; atc --model=/home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx --framework=5 --output=/tmp/stream_predictor_test --input_format=ND --soc_version=Ascend310B1 --input_shape="enc:1,16,512;enc_len:1" 2>&1 | tail -25',
]
for cmd in cmds:
 print('===',cmd[:80],'...' if len(cmd)>80 else '','===')
 out=c.exec_command(cmd,timeout=120)[1].read().decode(errors='replace')
 print(out[:4000])
c.close()
