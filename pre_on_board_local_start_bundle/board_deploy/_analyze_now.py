import paramiko, re, statistics, json
from datetime import datetime
from pathlib import Path

log = Path(r"c:\Users\Aa230\.cursor\projects\c-Users-Aa230-OneDrive-Desktop-HGBO-DSE-main\terminals\29.txt").read_text(encoding='utf-8', errors='replace')
PARTIAL = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*识别中>\s*(.+)")
FINAL = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*整句>>\s*(.+)")

def ts(s):
    h,m,sec=map(int,s.split(':'))
    return h*3600+m*60+sec

events=[]
for line in log.splitlines():
    m=PARTIAL.search(line)
    if m: events.append(('p', ts(m.group(1)), m.group(2).strip()))
    m=FINAL.search(line)
    if m: events.append(('f', ts(m.group(1)), m.group(2).strip()))

# Estimate sub-second timing: assign 200ms slots within same second for successive partials
BLOCK_MS=200
partial_gaps=[]
final_gaps=[]
utt_gaps=[]
last_p_t=None; last_p_text=''; last_f_t=None; idx_in_sec=0; cur_sec=None
for kind,t,text in events:
    if kind=='p':
        if cur_sec!=t: cur_sec=t; idx_in_sec=0
        est_t=t+idx_in_sec*BLOCK_MS/1000.0
        idx_in_sec+=1
        if last_p_t is not None and text!=last_p_text:
            partial_gaps.append((est_t-last_p_t)*1000)
        last_p_t=est_t; last_p_text=text
    else:
        if last_p_t is not None:
            final_gaps.append((t-last_p_t)*1000)
        if last_f_t is not None:
            utt_gaps.append((t-last_f_t)*1000)
        last_f_t=t; last_p_t=None; last_p_text=''

def summ(v):
    if not v: return {"count":0}
    v=sorted(v)
    return {"count":len(v),"avg_ms":round(statistics.fmean(v),1),"p50_ms":round(v[len(v)//2],1),"p95_ms":round(v[int(len(v)*0.95)],1)}

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
cmd=r"""bash -lc 'ASR=$(pgrep -f board_audio_receiver.py|head -1); VID=$(pgrep -f run_board_runtime.py|head -1); echo ASR_PID=$ASR VID_PID=$VID; ps -p $ASR -o pid,pcpu,pmem,rss,cmd 2>/dev/null; ps -p $VID -o pid,pcpu,pmem,rss 2>/dev/null; npu-smi info | head -12; free -h | head -2'"""
_,o,_=c.exec_command(cmd,timeout=25)
res=o.read().decode(errors='replace')
c.close()

report={
  "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  "backend":"ctc",
  "latency_estimated_ms":{
    "partial_update": summ(partial_gaps),
    "partial_to_final": summ(final_gaps),
    "utterance_gap": summ(utt_gaps),
  },
  "counts":{"partial":sum(1 for k,_,_ in events if k=='p'),"final":sum(1 for k,_,_ in events if k=='f')},
  "board_resources": res,
}
out=Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\logs\asr_ctc_benchmark.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
