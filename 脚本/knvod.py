"""
{
    "key": "柯南影视",
    "name": "柯南影视",
    "type": 3,
    "api": "./py/knvod.py",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 1
}
"""

import hashlib
import json
import re
import time
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter

requests.packages.urllib3.disable_warnings()

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


class Spider(BaseSpider):
    HOST='https://www.knvod.com'
    PARSE='https://xn--ewr.211997.xyz'
    UID='DCC147D11943AF75'
    UA='Mozilla/5.0 (Linux; Android 12; SM-G977N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

    def init(self,extend=''):
        self.s=requests.Session()
        self.s.mount('https://',HTTPAdapter(max_retries=2))
        self.s.verify=False
        return self

    def getName(self):
        return '柯南影视'

    def isVideoFormat(self,url):
        return any(x in url for x in ('.m3u8','.mp4','.flv','.mkv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def headers(self,ref=None):
        return {'User-Agent':self.UA,'Referer':ref or self.HOST+'/','Accept':'*/*','Accept-Language':'zh-CN,zh;q=0.9'}

    def fetch(self,url,ref=None,tries=6):
        for i in range(tries):
            r=self.s.get(url,headers=self.headers(ref),timeout=20)
            if r.status_code==200 and len(r.text)>200:
                return r.text
            time.sleep(1.2)
        return ''

    def apikey(self,t):
        return hashlib.md5(('DS%d%s'%(t,self.UID)).encode()).hexdigest()

    def parsekey(self):
        t=int(time.time())
        return hashlib.sha256(('%d%s'%(t//3600*3600,'knvod')).encode()).hexdigest()

    def vodapi(self,tid,page,ext=None):
        t=int(time.time())
        d={'type':tid,'class':'','area':'','lang':'','version':'','state':'','letter':'','page':page,'time':t,'key':self.apikey(t)}
        if ext:
            for k in ('class','area','lang','year','version','state','letter','by'):
                if ext.get(k): d[k]=ext[k]
        h=self.headers()
        h['X-Requested-With']='XMLHttpRequest'
        h['Content-Type']='application/x-www-form-urlencoded'
        for i in range(4):
            r=self.s.post(self.HOST+'/index.php/api/vod',data=d,headers=h,timeout=20)
            if r.status_code==200 and r.text.strip().startswith('{'):
                return r.json()
            time.sleep(1.2)
        return {}

    def vodlist(self,arr):
        return [{'vod_id':str(v.get('vod_id','')),'vod_name':v.get('vod_name',''),'vod_pic':v.get('vod_pic',''),'vod_remarks':v.get('vod_remarks','')} for v in arr if v.get('vod_id')]

    def homeContent(self,filter):
        cls=[{'type_id':'1','type_name':'电影'},{'type_id':'2','type_name':'连续剧'},{'type_id':'3','type_name':'综艺'},{'type_id':'4','type_name':'动漫'}]
        res={'class':cls}
        if filter: res['filters']=self.filters()
        j=self.vodapi(2,1)
        res['list']=self.vodlist(j.get('list',[]))
        return res

    def homeVideoContent(self):
        j=self.vodapi(1,1)
        return {'list':self.vodlist(j.get('list',[]))}

    def categoryContent(self,tid,pg,filter,extend):
        page=int(pg) if pg else 1
        j=self.vodapi(tid,page,extend)
        return {'list':self.vodlist(j.get('list',[])),'page':page,'pagecount':int(j.get('pagecount',1) or 1),'limit':int(j.get('limit',10) or 10),'total':int(j.get('total',0) or 0)}

    def detailContent(self,ids):
        vid=ids[0]
        h=self.fetch('%s/vdetail/%s.html'%(self.HOST,vid))
        if not h: return {'list':[]}
        name=self.first(h,[r'<h1[^>]*>([^<]+)</h1>',r'<title>《([^》]+)》'])
        pic=self.first(h,[r'alt="[^"]*海报图片"[^>]*data-src="([^"]+)"',r'alt="海报背景"[^>]*src="(https?://[^"]+)"',r'data-src="(https?://[^"]+)"'])
        names=re.findall(r'<a class="swiper-slide"[^>]*>.*?</i>&nbsp;([^<]+?)<span',h,re.S) or re.findall(r'swiper-slide[^>]*>(?:[^<]*<i[^>]*></i>)?[^<]*?([^<>]{1,12})<span class="badge"',h)
        blocks=re.findall(r'<ul class="anthology-list-play[^"]*">(.*?)</ul>',h,re.S)
        froms,urls=[],[]
        for i,b in enumerate(blocks):
            eps=re.findall(r'href="(/vplay/[\d\-]+\.html)"[^>]*>([^<]+)<',b)
            if not eps: continue
            eps=eps[::-1]
            froms.append(names[i].strip() if i<len(names) else '线路%d'%(i+1))
            urls.append('#'.join('%s$%s'%(t.strip(),u) for u,t in eps))
        v={'vod_id':vid,'vod_name':name,'vod_pic':pic,
           'vod_year':self.pick(h,'年份'),'vod_area':self.pick(h,'地区'),
           'vod_remarks':self.pick(h,'状态') or self.pick(h,'备注'),
           'vod_actor':self.pick(h,'主演') or self.pick(h,'演员'),'vod_director':self.pick(h,'导演'),
           'vod_content':self.pick(h,'简介') or self.first(h,[r'id="height_limit"[^>]*>([^<]+)<',r'name="description"\s+content="([^"]+)"']),
           'vod_play_from':'$$$'.join(froms),'vod_play_url':'$$$'.join(urls)}
        return {'list':[v]}

    def searchContent(self,key,quick,pg='1'):
        page=int(pg) if pg else 1
        kw=quote(key)
        u='%s/search/%s----------%d---.html'%(self.HOST,kw,page)
        h=self.fetch(u)
        if not h:
            h=self.fetch('%s/search/%s-------------.html'%(self.HOST,kw))
        seen,out={},[]
        for b in re.findall(r'<div class="public-list-box search-box.*?(?=<div class="public-list-box search-box|<div class="page)',h,re.S):
            vid=self.first(b,[r'/vdetail/(\d+)\.html'])
            if not vid or vid in seen: continue
            seen[vid]=1
            out.append({'vod_id':vid,
                'vod_name':self.first(b,[r'class="thumb-txt[^"]*"[^>]*><a[^>]*>([^<]+)<',r'alt="([^"]*?)封面图"']),
                'vod_pic':self.first(b,[r'data-src="(https?://[^"]+)"']),
                'vod_remarks':self.first(b,[r'class="public-list-prb[^"]*"[^>]*>([^<]+)<'])})
        if not out:
            for vid in re.findall(r'/vdetail/(\d+)\.html',h):
                if vid in seen: continue
                seen[vid]=1
                out.append({'vod_id':vid,'vod_name':'','vod_pic':'','vod_remarks':''})
        return {'list':out,'page':page}

    def playerContent(self,flag,id,vipFlags):
        play=id if id.startswith('http') else self.HOST+id
        h=self.fetch(play)
        m=re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>',h,re.S)
        if not m:
            return {'parse':1,'url':play,'header':self.headers(play)}
        d=json.loads(m.group(1))
        raw=d.get('url','')
        if self.isVideoFormat(raw):
            return {'parse':0,'url':raw,'header':{'User-Agent':self.UA,'Referer':self.HOST+'/'}}
        title=quote(self.first(h,[r'<title>([^<]+?)-'])or'')
        nxt='//www.knvod.com'+(d.get('link_next') or '')
        ppy='%s/ppy.php?url=%s&next=%s&title=%s'%(self.PARSE,raw,nxt,title)
        p=self.fetch(ppy,play)
        cm=re.search(r'var\s+config\s*=\s*(\{.*?\})\s*;',p,re.S)
        if not cm:
            return {'parse':1,'url':ppy,'header':self.headers(play)}
        cfg=cm.group(1)
        cu=self.first(cfg,[r'"url"\s*:\s*"([^"]+)"'])
        dm=self.first(cfg,[r'"dmkey"\s*:\s*"([^"]*)"'])
        pb=self.first(cfg,[r'"pbgjz"\s*:\s*"([^"]*)"'])
        body=json.dumps({'url':cu,'pbgjz':pb,'dmkey':dm,'key':self.parsekey()},ensure_ascii=False)
        hd=self.headers(ppy)
        hd['Content-Type']='application/x-www-form-urlencoded; charset=UTF-8'
        hd['X-Requested-With']='XMLHttpRequest'
        hd['Origin']=self.PARSE
        for i in range(3):
            r=self.s.post(self.PARSE+'/kk.php',data=body.encode('utf-8'),headers=hd,timeout=20)
            if r.status_code==200 and r.text.strip().startswith('{'):
                j=r.json()
                real=j.get('vip') or j.get('url')
                if int(j.get('code',0))==200 and real and 'op_ticket_' not in real:
                    return {'parse':0,'url':real,'header':{'User-Agent':self.UA,'Referer':self.PARSE+'/'}}
            time.sleep(1.2)
        return {'parse':1,'url':ppy,'header':self.headers(play)}

    def localProxy(self,params):
        return [200,'text/plain','']

    def first(self,text,pats):
        for p in pats:
            m=re.search(p,text,re.S)
            if m: return m.group(1).strip()
        return ''

    def pick(self,h,label):
        m=re.search(r'>%s[：:]</em>(.*?)</li>'%label,h,re.S)
        if not m:
            m=re.search(r'>%s\s*[：:]\s*</strong>(.*?)</div>'%label,h,re.S)
        if not m: return ''
        seg=re.sub(r'<span class="slash">/</span>',',',m.group(1))
        seg=re.sub(r'<[^>]+>','',seg).replace('&nbsp;',',')
        return re.sub(r',+',',',seg).strip().strip(',')

    def filters(self):
        by=[{'key':'by','name':'排序','value':[{'n':'最新','v':'time'},{'n':'最热','v':'hits'},{'n':'评分','v':'score'}]}]
        year=[{'key':'year','name':'年份','value':[{'n':str(y),'v':str(y)} for y in range(2026,2009,-1)]}]
        lang=[{'key':'lang','name':'语言','value':[{'n':n,'v':n} for n in ('国语','粤语','韩语','日语','英语','泰语')]}]
        f=by+year+lang
        return {'1':f,'2':f,'3':f,'4':f}


# ---- TVBox 本地线路过滤（自动生成，勿改） ----
_TVBOX_DROP_LINES = []
_TVBOX_LINE_ORDER = ["不卡①", "超快U"]
_TVBOX_DROP_SUB = []
_TVBOX_ORDER_SUB = []
_TVBOX_SINK_SUB = []

def _tvbox_filter_lines(result, drop):
    if not isinstance(result, dict):
        return result
    items = result.get('list')
    if isinstance(items, list):
        for item in items:
            _tvbox_filter_item(item, drop)
    else:
        _tvbox_filter_item(result, drop)
    return result

def _tvbox_filter_item(item, drop):
    froms = item.get('vod_play_from') or ''
    urls = item.get('vod_play_url') or ''
    if not isinstance(froms, str) or not isinstance(urls, str):
        return
    if '$$$' not in froms:
        return
    parts_from = [f.strip() for f in froms.split('$$$')]
    parts_url = urls.split('$$$')
    if len(parts_from) != len(parts_url):
        return
    keep = [(f, u) for f, u in zip(parts_from, parts_url) if f not in drop and not any(s in f for s in _TVBOX_DROP_SUB)]
    if not keep or len(keep) == len(parts_from):
        return
    item['vod_play_from'] = '$$$'.join(f for f, _ in keep)
    item['vod_play_url'] = '$$$'.join(u for _, u in keep)

def _tvbox_sort_lines(result, order):
    if not order and not _TVBOX_ORDER_SUB:
        return result
    if not isinstance(result, dict):
        return result
    items = result.get('list')
    if isinstance(items, list):
        for item in items:
            _tvbox_sort_item(item, order)
    else:
        _tvbox_sort_item(result, order)
    return result

def _tvbox_sort_item(item, order):
    froms = item.get('vod_play_from') or ''
    urls = item.get('vod_play_url') or ''
    if not isinstance(froms, str) or not isinstance(urls, str):
        return
    if '$$$' not in froms:
        return
    parts_from = [f.strip() for f in froms.split('$$$')]
    parts_url = urls.split('$$$')
    if len(parts_from) != len(parts_url):
        return
    known = {f: i for i, f in enumerate(order)}
    subs = [p for p in _TVBOX_ORDER_SUB if p]
    sinks = [p for p in _TVBOX_SINK_SUB if p]
    unknown_base = len(order) + len(subs)
    def _tvbox_rank(f):
        for p in sinks:
            if p in f:
                return unknown_base + 1000
        if f in known:
            return known[f]
        for i, pat in enumerate(subs):
            if pat in f:
                return len(order) + i
        return unknown_base
    # 已知线路按 order（画质速度最优在前），未知线路稳定保持原序后置，
    # sink 命中的差线（4K 等）沉到最后但不删除。
    pairs = list(zip(parts_from, parts_url))
    pairs.sort(key=lambda p: _tvbox_rank(p[0]))
    item['vod_play_from'] = '$$$'.join(f for f, _ in pairs)
    item['vod_play_url'] = '$$$'.join(u for _, u in pairs)

def _tvbox_apply(cls):
    fn = getattr(cls, 'detailContent', None)
    if fn is None:
        return
    def wrapper(self, *a, _fn=fn, **k):
        res = _tvbox_filter_lines(_fn(self, *a, **k), _TVBOX_DROP_LINES)
        return _tvbox_sort_lines(res, _TVBOX_LINE_ORDER)
    setattr(cls, 'detailContent', wrapper)

_tvbox_apply(Spider)
