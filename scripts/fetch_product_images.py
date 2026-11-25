#!/usr/bin/env python3
"""Download genuine product images from the gift's linked retailer pages.

No tracking, no generated images, no guessed product matches. Images are checked,
resized and re-encoded to strip metadata before committing to the public site.
"""
import json, os, re, time, io, html, pathlib
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"assets"/"products"
OUT.mkdir(parents=True,exist_ok=True)
DATA=json.loads((ROOT/"products.json").read_text(encoding="utf-8"))
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36","Accept-Language":"es-ES,es;q=0.9,en;q=0.8"})
def candidates(soup,base):
    found=[]
    def add(url):
        if not isinstance(url,str) or not url.strip(): return
        u=urljoin(base,html.unescape(url.strip()))
        if u.startswith("https://") or u.startswith("http://"):
            if u not in found: found.append(u)
    for attrs in [{"property":"og:image:secure_url"},{"property":"og:image"},{"name":"twitter:image"},{"property":"twitter:image"},{"itemprop":"image"}]:
        for tag in soup.find_all("meta",attrs=attrs):add(tag.get("content"))
    for link in soup.find_all("link",rel="image_src"):add(link.get("href"))
    for script in soup.find_all("script",type="application/ld+json"):
        try: data=json.loads(script.string or script.get_text())
        except Exception:continue
        def walk(v):
            if isinstance(v,list):
                for a in v:walk(a)
            if isinstance(v,dict):
                typ=v.get("@type",[])
                if isinstance(typ,str):typ=[typ]
                if "Product" in typ:
                    imgs=v.get("image",[])
                    if isinstance(imgs,str):add(imgs)
                    elif isinstance(imgs,list):
                        for im in imgs:
                            if isinstance(im,str):add(im)
                            elif isinstance(im,dict):add(im.get("url"))
                for a in v.values():
                    if isinstance(a,(list,dict)):walk(a)
        walk(data)
    for img in soup.select("img"):
        attrs=" ".join(str(img.get(k,"")) for k in ("class","id","alt")).lower()
        if any(k in attrs for k in ("product","main-image","hero","gallery","pdp","primary")):
            for k in ("data-src","data-zoom-image","src","data-original"):add(img.get(k))
    return found
def get_image(url,referer):
    r=S.get(url,timeout=24,headers={"Referer":referer},stream=True)
    r.raise_for_status()
    if "image" not in r.headers.get("content-type","").lower() and not urlparse(r.url).path.lower().endswith((".jpg",".jpeg",".png",".webp")):raise ValueError("not image")
    data=bytearray()
    for chunk in r.iter_content(65536):
        data.extend(chunk)
        if len(data)>16_000_000:raise ValueError("image too large")
    im=Image.open(io.BytesIO(data))
    im.load()
    if im.width<240 or im.height<240:raise ValueError("too small")
    if im.width/im.height>3.5 or im.height/im.width>3.5:raise ValueError("banner aspect ratio")
    im=ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((1200,1200),Image.Resampling.LANCZOS)
    buf=io.BytesIO()
    im.save(buf,format="WEBP",quality=84,method=6)
    return buf.getvalue(),(im.width,im.height)
status=[]
for p in DATA:
    idx=p["id"]
    link=p["url"]
    target=OUT/f"{idx:02d}.webp"
    if not link:
        status.append({"id":idx,"status":"no retailer link"});continue
    if target.exists() and target.stat().st_size>5000:
        status.append({"id":idx,"status":"saved","file":f"assets/products/{idx:02d}.webp"});continue
    try:
        page=S.get(link,timeout=28)
        page.raise_for_status()
        soup=BeautifulSoup(page.text,"html.parser")
        urls=candidates(soup,page.url)
        print(f"{idx:02d} {p['name']}: {page.status_code}, {len(urls)} candidate images",flush=True)
        for u in urls[:18]:
            try:
                content,size=get_image(u,page.url)
                target.write_bytes(content)
                status.append({"id":idx,"status":"saved","file":f"assets/products/{idx:02d}.webp","source_page":page.url,"source_image":u,"dimensions":size})
                print(f"  saved {size}",flush=True)
                break
            except Exception as e: print(f"  rejected {u[:95]}: {str(e)[:100]}",flush=True)
        else: status.append({"id":idx,"status":"no valid product image","source_page":page.url})
    except Exception as e:
        status.append({"id":idx,"status":"page inaccessible","error":str(e)[:160]})
    time.sleep(.4)
(ROOT/"image-status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("RESULT:",json.dumps({"saved":sum(x["status"]=="saved" for x in status),"total":len(status)},ensure_ascii=False),flush=True)
