"""Process-local case-level execution telemetry."""
import time
from collections import Counter
STATE={"counters":Counter(),"events":[],"cases":{},"current_case":None}
def reset(): STATE["counters"]=Counter(); STATE["events"]=[]; STATE["cases"]={}; STATE["current_case"]=None
def begin_case(case_id,question,answer):
    STATE["current_case"]=case_id
    STATE["cases"][case_id]={"case_id":case_id,"question":question,"generated_answer":answer,"retrieval_used":False,"retrieved_documents":[],"retrieval_score":0.0,"embedding_used":False,"faiss_used":False,"faiss_hits":0,"nli_used":False,"nli_label":"","nli_score":0.0,"rule_checker_used":False,"rule_flags":[],"self_consistency_used":False,"agreement_score":0.0,"predicted_label":"","confidence":0.0,"fallback_used":False}
def event(name,phase="start",**data):
    if phase=="start": STATE["events"].append({"event":name+"_start","case_id":STATE["current_case"],"timestamp":time.time()})
    else:
        STATE["events"].append({"event":name+"_end","case_id":STATE["current_case"],"timestamp":time.time(),**data}); STATE["counters"][name+"_calls"]+=1
def update(**data): STATE["cases"][STATE["current_case"]].update(data)
