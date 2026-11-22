#!/usr/bin/env python3
"""Private Kauthar demo: download verified CC0 Commons clips, never commit media.
Uses Wikimedia imageinfo for exact license; forbids non-CC0 and files >30MiB.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "remotion-app" / "public" / "stock"
MAX_BYTES = 30 * 1024 * 1024
CANDIDATES = {
    "experience": ["File:Cloudy Beach.webm", "File:Kelingking Beach.webm",
                   "File:Along the Shore of Teluk Prancis Beach (1).webm"],
    "giving": ["File:Food done and ready.webm", "File:Cooking Chicken and Rice.webm"]
}
def load(url):
    request = urllib.request.Request(url, headers={"User-Agent": "StoryStudio3/0.1 (license-verified editorial private preview)"})
    return urllib.request.urlopen(request, timeout=35)

def metadata(title):
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action":"query", "format":"json", "prop":"imageinfo",
        "iiprop":"url|size|mime|extmetadata", "titles":title})
    with load(u) as r: data = json.load(r)
    page = next(iter(data["query"]["pages"].values()))
    if "missing" in page or not page.get("imageinfo"):
        raise ValueError("Missing file: " + title)
    info=page["imageinfo"][0]; ext=info.get("extmetadata",{})
    license_id=re.sub("<[^>]*>","",ext.get("LicenseShortName",{}).get("value",""))
    if license_id != "CC0":
        raise ValueError("Not CC0: "+title+" "+license_id)
    if info.get("size",0)>MAX_BYTES or info.get("size",0)<=0:
        raise ValueError("Large/invalid file: "+title+" bytes="+str(info.get("size")))
    if not info["url"].startswith("https://upload.wikimedia.org/"):
        raise ValueError("Non-wikimedia upload URL")
    return {"title":title,"url":info["url"],"page":info.get("descriptionurl"),
            "license":"CC0","license_status":"VERIFIED",
            "credit":re.sub("<[^>]*>","",ext.get("Artist",{}).get("value",""))[:300],
            "source_bytes":info["size"],"mime":info.get("mime")}

def download_item(role,candidates):
    errors=[]
    for title in candidates:
        try:
            obj=metadata(title)
            dest=OUT/(role+".webm")
            hasher=hashlib.sha256()
            total=0
            with load(obj["url"]) as r, dest.open("wb") as f:
                while chunk := r.read(65536):
                    total+=len(chunk)
                    if total>MAX_BYTES:
                        raise ValueError("File too large at download")
                    hasher.update(chunk); f.write(chunk)
            if total < 3000:
                raise ValueError("Small/invalid media")
            obj.update({"file":"stock/"+role+".webm", "downloaded_bytes":total, "sha256":hasher.hexdigest(),
                        "description":"Illustrative stock, not Kauthar's own camera footage", "role":role})
            return obj
        except Exception as e:
            errors.append(title+": "+str(e))
            if (OUT/(role+".webm")).exists():
                (OUT/(role+".webm")).unlink()
    return {"role":role,"status":"BLOCKED","errors":errors}

if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    assets=[download_item(r, titles) for r,titles in CANDIDATES.items()]
    manifest={"assets":assets,"publishable":False, "creator_source_rights":"UNCLEARED",
              "note":"CC0 applies to stock assets only; Kauthar A-roll remains private."}
    path=ROOT/"remotion-app"/"public"/"stock"/"asset_licenses.json"
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
