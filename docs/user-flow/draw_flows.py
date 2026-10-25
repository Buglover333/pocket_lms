from pathlib import Path
import html, json, textwrap

OUT=Path(__file__).resolve().parent
W=2560
C={'ink':'#17334b','muted':'#617489','line':'#8495a4','mint':'#effbf8','mintstroke':'#76c5b5','violet':'#7655bd','violetfill':'#f3edff','get':'#1879b9','post':'#16866c','patch':'#b77713','warn':'#936319','warnbg':'#fff8e8'}
E=lambda x:html.escape(str(x),quote=True)
class Drawing:
 def __init__(self,h,title,subtitle):
  self.h=h;self.parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{E(title)}">',
   '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#8495a4"/></marker></defs>',
   f'<rect width="{W}" height="{h}" fill="#ffffff"/>',f'<rect width="{W}" height="145" fill="#102b43"/>']
  self.text(60,66,title,43,'#ffffff',700)
  self.text(60,111,subtitle,23,'#c7dbe8')
  self.nodes=[]
 def text(self,x,y,s,size=24,color=None,weight=400,anchor='start',mono=False):
  font='Menlo,DejaVu Sans Mono,monospace' if mono else 'Arial,DejaVu Sans,sans-serif'
  self.parts.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{color or C["ink"]}" text-anchor="{anchor}">{E(s)}</text>')
 def lines(self,x,y,text,width,size=22,color=None,lineh=None):
  if not text:return y
  n=max(10,int(width/(size*.57)));lineh=lineh or size*1.38
  for paragraph in text.split('\n'):
   for line in textwrap.wrap(paragraph,n,break_long_words=False,break_on_hyphens=False) or ['']:
    self.text(x,y,line,size,color);y+=lineh
  return y
 def rect(self,x,y,w,h,fill,stroke='none',rx=18,dash=False):
  self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"'+(' stroke-dasharray="10 7"' if dash else '')+'/>')
 def path(self,pts,label=None,lx=None,ly=None,arrow=True,dash=False):
  d='M'+' L'.join(f'{x},{y}' for x,y in pts)
  self.parts.append(f'<path d="{d}" fill="none" stroke="{C["line"]}" stroke-width="3" stroke-linejoin="round"'+(' marker-end="url(#arr)"' if arrow else '')+(' stroke-dasharray="8 6"' if dash else '')+'/>')
  if label:self.text(lx if lx is not None else (pts[0][0]+pts[-1][0])/2,ly if ly is not None else pts[0][1]-12,label,20,C['muted'],500,anchor='middle')
 def chip(self,x,y,method,path,w):
  col=C.get(method.lower(),C['muted']);self.rect(x,y,w,35,'#ffffff','#dce7e9',7)
  bw=96 if method=='PATCH' else 80
  self.rect(x+5,y+5,bw,25,col,rx=5)
  self.text(x+5+bw/2,y+24,method,16,'white',700,'middle')
  self.text(x+bw+19,y+25,path,21,C['ink'],400,mono=True)
 def node(self,id,x,y,w,h,title,apis=(),note='',kind='normal'):
  self.nodes.append(dict(id=id,x=x,y=y,w=w,h=h,title=title,apis=list(apis),note=note))
  fill=C['mint'] if kind=='normal' else ('#f1f6fb' if kind=='external' else '#fff4ef')
  stroke=C['mintstroke'] if kind=='normal' else ('#b4c6d5' if kind=='external' else '#d9957b')
  self.parts.append(f'<g id="{id}" data-node="{id}"><title>{E(title+". "+note)}</title>')
  self.rect(x,y,w,h,fill,stroke)
  # Reserve two title lines in every card so badges align across a row.
  lines=textwrap.wrap(title,max(12,int((w-40)/(29*.57))),break_long_words=False)
  for i,line in enumerate(lines[:2]):self.text(x+23,y+38+i*34,line,29,weight=700)
  api_y=y+88
  for method,path in apis:
   self.chip(x+20,api_y,method,path,w-40);api_y+=43
  note_y=max(y+103,api_y+19)
  end=self.lines(x+23,note_y,note,w-46,size=21,color=C['muted'])
  if end>y+h+4:raise ValueError(f'Content overflow: {id}, {end} > {y+h}')
  self.parts.append('</g>')
 def diamond(self,x,y,w,h,label):
  self.parts.append(f'<path d="M{x-w/2},{y} L{x},{y-h/2} L{x+w/2},{y} L{x},{y+h/2} Z" fill="{C["violetfill"]}" stroke="{C["violet"]}" stroke-width="3"/>')
  lines=label.split('\n')
  for i,line in enumerate(lines):self.text(x,y-(len(lines)-1)*15+i*30+8,line,24,C['violet'],700,'middle')
 def heading(self,y,s):self.text(270,y,s,29,C['ink'],700)
 def legend(self,y):
  x=65
  for method,label in [('GET','чтение'),('POST','отправка / создание'),('PATCH','изменение')]:
   col=C[method.lower()];self.rect(x,y-23,100,31,col,rx=7);self.text(x+50,y,method,17,'white',700,'middle');self.text(x+114,y,label,21,C['muted']);x+=440 if method=='POST' else 330
 def footer(self,y):
  self.text(60,y,'API ветки endpoints · 25.10.2026 · S3 требует проверки на реальном хранилище',20,C['muted'])
 def save(self,name):
  self.parts.append('</svg>');(OUT/(name+'.svg')).write_text(''.join(self.parts));(OUT/(name+'.json')).write_text(json.dumps(self.nodes,ensure_ascii=False,indent=2))

def nav(d,role):
 d.legend(186)
 d.node(role+'-auth',70,245,450,260,'Войти / зарегистрироваться',[('POST','/auth'),('POST','/register')], 'Регистрация — при первом входе.')
 d.node(role+'-home',650,245,490,260,'Главная страница',[('GET','/get_courses'),('GET','/get_modules')],'При действующей сессии начинаем здесь. Отдельного dashboard нет.')
 d.node(role+'-open',1270,245,650,260,'Открыть модуль / курс',[('GET','/get_module_data'),('GET','/get_course_data')],'Модуль открывается при необходимости; затем выбирается курс.')
 d.path([(520,355),(650,355)]);d.path([(1140,355),(1270,355)])
 d.diamond(2220,355,280,180,'Выбрать\nдействие')
 d.path([(1920,355),(2080,355)])
 d.path([(2220,445),(2220,510),(100,510)],arrow=False)

# 01 — teacher
D=Drawing(3650,'01  Преподаватель · юзер-флоу + эндпоинты','Актуальные запросы подписаны прямо у действий. Развилки и параллельные разделы не требуют выполнять все шаги подряд.')
nav(D,'t');D.path([(100,510),(100,2785)],arrow=False)
xs=[270,1010,1750];cw=620
for y,label in [(625,'01 · Создание и редактирование структуры'),(1035,'02 · Учебные материалы'),(1445,'03 · Задания')]:
 D.heading(y-36,label);D.path([(100,y+135),(270,y+135)])
 for i in (0,1):D.path([(xs[i]+cw,y+135),(xs[i+1],y+135)])
D.path([(100,550),(1320,550),(1320,625)],'Редактировать существующий',900,540)
D.node('t-structure-create',270,625,cw,300,'Создать модуль или курс',[('POST','/create_module'),('POST','/create_course')],'Альтернативы: выбирается нужный объект.')
D.node('t-structure-read',1010,625,cw,300,'Получить данные перед правкой',[('GET','/get_module_data'),('GET','/get_course_data')],'Открыть соответствующий объект. GET не изменяет его.')
D.node('t-structure-edit',1750,625,cw,300,'Сохранить изменения',[('PATCH','/update_module'),('PATCH','/update_course')],'Для публикации курса: status=published. У модуля отдельного статуса публикации нет.')
D.node('t-material-open',270,1035,cw,310,'Открыть или создать материал',[('GET','/get_materials'),('GET','/get_material_data'),('POST','/create_material')],'При создании черновика передать is_published=false.')
D.node('t-material-edit',1010,1035,cw,310,'Изменить содержание',[('PATCH','/update_material')],'Содержание и параметры материала. Вложения — по схеме 03 «Файлы и S3».')
D.node('t-material-publish',1750,1035,cw,310,'Опубликовать или скрыть',[('PATCH','/update_material')],'is_published=true — опубликовать; false — скрыть. Чтение опубликованного: GET /get_materials.')
D.node('t-assignment-open',270,1445,cw,310,'Открыть или создать задание',[('GET','/get_assignments'),('GET','/get_assignment_data'),('POST','/create_assignment')],'GET — список и детали; POST — создание. Черновик: is_published=false.')
D.node('t-assignment-edit',1010,1445,cw,310,'Уточнить задание',[('PATCH','/update_assignment')],'Описание, максимальный балл и due_date. Персональные назначения ещё не подключены к HTTP-запросу.')
D.node('t-assignment-publish',1750,1445,cw,310,'Опубликовать или скрыть',[('PATCH','/update_assignment')],'is_published=true / false. GET /get_assignments показывает доступные студенту задания.')
D.heading(1815,'04 · Приглашение в курс — последний шаг выполняет студент')
D.path([(100,1985),(270,1985)])
D.node('t-members',270,1855,cw,260,'Посмотреть участников',[('GET','/get_members')],'Профили участников своего курса; также источник данных для раздела «Контакты».')
D.node('t-invite',1010,1855,cw,260,'Получить приглашение',[('POST','/create_invitation')],'Код и ссылка курса. Копирование ссылки выполняет интерфейс, без нового запроса.')
D.node('t-invite-accept',1750,1855,cw,260,'Студент: присоединиться',[('POST','/accept_invitation')],'Получатель приглашения входит в аккаунт и отправляет код. Текущая роль присоединения — student.',kind='external')
D.path([(890,1985),(1010,1985)]);D.path([(1630,1985),(1750,1985)])
D.heading(2205,'05 · Проверка работ выбранного студента')
D.path([(100,2370),(270,2370)])
D.node('t-submissions',270,2245,600,250,'Выбрать студента и задание',[('GET','/get_submissions')],'assignment_id + student_id. По умолчанию запрос возвращает свои сдачи; преподаватель выбирает студента своего курса.')
D.node('t-submission',960,2245,600,250,'Открыть сдачу и вложения',[('GET','/get_submission_data'),('GET','/get_file_download')],'Второй запрос нужен при скачивании файла. Проверяется доступ к работе.')
D.path([(870,2370),(960,2370)]);D.path([(1560,2370),(1630,2370)])
D.diamond(1710,2370,160,150,'Принять?')
D.node('t-grade',1890,2200,600,200,'Выставить балл и комментарий',[('POST','/grade_submission')],'Балл не выше max_score.')
D.node('t-return',1890,2415,600,200,'Вернуть на доработку',[('POST','/return_submission')],'Студент исправляет работу — схема 02.')
D.path([(1790,2370),(1835,2370),(1835,2285),(1890,2285)],'Да',1835,2250)
D.path([(1710,2445),(1710,2500),(1890,2500)],'Нет',1785,2482)
D.text(270,2640,'Командная сдача, оценка и обратная связь доступны активным участникам соответствующей команды.',22,C['muted'])
D.heading(2730,'06 · Другие разделы — независимые ветки меню')
D.path([(100,2785),(2170,2785)],arrow=False)
menu=[(270,'t-calendar','Календарь',[('GET','/get_calendar')],'Дедлайны course_id. Для нескольких курсов запрос повторяется.'),
      (820,'t-grades','Баллы студента',[('GET','/get_grades')],'Оценки по заданиям и попыткам. Выбор чужого студента доступен преподавателю его курса.'),
      (1370,'t-teams','Команды курса',[('GET','/get_groups'),('POST','/create_group'),('PATCH','/update_group'),('GET','/get_team_members')],'PATCH меняет имя и описание; состав пока только просматривается.'),
      (1920,'t-profile','Мой профиль',[('GET','/get_user_info'),('PATCH','/update_settings')],'user_id совпадает с токеном. Менять имя и фамилию; email — только чтение.')]
for x,id,title,apis,note in menu:
 D.path([(x+250,2785),(x+250,2830)]);D.node(id,x,2830,500,390,title,apis,note)
D.rect(60,3285,2440,220,C['warnbg'],'#dfc285',16,True)
D.text(90,3328,'Ещё требует реализации / согласования',29,C['warn'],700)
D.lines(90,3371,'Публикация по таймеру; получатели материалов; HTTP-управление назначениями и составом команд; приглашение преподавателя и приглашение в модуль; итоговая оценка и статистика; расширенные поля учебного плана.',2340,23,C['warn'])
D.text(90,3464,'Эти функции не помечены выдуманными «готовыми» эндпоинтами. Полная сверка находится в отчёте по БД.',22,C['warn'])
D.footer(3610);D.save('01-teacher-flow-v3')

# 02 — student
D=Drawing(2770,'02  Студент · юзер-флоу + эндпоинты','Доступ — по текущему аккаунту и участию в курсе. Выполнение задания и раскрытие меню сами по себе не требуют API.')
nav(D,'s');D.path([(100,510),(100,2225)],arrow=False)
D.heading(610,'01 · Изучить материал')
D.path([(100,785),(270,785)])
D.node('s-material-list',270,650,620,300,'Открыть список материалов',[('GET','/get_materials')],'Видны опубликованные материалы доступного курса.')
D.node('s-material-read',1010,650,620,300,'Прочитать выбранный материал',[('GET','/get_material_data')],'Содержание и метаданные вложений.')
D.node('s-material-download',1750,650,620,300,'Открыть вложение, если есть',[('GET','/get_file_download')],'После проверки доступа выдаётся ссылка на скачивание. S3-файлы — схема 03.')
D.path([(890,785),(1010,785)]);D.path([(1630,785),(1750,785)])
D.heading(1030,'02 · Выполнить и сдать задание')
D.path([(100,1205),(270,1205)])
D.node('s-assignment',270,1070,620,300,'Выбрать задание',[('GET','/get_assignments'),('GET','/get_assignment_data')],'Из списка или ближайшего дедлайна открываются те же детали задания.')
D.node('s-work',1010,1070,620,300,'Выполнить работу',[],'Подготовить ответ, ссылки или файлы. Само выполнение задания не вызывает отдельный эндпоинт.')
D.node('s-files',1750,1070,620,300,'Подготовить файлы, если есть',[('POST','/create_file_upload'),('POST','/complete_file_upload')],'Между запросами файл отправляется в S3. После подтверждения получаем готовые file_ids; см. схему 03.')
D.path([(890,1205),(1010,1205)]);D.path([(1630,1205),(1750,1205)])
D.node('s-submit',1750,1460,620,260,'Сдать работу',[('POST','/submit_work')],'assignment_id, submitted_by, answer_text, file_ids. Владелец и доступ проверяются сервером.')
D.node('s-feedback',1010,1460,620,260,'Открыть статус и обратную связь',[('GET','/get_submission_data')],'Статус, оценка, комментарий преподавателя. До проверки оценка может отсутствовать.')
D.path([(2060,1370),(2060,1460)]);D.path([(1750,1572),(1630,1572)])
D.path([(1320,1370),(1320,1410),(2060,1410)],'Без файлов',1710,1400,arrow=False)
D.diamond(550,1572,260,180,'Работа\nвозвращена?')
D.path([(1010,1572),(680,1572)])
D.node('s-result',270,1830,620,260,'Посмотреть статус и баллы',[('GET','/get_grades')],'Если оценка ещё не выставлена — ожидаем проверки. Само отсутствие возврата не означает, что работа принята.')
D.node('s-resubmit',1010,1830,620,260,'Исправить и отправить повторно',[('POST','/resubmit_work')],'Для своей draft/returned работы. Новые файлы сначала загрузить по схеме 03, затем передать file_ids.')
D.path([(420,1572),(220,1572),(220,1945),(270,1945)],'Нет',315,1548)
D.path([(550,1662),(550,1765),(1320,1765),(1320,1830)],'Да',900,1748)
D.path([(1630,1945),(1690,1945),(1690,1572),(1630,1572)],'Повторная проверка',1880,1780)
D.heading(2180,'03 · Другие разделы — независимые ветки меню')
D.path([(100,2225),(2170,2225)],arrow=False)
menu=[(270,'s-calendar','Календарь',[('GET','/get_calendar')],'Дедлайны по курсу. Задание из календаря открывает get_assignment_data.'),
      (820,'s-submissions','Мои работы',[('GET','/get_submissions')],'assignment_id обязателен. Возвращаются свои сдачи и доступная командная работа.'),
      (1370,'s-contacts','Контакты',[('GET','/get_members')],'Профили участников доступного курса. Группировка по курсам — в интерфейсе.'),
      (1920,'s-profile','Мой профиль',[('GET','/get_user_info'),('PATCH','/update_settings')],'user_id совпадает с токеном. Имя и фамилия редактируются; email отображается.')]
for x,id,title,apis,note in menu:
 D.path([(x+250,2225),(x+250,2270)]);D.node(id,x,2270,500,300,title,apis,note)
D.rect(60,2630,2440,75,C['warnbg'],'#dfc285',12,True)
D.text(90,2675,'Отдельная итоговая оценка курса и формула её расчёта пока не реализованы. get_grades возвращает оценки по заданиям / попыткам.',22,C['warn'])
D.footer(2740);D.save('02-student-flow-v3')

# 03 — S3 shared flow
D=Drawing(1660,'03  Файлы и S3 · общий сценарий','Пользователь видит «прикрепить» и «скачать». Ниже — точные запросы интерфейса, сервера LMS и хранилища.')
D.legend(186);D.heading(285,'01 · Загрузка файла')
D.node('f-init',70,330,510,310,'Подготовить загрузку в LMS',[('POST','/create_file_upload')],'JSON: имя, тип, MIME и размер. Сервер возвращает file_id, upload_url и fields. Ключ S3 назначает сервер.')
D.node('f-transfer',700,330,510,310,'Отправить файл в хранилище',[],'POST → S3 напрямую. multipart/form-data: выданные fields + бинарный file. Это не эндпоинт LMS.',kind='external')
D.node('f-confirm',1330,330,510,310,'Подтвердить загрузку в LMS',[('POST','/complete_file_upload')],'file_id. Сервер проверяет объект через S3 HEAD: размер и MIME. Только затем файл становится ready.')
D.node('f-attach',1960,330,530,310,'Использовать готовый file_id',[],'Для сдачи: file_ids в submit_work / resubmit_work. Для материала: lesson_id указывается при подготовке загрузки.')
for a,b in [(580,700),(1210,1330),(1840,1960)]:D.path([(a,485),(b,485)])
D.heading(780,'02 · Скачивание файла')
D.node('f-request',70,825,540,280,'Запросить доступ к файлу',[('GET','/get_file_download')],'file_id. Пользователь должен иметь доступ к материалу или сдаче, к которым относится файл.')
D.diamond(980,965,320,220,'Доступ\nразрешён?')
D.path([(610,965),(820,965)])
D.node('f-url',1330,825,510,280,'Получить временную ссылку',[],'Внутри get_file_download сервер создаёт подписанную ссылку S3. Срок действия — 300 секунд. Отдельного нового вызова LMS нет.')
D.node('f-download',1960,825,530,280,'Скачать объект из S3',[],'GET → S3 по полученной ссылке. Это обращение к хранилищу, а не ещё один эндпоинт LMS.',kind='external')
D.path([(1140,965),(1330,965)],'Да',1230,945);D.path([(1840,965),(1960,965)])
D.node('f-deny',700,1200,560,155,'Отказать в доступе',[],'HTTP 403. Ссылка не выдаётся.',kind='deny')
D.path([(980,1075),(980,1200)],'Нет',1040,1145)
D.rect(60,1430,2440,125,'#f1f6fb','#c2d1dc',14)
D.text(90,1473,'Дополнительные операции',27,weight=700)
D.text(90,1515,'GET /get_file — метаданные. POST /upload_file — регистрация внешней HTTP-ссылки; этот запрос не загружает байты в S3.',23,C['muted'])
D.footer(1620);D.save('03-files-s3-flow-v3')
print('Three exact SVG diagrams generated')
