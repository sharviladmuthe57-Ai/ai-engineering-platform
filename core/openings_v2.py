"""Additive exterior-aware opening detector V2."""
from typing import Any
import numpy as np
from .openings import _gaps, _profile

def _ori(s): return "horizontal" if s in ("top","bottom") else "vertical"
def _bounds(r,s):
    if s=="top": return r["x"],r["y"]-5,r["x"]+r["w"],r["y"]+5,0
    if s=="bottom": return r["x"],r["y"]+r["h"]-5,r["x"]+r["w"],r["y"]+r["h"]+5,0
    if s=="left": return r["x"]-5,r["y"],r["x"]+5,r["y"]+r["h"],1
    return r["x"]+r["w"]-5,r["y"],r["x"]+r["w"]+5,r["y"]+r["h"],1
def _exterior(regions,W,H):
    if not regions:return set()
    a=min(r["x"] for r in regions); b=min(r["y"] for r in regions)
    c=max(r["x"]+r["w"] for r in regions); d=max(r["y"]+r["h"] for r in regions); t=max(8,int(min(W,H)*.018)); out=set()
    for i,r in enumerate(regions):
        if abs(r["y"]-b)<=t:out.add((i,"top"))
        if abs(r["y"]+r["h"]-d)<=t:out.add((i,"bottom"))
        if abs(r["x"]-a)<=t:out.add((i,"left"))
        if abs(r["x"]+r["w"]-c)<=t:out.add((i,"right"))
    return out
def _geometry(r,s,a,b):
    q=(a+b)/2
    if s in ("top","bottom"):
        y=r["y"] if s=="top" else r["y"]+r["h"]; return {"x":r["x"]+q,"y":y},[{"x":r["x"]+a,"y":y},{"x":r["x"]+b,"y":y}]
    x=r["x"] if s=="left" else r["x"]+r["w"]; return {"x":x,"y":r["y"]+q},[{"x":x,"y":r["y"]+a},{"x":x,"y":r["y"]+b}]
def _ink(binary,p,r):
    x,y=p["position_px"]["x"],p["position_px"]["y"]; h=max(8,p["width_px"]//2); d=max(12,int(min(r["w"],r["h"])*.12));s=p["side"]
    if s=="top":z=binary[int(y):int(y)+d,max(0,int(x)-h):int(x)+h]
    elif s=="bottom":z=binary[int(y)-d:int(y),max(0,int(x)-h):int(x)+h]
    elif s=="left":z=binary[max(0,int(y)-h):int(y)+h,int(x):int(x)+d]
    else:z=binary[max(0,int(y)-h):int(y)+h,int(x)-d:int(x)]
    return float(np.count_nonzero(z))/z.size if z.size else 1.
def _parallel(binary,p):
    (a,b)=p["endpoints_px"];x1,y1=a["x"],a["y"];x2,y2=b["x"],b["y"];k=max(5,p["width_px"]//8)
    if p["orientation"]=="horizontal":z=binary[max(0,y1-k):y1+k+1,max(0,x1):x2];v=np.sum(z>0,axis=1);n=z.shape[1]
    else:z=binary[max(0,y1):y2,max(0,x1-k):x1+k+1];v=np.sum(z>0,axis=0);n=z.shape[0]
    return round(min(1.,np.count_nonzero(v>=n*.45)/3),2) if v.size else 0.
def _cluster(raw,short):
    out=[];d=max(12,int(short*.018))
    for p in sorted(raw,key=lambda x:x["width_px"],reverse=True):
        q=next((q for q in out if q["orientation"]==p["orientation"] and abs(q["position_px"]["x"]-p["position_px"]["x"])<=d and abs(q["position_px"]["y"]-p["position_px"]["y"])<=d),None)
        if q:q["raw_proposal_ids"].append(p["proposal_id"]);q["support_count"]+=1;q["exterior_wall"]|=p["exterior_wall"]
        else:p["raw_proposal_ids"]=[p["proposal_id"]];p["support_count"]=1;out.append(p)
    return out
def extract_opening_candidates_v2(wall_mask,binary,regions,*,scale_x_m_per_px,scale_y_m_per_px,W,H):
    ext=_exterior(regions,W,H);raw=[];lo=max(10,int(min(W,H)*.018));hi=max(70,int(min(W,H)*.23))
    for i,r in enumerate(regions):
      for s in ("top","bottom","left","right"):
       x1,y1,x2,y2,axis=_bounds(r,s)
       for a,b in _gaps(_profile(wall_mask,x1,y1,x2,y2,axis),lo,hi):
        pos,ends=_geometry(r,s,a,b);raw.append({"proposal_id":f"v2_raw_{i}_{s}_{a}_{b}","room_id":f"room_{i+1}","region_index":i,"side":s,"wall_location":s,"orientation":_ori(s),"position_px":pos,"endpoints_px":ends,"width_px":b-a,"exterior_wall":(i,s) in ext})
    clustered=_cluster(raw,min(W,H));final=[]
    for p in clustered:
      r=regions[p["region_index"]];noise=round(min(1.,_ink(binary,p,r)*3),2);parallel=_parallel(binary,p) if p["exterior_wall"] else 0.;width=round(min(1.,p["width_px"]/max(min(r["w"],r["h"])*.35,1)),2);kind=None
      if p["exterior_wall"] and parallel>=.33 and noise<.72:kind="window"
      elif not p["exterior_wall"] and p["width_px"]>=max(22,int(min(W,H)*.035)) and noise<.36:kind="door"
      elif p["exterior_wall"] and p["width_px"]>=max(40,int(min(W,H)*.07)) and noise<.42:kind="door"
      if not kind:continue
      scale=scale_x_m_per_px if p["orientation"]=="horizontal" else scale_y_m_per_px;conf=.30+.20*width+.20*min(1.,p["support_count"]/2)+(.22*parallel if kind=="window" else .12*(1-noise))
      final.append({"id":f"opening_v2_{kind}_{p['proposal_id']}","type":kind,"room_id":p["room_id"],"position_px":p["position_px"],"side":p["side"],"wall_location":p["wall_location"],"offset_px":None,"width_px":p["width_px"],"approx_width_m":round(p["width_px"]*scale,2),"scale_x_m_per_px":round(scale_x_m_per_px,8),"scale_y_m_per_px":round(scale_y_m_per_px,8),"confidence":round(min(.92,conf),2),"detection_method":"exterior_wall_aware_v2","provenance":{"source":"cv_wall_mask","version":"v2","raw_proposal_ids":p["raw_proposal_ids"],"evidence":{"gap_score":1.,"exterior_wall":p["exterior_wall"],"parallel_line_score":parallel,"width_score":width,"fixture_noise_penalty":noise,"wall_continuity_score":round(min(1.,p["support_count"]/2),2)}},"verification_status":"pending","endpoints_px":p["endpoints_px"]})
    return final,{"raw_proposals":len(raw),"deduplicated_proposals":len(clustered),"final_candidates":len(final)}
