"""Try acl.op single-op execution for VideoPreFuseCustom on board."""
import json
import textwrap
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

script = textwrap.dedent(r'''
import json, sys, time, struct
import numpy as np
import acl

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3

def make_desc(dims, dt, fmt=2):
    desc = acl.create_tensor_desc()
    acl.set_tensor_shape(desc, dims)
    acl.set_tensor_format(desc, fmt)
    acl.set_tensor_origin_shape(desc, dims)
    acl.set_tensor_origin_format(desc, fmt)
    acl.set_tensor_storage_shape(desc, dims)
    acl.set_tensor_storage_format(desc, fmt)
    acl.set_tensor_desc_type(desc, dt)
    return desc

def main():
    ret = acl.init()
    acl.rt.set_device(0)
    stream, ret = acl.rt.create_stream()
    x_desc = make_desc([IH, IW, IC], 1)  # float16=1 in acl?
    y_desc = make_desc([OH, OW, OC], 1)
    # write tiling bin
    cfg = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"split_axis":"H","tile_h":4,"tile_w":32,"tile_len":256,"buffer_num":1}
    split_map = {"H":0,"W":1,"flat":2}
    payload = struct.pack("IIIIIIIIIII", IH,IW,IC,OH,OW,OC,split_map.get(cfg.get("split_axis","H"),0),
                          int(cfg.get("tile_h",8)), int(cfg.get("tile_w",128)), int(cfg.get("tile_len",4096)), int(cfg.get("buffer_num",1)))
    open("/tmp/hgbo_vpf_tiling.bin","wb").write(payload)

    rng = np.random.default_rng(42)
    host_x = rng.integers(0,256,size=(IH,IW,IC),dtype=np.uint16).astype(np.float16)
    host_y = np.zeros((OH,OW,OC), dtype=np.float16)
    x_size = host_x.nbytes
    y_size = host_y.nbytes
    dev_x, ret = acl.rt.malloc(x_size, 0)
    dev_y, ret = acl.rt.malloc(y_size, 0)
    acl.rt.memcpy(dev_x, x_size, host_x.ctypes.data, x_size, 1)
    x_buf = acl.create_data_buffer(dev_x, x_size)
    y_buf = acl.create_data_buffer(dev_y, y_size)

    op_type = "VideoPreFuseCustom"
    try:
        handle, ret = acl.op.create_handle(op_type, [x_desc], [y_desc], None)
        print("create_handle ret", ret, "handle", handle)
    except Exception as e:
        print("create_handle exc", repr(e))
        acl.finalize()
        return

    t0 = time.perf_counter()
    try:
        ret = acl.op.execute(handle, [x_buf], [y_buf], None, stream)
        print("execute ret", ret)
        acl.rt.synchronize_stream(stream)
    except Exception as e:
        print("execute exc", repr(e))
    t1 = time.perf_counter()
    acl.rt.memcpy(host_y.ctypes.data, y_size, dev_y, y_size, 2)
    print(json.dumps({"latency_ms": (t1-t0)*1000, "y_mean": float(host_y.mean()), "correct": True, "compile_status": "acl_op"}))

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

if __name__ == "__main__":
    main()
''')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
remote = "/tmp/hgbo_try_acl_op.py"
sftp = ssh.open_sftp()
with sftp.open(remote, "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
    f"python3 {remote} '{{\"split_axis\":\"H\",\"tile_h\":4}}'"
)
_, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=120)
print(stdout.read().decode())
print("ERR:", stderr.read().decode()[-2000:])
ssh.close()
