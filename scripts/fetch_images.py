import os,re,time,requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlparse
from pathlib import Path
from PIL import Image,ImageOps
from io import BytesIO

HTML=Path('index.html').read_text(encoding='utf-8')
cards=re.findall(r'<article class="gift".*?</article>',HTML,re.S)
folder=Path('images');folder.mkdir(exist_ok=True)
s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36','Accept-Language':'es-ES,es;q=0.9,en;q=0.8'})
def candidates(url):
    try:
        r=s.get(url,timeout=22)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,'html.parser')
        found=[]
        for selector,attr in [('meta[property="og:image:secure_url"]','content'),('meta[property="og:image"]','content'),('meta[name="twitter:image"]','content'),('meta[property="twitter:image"]','content'),('link[rel="image_src"]','href')]:
            for tag in soup.select(selector):found.append(urljoin(r.url,tag.get(attr,'')))
        for selector in ['img#landingImage','img[data-old-hires]','img.product__media','img.product-image','img[itemprop="image"]','img']:
            for tag in soup.select(selector)[:8]:
                src=tag.get('data-old-hires') or tag.get('data-src') or tag.get('src') or ''
                if src and not src.startswith('data:'):found.append(urljoin(r.url,src))
            if found:break
        return list(dict.fromkeys(x for x in found if x.startswith('http')))
    except Exception as e:
        print('Page error',str(e)[:140]);return []
def save(url,path):
    try:
        r=s.get(url,timeout=22,headers={'Referer':urlparse(url).scheme+'://'+urlparse(url).netloc+'/'})
        r.raise_for_status()
        if len(r.content)>12_000_000:return False
        im=Image.open(BytesIO(r.content))
        if im.width<250 or im.height<180:return False
        im=ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((1000,1000),Image.Resampling.LANCZOS)
        im.save(path,'WEBP',quality=84,method=5)
        return True
    except Exception:return False
for i,card in enumerate(cards,1):
    m=re.search(r'<a href="([^"]+)"',card)
    if not m:continue
    dest=folder/f'{i:02}.webp'
    if dest.exists():continue
    print(i,m.group(1),flush=True)
    for u in candidates(m.group(1))[:12]:
        if save(u,dest):
            print(' SAVED',u[:120],flush=True);break
    else:print(' NO IMAGE',flush=True)
    time.sleep(.35)
