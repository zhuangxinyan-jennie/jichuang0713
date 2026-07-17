import textwrap, paramiko
script = textwrap.dedent(r'''
import json, time, struct, traceback
import numpy as np
import acl

IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(struct.pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))

out = {}
try:
    acl.init()
    acl.rt.set_device(0)
    # try load custom opp
    if hasattr(acl.op, "load"):
        try:
            r = acl.op.load("/home/HwHiAiUser/custom_opp/vendors/customize")
            out["op_load"] = int(r)
        except Exception as e:
            out["op_load"] = str(e)
    if hasattr(acl.op, "set_model_dir"):
        try:
            r = acl.op.set_model_dir("/home/HwHiAiUser/custom_opp/vendors/customize")
            out["set_model_dir"] = int(r)
        except Exception as e:
            out["set_model_dir"] = str(e)

    stream,_ = acl.rt.create_stream()
    xd = acl.create_tensor_desc(1,[IH,IW,IC],2)
    yd = acl.create_tensor_desc(1,[OH,OW,OC],2)
    host_x = np.ones((IH,IW,IC), dtype=np.float16)
    dev_x,_ = acl.rt.malloc(host_x.nbytes,0)
    dev_y,_ = acl.rt.malloc(OH*OW*OC*2,0)
    acl.rt.memcpy(dev_x, host_x.nbytes, host_x.ctypes.data, host_x.nbytes, 1)
    xb = acl.create_data_buffer(dev_x, host_x.nbytes)
    yb = acl.create_data_buffer(dev_y, OH*OW*OC*2)

    # 4-arg attempts
    for name, args in [
        ("4a", ("VideoPreFuseCustom", [xd], [yd], 0)),
        ("3a", ("VideoPreFuseCustom", [xd], [yd])),
    ]:
        try:
            ret = acl.op.create_handle(*args)
            out[name+"_ret"] = str(ret)
            if isinstance(ret, tuple):
                h, code = ret
            else:
                h, code = ret, 0
            ex = acl.op.execute(h, [xb], [yb], None, stream)
            acl.rt.synchronize_stream(stream)
            out[name+"_exec"] = int(ex)
            acl.op.destroy_handle(h)
        except Exception as e:
            out[name] = str(e)

    acl.finalize()
except Exception:
    out["fatal"] = traceback.format_exc()[-1200:]
print(json.dumps(out, indent=2))
''')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_acl5.py","w") as f: f.write(script.replace("\r\n","\n"))
sftp.close()
cmd = ("source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
       "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
       "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
       "python3 /tmp/probe_acl5.py 2>&1")
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=300)
print(stdout.read().decode())
