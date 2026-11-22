#!/usr/bin/env python3
"""Search locally cached RemotionUI/HyperFrames catalog; never auto-install effects."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def load_catalog(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for key in ("components","items","blocks"):
            if isinstance(data.get(key),list): return data[key]
    raise ValueError("No recognized catalog items list")

def search(items,term,count):
    words=[w.lower() for w in term.split() if w.strip()]
    result=[]
    for item in items:
        if not isinstance(item,dict): continue
        fields=[item.get("name",""),item.get("description",""),item.get("type",""),
                " ".join(str(t) for t in item.get("tasks",[]))]
        corpus=" ".join(str(f) for f in fields).lower()
        hits=sum(int(w in corpus) for w in words)
        if words and not hits: continue
        score=hits*3+sum(int(w in str(item.get("name","")).lower()) for w in words)*4
        result.append((score,{k:item.get(k) for k in ("name","description","type","installCommand","docsUrl","tasks") if item.get(k) is not None}))
    return [x[1] for x in sorted(result,key=lambda x:(-x[0],x[1].get("name","")))[:count]]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("catalog")
    p.add_argument("query")
    p.add_argument("--count",type=int,default=8)
    a=p.parse_args()
    items=load_catalog(a.catalog)
    print(json.dumps({"catalog_total":len(items),"query":a.query,"results":search(items,a.query,max(1,min(a.count,30)))},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
