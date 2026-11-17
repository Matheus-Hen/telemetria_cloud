import json,urllib.request,urllib.parse,time,sys
Q=['cloud gaming telemetry','sim racing telemetry video','racing game HUD OCR telemetry','extract telemetry from video OCR speed','game video HUD information extraction','telemetria jogos em nuvem','telemetria simulador de corrida','extração de dados vídeo HUD OCR']
out={}
for q in Q:
    url='https://api.semanticscholar.org/graph/v1/paper/search?'+urllib.parse.urlencode({'query':q,'limit':20,'fields':'title,year,venue,externalIds'})
    for t in range(4):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'tcc-busca'}),timeout=30)); break
        except Exception as e:
            r={'error':str(e)}; time.sleep(5)
    out[q]=r; print(q, r.get('total'), r.get('error'))
    time.sleep(3)
json.dump(out,open('semanticscholar.json','w'),indent=1,ensure_ascii=False)
