"""Test acl.op with attr count 0."""
import textwrap, paramiko

script = textwrap.dedent(r'''
import json, time, struct, traceback
import numpy as np
import acl

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3

write_tiling = lambda: open("/tmp/hgbo_vpf_tiling.bin","wb").write(
    struct.pack("IIIIIIIIIII", IH,IW,IC,OH,OW,OC, 0,4,32,256,1))

out = {}
try:
    write_tiling()
    acl.init()
    acl.rt.set_device(0)
    stream, _ = acl.rt.create_stream()
    x_desc = acl.create_tensor_desc(1, [IH,IW,IC], 2)
    y_desc = acl.create_tensor_desc(1, [OH,OW,OC], 2)
    host_x = np.random.randint(0,256,(IH,IW,IC),dtype=np.uint16).astype(np.float16)
    host_y = np.zeros((OH,OW,OC), dtype=np.float16)
    dev_x,_ = acl.rt.malloc(host_x.nbytes, 0)
    dev_y,_ = acl.rt.malloc(host_y.nbytes, 0)
    acl.rt.memcpy(dev_x, host_x.nbytes, host_x.ctypes.data, host_x.nbytes, 1)
    x_buf = acl.create_data_buffer(dev_x, host_x.nbytes)
    y_buf = acl.create_data_buffer(dev_y, host_y.nbytes)

    for variant in ["v0", "v1", "v2"]:
        try:
            if variant == "v0":
                handle, ret = acl.op.create_handle("VideoPreFuseCustom", [x_desc], [y_desc], 0)
            elif variant == "v1":
                handle, ret = acl.op.create_handle("VideoPreFuseCustom", 1, 1, 0)
            else:
                handle, ret = acl.op.create_handle("VideoPreFuseCustom", x_desc, y_desc, 0)
            ex = acl.op.execute(handle, [x_buf], [y_buf], None, stream)
            acl.rt.synchronize_stream(stream)
            out[variant] = {"create": int(ret), "exec": int(ex), "handle": str(handle)}
            acl.op.destroy_handle(handle)
        except Exception as e:
            out[variant] = str(e)

    acl.rt.memcpy(host_y.ctypes.data, host_y.nbytes, dev_y, host_y.nbytes, 2)
    out["y_mean"] = float(host_y.mean())
    acl.destroy_data_buffer(x_buf)
    acl.destroy_data_buffer(y_buf)
    acl.rt.free(dev_x); acl.rt.free(dev_y)
    acl.destroy_tensor_desc(x_desc); acl.destroy_tensor_desc(y_desc)
    acl.rt.destroy_stream(stream); acl.rt.reset_device(0); acl.finalize()
except Exception:
    out["fatal"] = traceback.format_exc()[-1200:]
print(json.dumps(out, indent=2))
''')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_acl2.py","w") as f: f.write(script.replace("\r\n","\n"))
sftp.close()
cmd = ("source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
       "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
       "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
       "python3 /tmp/probe_acl2.py 2>&1")
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=300)
print(stdout.read().decode())
