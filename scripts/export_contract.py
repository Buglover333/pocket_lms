import sys
from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
if str(root / "src") not in sys.path:
    sys.path.insert(0, str(root / "src"))
from backend.api.main import app
spec=app.openapi()
(root/'openapi.json').write_text(encoding='utf-8', data=json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
components=spec['components']['schemas']
def resolved(s):
 while '$ref' in s:s=components[s['$ref'].split('/')[-1]]
 return s
def example(s,name=''):
 s=resolved(s)
 if s.get('examples'):return s['examples'][0]
 if 'default' in s and s['default'] is not None:return s['default']
 if 'enum' in s:return s['enum'][0]
 if 'const' in s:return s['const']
 if 'anyOf' in s:return example(next(x for x in s['anyOf'] if x.get('type')!='null'),name)
 t=s.get('type')
 if t=='object':return {k:example(v,k) for k,v in s.get('properties',{}).items() if k in s.get('required',[]) or k in ('is_published','file_ids','answer_text','first_name','last_name')}
 if t=='array':return [example(s['items'])]
 if t=='boolean':return True
 if t in ('integer','number'):return max(s.get('minimum',1),s.get('exclusiveMinimum',0)+1)
 f=s.get('format')
 if f=='uuid':return '00000000-0000-4000-8000-000000000001'
 if f=='email' or name=='email':return 'student@mail.ru'
 if f=='date-time':return '2026-10-25T12:00:00Z'
 if f=='date':return '2026-10-25'
 if 'password' in name:return 'ExamplePass123'
 if name=='first_name':return 'Анна'
 if name=='last_name':return 'Иванова'
 if name=='mime_type':return 'application/pdf'
 if name=='file_name':return 'report.pdf'
 if 'url' in name:return 'https://example.com/document.pdf'
 if name=='invite_code':return 'EXAMPLE-INVITE'
 if name=='reset_code':return 'ONE-TIME-CODE-FROM-ADMIN-32-CHARACTERS'
 if name=='current_password':return 'CurrentPass123'
 if name=='x-requested-with':return 'PocketLMS'
 if name=='status' and s.get('type')=='string':return 'submitted'
 return 'Пример'
def typename(s):
 if '$ref' in s:return s['$ref'].split('/')[-1]
 if 'anyOf'in s:return ' / '.join(typename(x) for x in s['anyOf'])
 if s.get('type')=='array':return 'array<'+typename(s['items'])+'>'
 return s.get('format',s.get('type','object'))
rows=['# HTTP-контракт Pocket LMS: локальная проверка 04.11.2026','',
'Сгенерировано из текущих моделей приложения. Примеры синтетические. `get_dashboard` отсутствует. Полные схемы — в openapi.json. Применённые решения аналитиков — в docs/API_REVIEW_2026-11-04.md.',
'', 'Для всех защищённых запросов: `Authorization: Bearer <access_token>`. Публичные: `/auth`, `/register`, `/auth/reset_password`, `/app`; `/auth/refresh` использует HttpOnly cookie и обязательный X-Requested-With: PocketLMS. Остальные запросы требуют действующую сессию. Старые `/get_courses`, `/get_modules`, `/get_user_info` также требуют query `user_id`, совпадающий с токеном; это сохранённый контракт.',
'', 'Публикация: PATCH update_material/update_assignment с is_published=true; GET только читает. Планировщик публикации пока отсутствует.',
'', 'Сдачи: GET get_submissions принимает assignment_id и необязательный student_id; без student_id — свои. Чужого студента выбирает преподаватель его курса. Для просмотра сдачи с вложениями используется get_submission_data.',
'', 'Профиль: GET get_user_info (query user_id совпадает с токеном); дублирующий get_settings удалён. PATCH update_settings принимает first_name, last_name, middle_name и avatar_id. DELETE delete_account проверяет текущий пароль, устанавливает is_active=false и отзывает все сессии. Email отображается, но не редактируется. Password_hash и права принимать через этот метод запрещено.',
'', '## Сводный список','', '| Метод | Путь | Назначение |','|---|---|---|']
plain=[]
names={}
for line in (root/'API_DESCRIPTION.md').read_text(encoding='utf-8').splitlines():
 cols=[x.strip() for x in line.split('|')]
 if len(cols)>5 and cols[2].startswith('`') and cols[3].startswith('`/'):
  names[(cols[2].strip('`'),cols[3].strip('`'))]=cols[4]

for path,ops in spec['paths'].items():
 for verb,op in ops.items():
  if verb not in ('get','post','patch','delete','put'):continue
  summary=op.get('summary','');rows.append(f'| {verb.upper()} | `{path}` | {summary} |');plain.append(f'{verb.upper()} {path} — {names.get((verb.upper(),path),summary)}')
for path,ops in spec['paths'].items():
 for verb,op in ops.items():
  if verb not in ('get','post','patch','delete','put'):continue
  rows += ['',f'## {verb.upper()} {path}','',op.get('description',op.get('summary','')),'']
  params=op.get('parameters',[])
  if params:
   rows+=['| Параметр | Где | Тип | Обязателен |','|---|---|---|---|']
   for p in params:rows.append(f'| `{p["name"]}` | {p["in"]} | {typename(p["schema"])} | {"Да" if p.get("required") else "Нет"} |')
  body=op.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema')
  if body:
   schema=resolved(body);rows += ['','Поля JSON:','','| Поле | Тип | Обязательно | Описание |','|---|---|---|---|']
   for k,v in schema.get('properties',{}).items():rows.append(f'| `{k}` | {typename(v)} | {"Да" if k in schema.get("required",[]) else "Нет"} | {v.get("description","")} |')
   rows+=['','Пример тела запроса:','','```json',json.dumps(example(body),ensure_ascii=False,indent=2),'```']
  else:rows+=['','JSON-тело не передаётся.']
  for code,response in op['responses'].items():
   if not code.startswith('2'):continue
   rs=response.get('content',{}).get('application/json',{}).get('schema')
   rows+=['',f'Успешный ответ: HTTP {code}.']
   if rs: rows+=['', 'Схема ответа: `'+typename(rs)+'`.']
   if rs and (rs.get('$ref') or resolved(rs).get('properties') or resolved(rs).get('type')=='array'):rows+=['','Пример формы ответа (синтетический):','','```json',json.dumps(example(rs),ensure_ascii=False,indent=2),'```']
   elif rs:rows+=['','Ответ этого существующего маршрута пока типизирован как произвольный JSON-объект. Точный набор полей требует отдельной публичной response-модели; не считать `{}` полным согласованным контрактом.']
  rows+=['','Ошибки: 401 — нет/недействителен токен; 403 — нет доступа; 404 — объект не найден; 422 — неверные входные данные. Для завершения загрузки и повторной сдачи также возможен 409. Для S3 без конфигурации — 503. Конкретные применимые ошибки описаны в обработчиках.']
(root/'API_CONTRACT_REVIEW.md').write_text(encoding='utf-8', data='\n'.join(rows)+'\n')
(root/'docs/ENDPOINTS.txt').write_text(encoding='utf-8', data='АКТУАЛЬНЫЕ МАРШРУТЫ ЛОКАЛЬНОЙ КОПИИ API — 04.11.2026\n\n'+ '\n'.join(plain)+'\n\nПодробные типы и примеры: API_CONTRACT_REVIEW.md. Ветка: feature/api-contract-review.\n')
print(len(plain),'HTTP operations exported')

index=['# API Pocket LMS — 04.11.2026','',
'Текущий контракт: feature/api-contract-review. Точные схемы и примеры — [API_CONTRACT_REVIEW.md](API_CONTRACT_REVIEW.md), OpenAPI — [openapi.json](openapi.json). Решения аналитиков — [docs/API_REVIEW_2026-11-04.md](docs/API_REVIEW_2026-11-04.md).',
'', 'GET /get_courses, /get_modules, /get_assignments, /get_groups, /get_members, /get_team_members и /get_grades возвращают массивы. Материалы и сдачи сохраняют MaterialsResponse/SubmissionsResponse с items.',
'', 'Публичное обновление профиля: first_name, last_name, middle_name, avatar_id. Email/SMTP отложены. Самостоятельное удаление — DELETE /delete_account с current_password. При регистрации действует список российских почтовых сервисов.',
'', 'GET /get_course_data возвращает карточку без материалов и инвайт-кода. GET /get_module_data возвращает поля ModuleResponse и disciplines без инвайт-кодов. Создание курса требует draft/published, код генерирует сервер. Приглашения создаются отдельно с ролью и областью.',
'', 'GET /app отдаёт frontend/dist/index.html как text/html. Пока сборки нет — 503. Для размещения frontend и API на одном origin CORS между ними не требуется. Это опциональная раздача сборки; frontend ещё не реализован.',
'', '| Метод | Путь | Назначение | Успешный ответ |','|---|---|---|---|']
for path,ops in spec['paths'].items():
 for verb,op in ops.items():
  if verb not in ('get','post','patch','delete','put'):continue
  successes=[]
  for status,res in op['responses'].items():
   if status.startswith('2'):
    schema=res.get('content',{}).get('application/json',{}).get('schema')
    successes.append(status+' '+(typename(schema) if schema else 'text/html'))
  index.append('| '+verb.upper()+' | `'+path+'` | '+op.get('summary','')+' | '+', '.join(successes)+' |')
(root/'API_DESCRIPTION.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
