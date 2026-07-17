"""Test acl.op single-op execution for VideoPreFuseCustom."""
import textwrap
import paramiko

script = textwrap.dedent(r'''
import json, time, struct, traceback
import numpy as np
import acl

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3
FP16, ND = 1, 2
H2D, D2H = 1, 2

def write_tiling():
    payload = struct.pack("IIIIIIIIIII", IH,IW,IC,OH,OW,OC, 0,4,32,256,1)
    open("/tmp/hgbo_vpf_tiling.bin","wb").write(payload)

def main():
    write_tiling()
    out = {}
    try:
        acl.init()
        acl.rt.set_device(0)
        stream, _ = acl.rt.create_stream()

        x_desc = acl.create_tensor_desc(FP16, [IH, IW, IC], ND)
        y_desc = acl.create_tensor_desc(FP16, [OH, OW, OC], ND)

        host_x = np.random.randint(0, 256, (IH, IW, IC), dtype=np.uint16).astype(np.float16)
        host_y = np.zeros((OH, OW, OC), dtype=np.float16)
        x_bytes, y_bytes = host_x.nbytes, host_y.nbytes

        dev_x, _ = acl.rt.malloc(x_bytes, 0)
        dev_y, _ = acl.rt.malloc(y_bytes, 0)
        acl.rt.memcpy(dev_x, x_bytes, host_x.ctypes.data, x_bytes, H2D)

        x_buf = acl.create_data_buffer(dev_x, x_bytes)
        y_buf = acl.create_data_buffer(dev_y, y_bytes)

        handle, ret = acl.op.create_handle("VideoPreFuseCustom", [x_desc], [y_desc], None)
        out["create_handle_ret"] = int(ret)
        out["handle"] = str(handle)

        t0 = time.perf_counter()
        ret = acl.op.execute(handle, [x_buf], [y_buf], None, stream)
        acl.rt.synchronize_stream(stream)
        t1 = time.perf_counter()
        out["execute_ret"] = int(ret)
        out["latency_ms"] = (t1 - t0) * 1000

        acl.rt.memcpy(host_y.ctypes.data, y_bytes, dev_y, y_bytes, D2H)
        out["y_mean"] = float(host_y.mean())
        out["y_max"] = float(host_y.max())

        acl.op.destroy_handle(handle)
        acl.destroy_data_buffer(x_buf)
        acl.destroy_data_buffer(y_buf)
        acl.rt.free(dev_x)
        acl.rt.free(dev_y)
        acl.destroy_tensor_desc(x_desc)
        acl.destroy_tensor_desc(y_desc)
        acl.rt.destroy_stream(stream)
        acl.rt.reset_device(0)
        acl.finalize()
        out["status"] = "ok"
    except Exception:
        out["status"] = "fail"
        out["trace"] = traceback.format_exc()[-1500:]
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
''')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_acl_op_exec.py", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
    "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
    "python3 /tmp/probe_acl_op_exec.py 2>&1"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=300)
print(stdout.read().decode())
ssh.close()
