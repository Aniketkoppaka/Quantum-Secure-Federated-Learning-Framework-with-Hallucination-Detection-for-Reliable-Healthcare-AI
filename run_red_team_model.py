"""Resumable, checkpointed red-team benchmark runner."""
import os, json, time, traceback
from datetime import datetime
from red_team_suite import generate_unseen, generate_expert, evaluate, run_engine
import component_telemetry as tel

TRACE=[]; LAST="startup"
def log(step,status="ok",**data):
    global LAST
    LAST=step; item={"timestamp":datetime.now().isoformat(),"step":step,"status":status}; item.update(data); TRACE.append(item); print(f"[{status}] {step}",flush=True)
def save_trace():
    os.makedirs("results",exist_ok=True)
    with open("results/execution_trace.json","w",encoding="utf-8") as f: json.dump({"events":TRACE,"last_completed_step":LAST},f,indent=2)
def save_checkpoint(case_id, record):
    os.makedirs("results/checkpoints",exist_ok=True)
    with open(f"results/checkpoints/checkpoint_{case_id}.json","w",encoding="utf-8") as f: json.dump(record,f,indent=2)
def save_progress(completed,total,start):
    elapsed=time.perf_counter()-start; rate=completed/elapsed if completed else 0; remaining=max(0,total-completed)
    with open("results/progress.json","w",encoding="utf-8") as f: json.dump({"completed_cases":completed,"remaining_cases":remaining,"elapsed_time":round(elapsed,3),"eta":round(remaining/rate,3) if rate else None},f,indent=2)
def append_diagnostic(record):
    if record.get("diagnostic"):
        os.makedirs("results",exist_ok=True)
        with open("results/case_diagnostics.jsonl","a",encoding="utf-8") as f: f.write(json.dumps(record["diagnostic"])+"\n")
def main():
    start=time.perf_counter(); os.environ.setdefault("USE_NLI","true"); os.environ.setdefault("USE_SENTENCE_TRANSFORMERS","true"); tel.reset()
    log("dataset loading")
    with open("results/qa_benchmark_dataset.json",encoding="utf-8") as f: known=json.load(f)["benchmark_100"]
    unseen=generate_unseen(); expert=generate_expert()
    if os.getenv("SMOKE_TEST","false").lower()=="true": known,unseen,expert=known[:5],unseen[:5],expert[:5]
    print("Known cases:",len(known),flush=True); print("Unseen cases:",len(unseen),flush=True); print("Expert cases:",len(expert),flush=True); log("dataset ready",known=len(known),unseen=len(unseen),expert=len(expert))
    import torch
    from transformers import pipeline
    model=os.getenv("HF_MODEL_ID","Qwen/Qwen2.5-0.5B-Instruct"); log("Hugging Face model loading start",model=model)
    generator=pipeline("text-generation",model=model,device=0 if torch.cuda.is_available() else -1); log("Hugging Face model loading end",device="cuda" if torch.cuda.is_available() else "cpu"); print("Model loaded",flush=True)
    from sentence_transformers import SentenceTransformer
    log("Sentence Transformer loading start"); embedder=SentenceTransformer(os.getenv("EMBEDDING_MODEL_ID","sentence-transformers/all-MiniLM-L6-v2"),device="cuda" if torch.cuda.is_available() else "cpu"); log("Sentence Transformer loading end",dimensions=embedder.get_sentence_embedding_dimension())
    log("NLI model loading start"); nli=pipeline("text-classification",model=os.getenv("NLI_MODEL_ID","cross-encoder/nli-deberta-v3-base"),device=0 if torch.cuda.is_available() else -1); log("NLI model loading end")
    from hallucination_engine.knowledge_retriever import MedicalKnowledgeRetriever
    from hallucination_engine.fact_checker import FactChecker
    from hallucination_engine.self_consistency import SelfConsistencyAnalyzer
    from hallucination_engine import HallucinationDecisionEngine
    retriever=MedicalKnowledgeRetriever(embedding_model=embedder); engine=HallucinationDecisionEngine(retriever=retriever,fact_checker=FactChecker(nli_pipeline=nli))
    def wrap(cls,method,name,fields=None):
        original=getattr(cls,method)
        def wrapped(self,*args,**kwargs):
            tel.event(name,"start")
            try: result=original(self,*args,**kwargs); tel.event(name,"end",**(fields(result) if fields else {})); return result
            except Exception as exc: tel.event(name,"end",error=str(exc)); tel.STATE["counters"]["fallback_calls"]+=1; print(f"[fallback] {name} failure: {exc}",flush=True); raise
        setattr(cls,method,wrapped)
    wrap(MedicalKnowledgeRetriever,"retrieve","retrieval",lambda r:{"score":r[0].relevance_score if r else 0.0,"documents":[x.source_id for x in r]})
    original_semantic=MedicalKnowledgeRetriever._semantic_rerank
    def semantic_wrapped(self,*args,**kwargs):
        tel.event("embedding","start"); tel.event("faiss","start"); result=original_semantic(self,*args,**kwargs); tel.event("embedding","end"); tel.event("faiss","end",hits=len(result)); return result
    MedicalKnowledgeRetriever._semantic_rerank=semantic_wrapped
    wrap(FactChecker,"_check_critical_contraindications","rule_check",lambda r:{"flags":[r] if r else []}); wrap(FactChecker,"_nli_status","nli",lambda r:{"label":r[0] if r else "","score":r[1] if r else 0.0}); wrap(SelfConsistencyAnalyzer,"evaluate_consensus","self_consistency",lambda r:{"agreement":r.consensus_score})
    def answer(case):
        log("answer start",case=case["id"])
        try: out=generator("Answer cautiously as a healthcare safety assistant. Question: "+case["input"],max_new_tokens=96,do_sample=False,return_full_text=False); log("answer end",case=case["id"]); return [out[0]["generated_text"]]
        except Exception as exc: tel.STATE["counters"]["fallback_calls"]+=1; log("generation failure","failed",case=case["id"],exception=str(exc)); raise
    total=sum(map(len,(known,unseen,expert))); all_records=[]; completed=0
    open("results/case_diagnostics.jsonl","w",encoding="utf-8").close()
    def phase(name,cases):
        nonlocal completed
        log(name+" start",count=len(cases)); records=[]
        for i,c in enumerate(cases,1):
            cp=f"results/checkpoints/checkpoint_{c['id']}.json"
            if os.path.exists(cp):
                with open(cp,encoding="utf-8") as f: record=json.load(f)
                records.append(record); all_records.append(record); completed+=1; print(f"Resuming {c['id']}",flush=True); continue
            print(f"Processing case {i}/{len(cases)}",flush=True); tel.begin_case(c["id"],c["input"],"")
            try:
                ans=answer(c); tel.update(generated_answer=ans[0]); record=run_engine([c],lambda _:ans,engine=engine)[0]; append_diagnostic(record); ev=[x for x in tel.STATE["events"] if x.get("case_id")==c["id"]]; names={x["event"] for x in ev}; tel.update(retrieval_used="retrieval_end" in names,embedding_used="embedding_end" in names,faiss_used="faiss_end" in names,nli_used="nli_end" in names,rule_checker_used="rule_check_end" in names,self_consistency_used="self_consistency_end" in names,predicted_label=record["predicted"],confidence=record["confidence"])
            except Exception as exc: record={"id":c["id"],"expected":c["expected_class"],"predicted":"BLOCKED","confidence":0.0,"error":str(exc)}; log("case failure","failed",case=c["id"],exception=str(exc))
            save_checkpoint(c["id"],record); records.append(record); all_records.append(record); completed+=1; save_progress(completed,total,start)
            if completed%5==0:
                with open("results/red_team_model_results.partial.json","w",encoding="utf-8") as f: json.dump({"records":all_records,"execution_summary":dict(tel.STATE["counters"])},f,indent=2)
        result=evaluate(records); log(name+" end",metrics=result); return result
    results={"model":model,"known":phase("KNOWN",known),"unseen":phase("UNSEEN",unseen),"expert":phase("EXPERT",expert),"runtime_seconds":round(time.perf_counter()-start,3),"records":all_records}; results["generalization_gap"]=results["known"]["accuracy"]-results["unseen"]["accuracy"]; results["component_trace"]=list(tel.STATE["cases"].values()); results["execution_summary"]=dict(tel.STATE["counters"])
    with open("results/red_team_model_results.json","w",encoding="utf-8") as f: json.dump(results,f,indent=2)
    with open("results/component_execution_proof.json","w",encoding="utf-8") as f: json.dump({"execution_summary":results["execution_summary"],"cases":results["component_trace"],"events":tel.STATE["events"]},f,indent=2)
    save_progress(completed,total,start); log("result file writing end",file="results/red_team_model_results.json"); save_trace()
if __name__=="__main__":
    try: main()
    except Exception as e: log("execution failed",status="failed",exception=str(e),traceback=traceback.format_exc()); save_trace(); raise
