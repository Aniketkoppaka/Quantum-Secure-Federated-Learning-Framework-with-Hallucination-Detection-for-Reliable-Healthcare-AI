"""Execute and log every available component with verifiable status."""
import os, json, time, traceback
from datetime import datetime
def phase(log,name,fn):
    t=time.perf_counter(); item={"component":name,"started":datetime.now().isoformat()}
    try: item.update(fn()); item["executed"]=True
    except Exception as e: item.update({"executed":False,"error":str(e),"traceback":traceback.format_exc()})
    item["duration_seconds"]=round(time.perf_counter()-t,3); log.append(item); print(name,item["executed"],item.get("error",""))
def main():
    log=[]; os.environ["USE_SENTENCE_TRANSFORMERS"]="true"; os.environ["USE_NLI"]="true"
    import torch
    phase(log,"CUDA",lambda:{"available":torch.cuda.is_available(),"device":torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,"torch":torch.__version__})
    from transformers import pipeline
    model=os.getenv("HF_MODEL_ID","Qwen/Qwen2.5-0.5B-Instruct")
    holder={}
    def load(): holder["gen"]=pipeline("text-generation",model=model,device=0 if torch.cuda.is_available() else -1); return {"model":model,"device":"cuda" if torch.cuda.is_available() else "cpu"}
    phase(log,"HuggingFace generation",load)
    def semantic():
        from sentence_transformers import SentenceTransformer
        import faiss, numpy as np
        m=SentenceTransformer(os.getenv("EMBEDDING_MODEL_ID","sentence-transformers/all-MiniLM-L6-v2"),device="cuda" if torch.cuda.is_available() else "cpu")
        v=m.encode(["renal impairment medication safety","kidney medication review"],normalize_embeddings=True).astype("float32"); idx=faiss.IndexFlatIP(v.shape[1]); idx.add(v); _,ids=idx.search(v[:1],2); return {"embedding_model":m.get_sentence_embedding_dimension(),"faiss_index":"IndexFlatIP","neighbors":ids.tolist()}
    phase(log,"SentenceTransformer + FAISS",semantic)
    def nli():
        p=pipeline("text-classification",model=os.getenv("NLI_MODEL_ID","cross-encoder/nli-deberta-v3-base"),device=0 if torch.cuda.is_available() else -1)
        return {"model":os.getenv("NLI_MODEL_ID","cross-encoder/nli-deberta-v3-base"),"sample":p({"text":"Aspirin is a medication.","text_pair":"Aspirin is used as a medication."})}
    phase(log,"NLI entailment",nli)
    def safety():
        from hallucination_engine import HallucinationDecisionEngine
        d=HallucinationDecisionEngine().evaluate_response("What is safe?",["Consult a qualified clinician for individualized advice."])
        return {"status":d.status.value,"confidence":d.composite_confidence,"action":d.action}
    phase(log,"Safety engine",safety)
    os.makedirs("results",exist_ok=True)
    json.dump({"run_started":datetime.now().isoformat(),"configuration":{"model":model,"USE_NLI":"true","USE_SENTENCE_TRANSFORMERS":"true"},"phases":log},open("results/execution_proof.json","w"),indent=2)
    print("results/execution_proof.json")
if __name__=="__main__": main()
