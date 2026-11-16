import json,urllib.request,urllib.parse,time
Q={'en':['"cloud gaming" telemetry','"sim racing" telemetry','"racing simulator" telemetry video','HUD OCR telemetry video game','telemetry extraction onboard video OCR speed','"cloud gaming" "racing" driver data'],
   'pt':['telemetria "jogos em nuvem"','telemetria "simulador de corrida"','telemetria vídeo OCR velocidade','"computação em nuvem" jogos telemetria piloto']}
out={}
for lang,qs in Q.items():
    for q in qs:
        url='https://api.openalex.org/works?'+urllib.parse.urlencode({'search':q,'per-page':25,'mailto':'tcc@example.org','select':'display_name,publication_year,doi,primary_location'})
        try: r=json.load(urllib.request.urlopen(url,timeout=40))
        except Exception as e: r={'error':str(e)}
        out[q]={'lang':lang,'count':r.get('meta',{}).get('count'),'top':[(w['display_name'],w['publication_year'],w.get('doi')) for w in r.get('results',[])]}
        print(lang,q,out[q]['count']); time.sleep(1)
    
for q in ['all:"cloud gaming" AND all:telemetry','all:"sim racing"','all:racing AND all:HUD AND all:OCR','all:telemetry AND all:video AND all:OCR']:
    url='http://export.arxiv.org/api/query?'+urllib.parse.urlencode({'search_query':q,'max_results':25})
    try: x=urllib.request.urlopen(url,timeout=40).read().decode()
    except Exception as e: x=str(e)
    import re
    tot=re.search(r'<opensearch:totalResults[^>]*>(\d+)',x); titles=[re.sub(r'\s+',' ',t) for t in re.findall(r'<entry>.*?<title>(.*?)</title>',x,re.S)]
    out['arXiv '+q]={'lang':'en','count':int(tot.group(1)) if tot else None,'top':titles}
    print('arxiv',q,out['arXiv '+q]['count']); time.sleep(3)
json.dump(out,open('openalex_arxiv.json','w'),indent=1,ensure_ascii=False)
