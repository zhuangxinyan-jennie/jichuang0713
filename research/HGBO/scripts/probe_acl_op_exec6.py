import textwrap, paramiko, json
script = textwrap.dedent(r'''
import json, acl
import numpy as np
IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(__import__("struct").pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))
acl.init(); acl.rt.set_device(0)
acl.op.set_model_dir("/home/HwHiAiUser/custom_opp/vendors/customize")
stream,_ = acl.rt.create_stream()
xd = acl.create_tensor_desc(1,[IH,IW,IC],2)
yd = acl.create_tensor_desc(1,[OH,OW,OC],2)
host_x = np.ones((IH,IW,IC), dtype=np.float16)
dev_x,_ = acl.rt.malloc(host_x.nbytes,0)
dev_y,_ = acl.rt.malloc(OH*OW*OC*2,0)
acl.rt.memcpy(dev_x, host_x.nbytes, host_x.ctypes.data, host_x.nbytes, 1)
xb = acl.create_data_buffer(dev_x, host_x.nbytes)
yb = acl.create_data_buffer(dev_y, OH*OW*OC*2)
out = {}
for opn in ["VideoPreFuseCustom", "video_pre_fuse_custom"]:
    try:
        h,r = acl.op.create_handle(opn, [xd], [yd], 0)
        out[opn+"_create"] = [int(h) if h else 0, int(r)]
        if h and int(r)==0:
            e = acl.op.execute(h, [xb], [yb], None, stream)
            acl.rt.synchronize_stream(stream)
            out[opn+"_exec"] = int(e)
            acl.op.destroy_handle(h)
    except Exception as ex:
        out[opn] = str(ex)
# try infer_shape
try:
    sh = acl.op.infer_shape("VideoPreFuseCustom", [xd], [yd], 0)
    out["infer_shape"] = str(sh)
except Exception as ex:
    out["infer_shape"] = str(ex)
print(json.dumps(out, indent=2))
acl.finalize()
''')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_acl6.py","w") as f: f.write(script.replace("\r\n","\n"))
sftp.close()
cmd = ("source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
       "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
       "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
       "python3 /tmp/probe_acl6.py 2>&1")
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=120)
print(stdout.read().decode())
