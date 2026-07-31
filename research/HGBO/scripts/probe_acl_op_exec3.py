"""Brute-force acl.op.create_handle 7-arg signature."""
import textwrap, paramiko

script = textwrap.dedent(r'''
import json, traceback
import numpy as np
import acl

IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(__import__("struct").pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))

acl.init(); acl.rt.set_device(0)
stream,_ = acl.rt.create_stream()
xd = acl.create_tensor_desc(1,[IH,IW,IC],2)
yd = acl.create_tensor_desc(1,[OH,OW,OC],2)
host_x = np.ones((IH,IW,IC), dtype=np.float16)
dev_x,_ = acl.rt.malloc(host_x.nbytes,0)
dev_y,_ = acl.rt.malloc(OH*OW*OC*2,0)
acl.rt.memcpy(dev_x, host_x.nbytes, host_x.ctypes.data, host_x.nbytes, 1)
xb = acl.create_data_buffer(dev_x, host_x.nbytes)
yb = acl.create_data_buffer(dev_y, OH*OW*OC*2)

attempts = []
# common 7-arg patterns for acl op api
candidates = [
    ("VideoPreFuseCustom", 1, 1, [xd], [yd], 0, None),
    ("VideoPreFuseCustom", [xd], [yd], 0, None, 0, 0),
    ("VideoPreFuseCustom", [xb], [yb], 0, None, 0, 0),
]
for i,c in enumerate(candidates):
    try:
        h,r = acl.op.create_handle(*c)
        e = acl.op.execute(h, [xb], [yb], None, stream)
        acl.rt.synchronize_stream(stream)
        attempts.append({"i":i,"create":int(r),"exec":int(e),"ok":True})
        acl.op.destroy_handle(h)
    except Exception as ex:
        attempts.append({"i":i,"err":str(ex)})

# try execute_v2
try:
    h,r = acl.op.create_handle("VideoPreFuseCustom", 1, 1, [xd], [yd], 0, None)
    e = acl.op.execute_v2(h, [xb], [yb], stream)
    acl.rt.synchronize_stream(stream)
    attempts.append({"execute_v2": int(e), "create": int(r)})
    acl.op.destroy_handle(h)
except Exception as ex:
    attempts.append({"execute_v2_err": str(ex)})

acl.finalize()
print(json.dumps(attempts, indent=2))
''')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_acl3.py","w") as f: f.write(script.replace("\r\n","\n"))
sftp.close()
cmd = ("source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
       "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
       "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
       "python3 /tmp/probe_acl3.py 2>&1")
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=300)
print(stdout.read().decode())
