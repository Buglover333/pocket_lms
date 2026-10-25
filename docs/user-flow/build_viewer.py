from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
p=Path(__file__).resolve().parent
names=['01-teacher-flow-v3','02-student-flow-v3','03-files-s3-flow-v3']
labels=['Преподаватель','Студент','Файлы и S3']
svgs=[(p/(n+'.svg')).read_text() for n in names]
nodes={}
contract_path = next(q for q in (p.parents[1]/'openapi.json', p.parents[2]/'pocket_lms-review/openapi.json') if q.exists())
contract=json.loads(contract_path.read_text())
for name in names:
 ET.parse(p/(name+'.svg'))
 entries=json.loads((p/(name+'.json')).read_text())
 for e in entries:
  assert e['id'] not in nodes
  for method,path in e['apis']:
   assert method.lower() in contract['paths'].get(path,{}),(method,path)
  nodes[e['id']]=e
 # No overlapping process cards.
 for i,a in enumerate(entries):
  for b in entries[i+1:]:
   overlap=min(a['x']+a['w'],b['x']+b['w'])>max(a['x'],b['x']) and min(a['y']+a['h'],b['y']+b['h'])>max(a['y'],b['y'])
   assert not overlap,(a['id'],b['id'])
html='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pocket LMS · User Flow + API · v3</title><style>
*{box-sizing:border-box}body{margin:0;height:100vh;overflow:hidden;display:flex;flex-direction:column;color:#17334b;background:#eef3f7;font:14px -apple-system,BlinkMacSystemFont,Arial,sans-serif}header{background:#102b43;color:white;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;gap:20px}h1{margin:0 0 6px;font-size:22px}header p{margin:0;color:#c7dbe8;font-size:13px}.tools{display:flex;align-items:center;gap:10px;padding:12px 24px;background:white;border-bottom:1px solid #d3dee7;flex-wrap:wrap}button{padding:9px 14px;border:1px solid #c5d4df;border-radius:8px;background:white;color:#17334b;cursor:pointer;font:inherit}button.active{background:#173e5f;color:white;border-color:#173e5f}.view{min-height:0;flex:1;overflow:auto;padding:24px}.sheet{background:white;width:1280px;margin:0 auto;box-shadow:0 4px 24px #102b431a}.sheet svg{width:100%;height:auto;display:block}g[data-node]{cursor:pointer}g[data-node]:hover>rect:first-of-type{stroke:#1879b9;stroke-width:4}g[data-node].selected>rect:first-of-type{stroke:#c78b20;stroke-width:5}.zoom{display:flex;align-items:center;gap:8px;margin-left:auto}.status{font-size:12px;background:#fff8e8;color:#795411;padding:9px 24px}.drawer{display:none;position:fixed;right:22px;top:160px;bottom:60px;width:380px;overflow:auto;background:white;border:1px solid #c5d4df;border-radius:14px;box-shadow:0 8px 40px #102b4330;padding:20px;z-index:10}.drawer.open{display:block}.drawer h2{font-size:20px;line-height:1.4}.drawer p{font-size:15px;line-height:1.65}.drawer code{display:block;padding:11px;margin:8px 0;background:#edf5fa;border-radius:7px;font-size:13px;overflow-wrap:anywhere}.drawer .close{float:right}.small{font-size:12px;color:#62788c}.empty{color:#62788c;font-style:italic}@media(max-width:800px){.zoom{margin-left:0}.drawer{left:15px;right:15px;width:auto;top:200px}header{padding:12px 16px}h1{font-size:18px}.tools{padding:10px 14px}}@media print{header,.tools,.status,.drawer{display:none!important}body{height:auto;overflow:visible;background:white}.view{overflow:visible;padding:0}.sheet{width:100%!important;box-shadow:none;margin:0}}
</style><header><div><h1>Pocket LMS · юзер-флоу с эндпоинтами</h1><p>Версия 3 · 25 октября 2026 · схемы API ветки endpoints</p></div><span>GET · POST · PATCH</span></header><nav class="tools"><button id="tab0" class="active" onclick="show(0)">Преподаватель</button><button id="tab1" onclick="show(1)">Студент</button><button id="tab2" onclick="show(2)">Файлы и S3</button><button onclick="fit()">Вписать по ширине</button><button onclick="saveSVG()">Скачать SVG</button><label class="zoom">Масштаб <input id="zoom" type="range" min="25" max="160" value="50" oninput="scale(this.value)"><span id="percent">50%</span></label></nav><main id="view" class="view"><div class="sheet" id="sheet"></div></main><div class="status">Нажмите блок для пояснения. Жёлтым отмечены ещё не реализованные функции. Схема API ветки endpoints; реальный S3 требует отдельной проверки.</div><aside id="drawer" class="drawer"><button class="close" onclick="closeCard()">Закрыть</button><div id="card"></div></aside><script>
const svgs=SVGS,nodes=NODES,names=NAMES;let current=0;
function scale(v){document.getElementById('sheet').style.width=(2560*v/100)+'px';document.getElementById('zoom').value=v;document.getElementById('percent').textContent=v+'%'}
function fit(){const z=Math.max(25,Math.min(160,Math.floor((document.getElementById('view').clientWidth-50)/2560*100)));scale(z)}
function show(i){current=i;document.getElementById('sheet').innerHTML=svgs[i];document.querySelectorAll('.tools button[id^=tab]').forEach((b,j)=>b.classList.toggle('active',i===j));document.getElementById('view').scrollTop=0;closeCard();fit()}
function closeCard(){document.getElementById('drawer').classList.remove('open');document.querySelectorAll('g.selected').forEach(x=>x.classList.remove('selected'))}
function saveSVG(){const url=URL.createObjectURL(new Blob([svgs[current]],{type:'image/svg+xml'}));const a=document.createElement('a');a.href=url;a.download=names[current]+'.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
document.getElementById('sheet').addEventListener('click',e=>{const g=e.target.closest('g[data-node]');if(!g)return;closeCard();g.classList.add('selected');const n=nodes[g.getAttribute('data-node')],c=document.getElementById('card');c.replaceChildren();const heading=document.createElement('h2');heading.textContent=n.title;c.append(heading);for(const [m,p] of n.apis){const code=document.createElement('code');code.textContent=m+' '+p;c.append(code)}if(!n.apis.length){const q=document.createElement('p');q.className='empty';q.textContent='Отдельный запрос LMS для этого шага не нужен.';c.append(q)}const body=document.createElement('p');body.textContent=n.note;c.append(body);document.getElementById('drawer').classList.add('open')});show(0);
</script></html>'''.replace('SVGS',json.dumps(svgs,ensure_ascii=False)).replace('NODES',json.dumps(nodes,ensure_ascii=False)).replace('NAMES',json.dumps(names))
(p/'user-flow-v3.html').write_text(html)
(p/'README.txt').write_text('Pocket LMS — юзер-флоу с эндпоинтами, версия 3, 25.10.2026\n\nОткрыть user-flow-v3.html в любом браузере. Все три схемы встроены в файл: переключение ролей, масштаб и пояснения по нажатию. Файл можно отправить коллеге; интернет для просмотра не нужен.\n\nPNG — для вставки на холст или в документ. SVG — для увеличения и редактирования.\n\nСхемы соответствуют исправлениям API ветки endpoints от 25.10.2026. Нереализованные функции выделены жёлтым. Настоящая интеграция S3 ещё требует bucket и тестовой роли.\n\nУ запросов POST /auth и POST /register альтернативные условия: вход либо регистрация. При действующей сессии — сразу главная. Методы у одного блока могут быть альтернативами; примечания поясняют выбор.\n')
with zipfile.ZipFile(p/'user-flow-v3-all.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in names:
  z.write(p/(n+'.png'),n+'.png');z.write(p/(n+'.svg'),n+'.svg')
 z.write(p/'user-flow-v3.html','user-flow-v3.html');z.write(p/'README.txt','README.txt')
with zipfile.ZipFile(p/'user-flow-v3-all.zip') as z:assert z.testzip() is None
print('Validated',len(nodes),'stage cards; all method/path pairs match local OpenAPI; no overlapping cards.')
