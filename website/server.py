"""Portable WSGI site + lead delivery. No third-party runtime dependencies in preview."""
from pathlib import Path
import os,json,sqlite3,time,secrets,hmac,hashlib,base64,re,ssl,smtplib,mimetypes,html,argparse,threading
from urllib.parse import urlsplit,unquote
from email.message import EmailMessage
from wsgiref.simple_server import make_server,WSGIServer,WSGIRequestHandler
from socketserver import ThreadingMixIn
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parent
def read_env():
 p=ROOT/'.env'
 if p.exists():
  for line in p.read_text(encoding='utf-8-sig').splitlines():
   if line.strip() and not line.lstrip().startswith('#') and '=' in line:
    k,v=line.split('=',1);os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))
read_env()
MODE=os.getenv('APP_MODE','preview')
PORT=int(os.getenv('PORT','8766'))
SITE=os.getenv('SITE_URL',f'http://127.0.0.1:{PORT}').rstrip('/')
DATA=Path(os.getenv('DATA_DIR',str(ROOT/'data'))).resolve();DATA.mkdir(parents=True,exist_ok=True)
SECRET=os.getenv('FORM_SECRET') or secrets.token_hex(32)
MAX_BODY=15*1024*1024
MAX_FILES=10*1024*1024
EMAIL='obogrevsistem@yandex.ru'
@contextmanager
def db():
 con=sqlite3.connect(DATA/'leads.sqlite3',timeout=30)
 con.row_factory=sqlite3.Row
 try:
  with con:yield con
 finally:con.close()
with db() as con:
 con.execute('CREATE TABLE IF NOT EXISTS leads (id TEXT PRIMARY KEY, created REAL, status TEXT, payload TEXT, ip_hash TEXT, last_error TEXT)')
 con.execute('CREATE INDEX IF NOT EXISTS leads_created ON leads(created)')
if MODE=='production':
 missing=[k for k in ['SMTP_USER','SMTP_PASSWORD','FORM_SECRET','LEGAL_OPERATOR','LEGAL_ADDRESS','SITE_URL'] if not os.getenv(k)]
 if missing:raise RuntimeError('Production configuration missing: '+', '.join(missing))
 if not SITE.startswith('https://'):raise RuntimeError('Production SITE_URL must use HTTPS')
 if os.getenv('LEGAL_APPROVED')!='1':raise RuntimeError('Finalize privacy/consent pages, then set LEGAL_APPROVED=1')
 if 'должны быть уточнены' in (ROOT/'public/privacy/index.html').read_text(encoding='utf-8') or 'должны быть уточнены' in (ROOT/'public/consent/index.html').read_text(encoding='utf-8'):
  raise RuntimeError('Privacy and consent still contain draft retention terms; finish legal copy in build.py and rebuild')

def token():
 nonce=f'{int(time.time())}.{secrets.token_hex(16)}'
 return nonce+'.'+hmac.new(SECRET.encode(),nonce.encode(),hashlib.sha256).hexdigest()
def valid_token(value,cookie):
 try:
  stamp,nonce,sig=value.split('.')
  expected=hmac.new(SECRET.encode(),f'{stamp}.{nonce}'.encode(),hashlib.sha256).hexdigest()
  return 0<=time.time()-int(stamp)<7200 and hmac.compare_digest(sig,expected) and hmac.compare_digest(value,cookie)
 except (ValueError,TypeError):return False
def send_email(lead,attachments):
 msg=EmailMessage();msg['Subject']='Заявка с сайта: '+lead['topic'][:100]
 msg['From']=os.getenv('SMTP_USER',EMAIL);msg['To']=EMAIL
 if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',lead['contact']):msg['Reply-To']=lead['contact']
 rows=[('Номер',lead['id']),('Контакт',lead['contact']),('Имя',lead['name']),('Город',lead['city']),('Тема',lead['topic']),('Задача',lead['message']),('Страница',lead['page']),('Согласие','Принято; редакция 2026-10-09'),('Метки',json.dumps(lead['attribution'],ensure_ascii=False))]
 msg.set_content('\n\n'.join(k+': '+v for k,v in rows))
 for a in attachments:
  main,sub=a['mime'].split('/',1);msg.add_attachment(a['bytes'],maintype=main,subtype=sub,filename=a['name'])
 if MODE=='preview':
  folder=DATA/'preview-mail';folder.mkdir(exist_ok=True);(folder/(lead['id']+'.eml')).write_bytes(msg.as_bytes());return
 host=os.getenv('SMTP_HOST','smtp.yandex.ru');port=int(os.getenv('SMTP_PORT','465'))
 context=ssl.create_default_context()
 if port==465:
  smtp=smtplib.SMTP_SSL(host,port,timeout=25,context=context)
 else:
  smtp=smtplib.SMTP(host,port,timeout=25);smtp.ehlo();smtp.starttls(context=context);smtp.ehlo()
 with smtp:
  smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);smtp.send_message(msg)

class Invalid(Exception):pass
def validate(payload):
 if not isinstance(payload,dict):raise Invalid('Некорректные данные формы.')
 if payload.get('website'):raise Invalid('Не удалось принять форму. Свяжитесь с нами по телефону.')
 if payload.get('consent') is not True:raise Invalid('Для отправки нужно согласие на обработку данных.')
 fields={}
 for key,limit in [('contact',150),('name',100),('city',100),('message',4000),('topic',160),('page',250)]:
  val=payload.get(key,'')
  if not isinstance(val,str) or len(val)>limit:raise Invalid('Проверьте длину полей.')
  fields[key]=val.strip().replace('\r','')
 contact=fields['contact']
 if '\n' in contact or not (re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',contact) or (re.fullmatch(r'[+\d()\s-]+',contact) and 10<=len(re.sub(r'\D','',contact))<=15)):
  raise Invalid('Укажите корректный телефон или email.')
 if any('\n' in fields[k] for k in ['topic','name','city']):raise Invalid('Проверьте поля формы.')
 if not fields['page'].startswith('/') or '?' in fields['page']:raise Invalid('Некорректный адрес страницы.')
 key=payload.get('id','')
 if not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9-]{20,50}',key):raise Invalid('Обновите страницу и попробуйте ещё раз.')
 fields['id']=key
 attribution=payload.get('attribution',{})
 if not isinstance(attribution,dict):raise Invalid('Некорректные рекламные метки.')
 fields['attribution']={k:str(attribution.get(k,''))[:200] for k in ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','yclid','client_id'] if attribution.get(k)}
 files=payload.get('files',[])
 if not isinstance(files,list) or len(files)>3:raise Invalid('Можно приложить не более 3 файлов.')
 attachments=[];total=0
 types={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.dwg':'application/acad'}
 for f in files:
  if not isinstance(f,dict) or not isinstance(f.get('name'),str) or not isinstance(f.get('data'),str):raise Invalid('Не удалось прочитать вложение.')
  name=Path(f['name'].replace('\\','/')).name[:120];ext=Path(name).suffix.lower()
  if ext not in types:raise Invalid('Неподдерживаемый формат вложения.')
  try:raw=base64.b64decode(f['data'],validate=True)
  except (ValueError,TypeError):raise Invalid('Повреждённое вложение.')
  total+=len(raw)
  if total>MAX_FILES or not raw:raise Invalid('Суммарный размер файлов — до 10 МБ.')
  signatures={'.pdf':raw.startswith(b'%PDF-'),'.jpg':raw.startswith(b'\xff\xd8'),'.jpeg':raw.startswith(b'\xff\xd8'),'.png':raw.startswith(b'\x89PNG\r\n\x1a\n'),'.webp':raw.startswith(b'RIFF') and raw[8:12]==b'WEBP','.docx':raw.startswith(b'PK\x03\x04'),'.xlsx':raw.startswith(b'PK\x03\x04'),'.dwg':raw.startswith(b'AC10')}
  if not signatures[ext]:raise Invalid('Содержимое файла не соответствует его расширению.')
  attachments.append({'name':name,'mime':types[ext],'bytes':raw})
 return fields,attachments

def app(environ,start_response):
 path=unquote(environ.get('PATH_INFO','/'));method=environ['REQUEST_METHOD']
 def respond(code,body,ctype='application/json; charset=utf-8',extra=()):
  if isinstance(body,dict):body=json.dumps(body,ensure_ascii=False).encode()
  elif isinstance(body,str):body=body.encode()
  headers=[('Content-Type',ctype),('Content-Length',str(len(body))),('X-Content-Type-Options','nosniff'),('Referrer-Policy','strict-origin-when-cross-origin'),('X-Frame-Options','DENY'),('Permissions-Policy','camera=(), microphone=(), geolocation=()'),('Content-Security-Policy',"default-src 'self'; script-src 'self' https://mc.yandex.ru https://mc.yandex.com; connect-src 'self' https://*.yandex.ru https://*.yandex.com; img-src 'self' data: https://*.yandex.ru https://*.yandex.com; style-src 'self'; font-src 'self'; frame-src https://mc.yandex.ru https://mc.yandex.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")]+list(extra)
  if path.startswith('/api/'):headers.append(('Cache-Control','no-store'))
  if MODE!='production':headers.append(('X-Robots-Tag','noindex, nofollow'))
  start_response(f'{code} '+{200:'OK',201:'Created',204:'No Content',301:'Moved Permanently',400:'Bad Request',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',409:'Conflict',413:'Content Too Large',415:'Unsupported Media Type',429:'Too Many Requests',500:'Internal Server Error',502:'Bad Gateway'}.get(code,'Error'),headers)
  return [b'' if method=='HEAD' else body]
 try:
  if path=='/api/config' and method=='GET':
   cookie=dict(x.strip().split('=',1) for x in environ.get('HTTP_COOKIE','').split(';') if '=' in x)
   old=cookie.get('form_session','')
   t=old if valid_token(old,old) else token()
   counter=os.getenv('METRIKA_ID','') if MODE=='production' else ''
   return respond(200,{'csrf':t,'preview':MODE=='preview','metrika':counter if counter.isdigit() else None},extra=[('Set-Cookie',f'form_session={t}; Path=/; HttpOnly; SameSite=Strict; Max-Age=7200'+('; Secure' if MODE=='production' else ''))])
  if path=='/api/leads' and method=='POST':
   if environ.get('HTTP_ORIGIN')!=SITE:return respond(403,{'error':'Недопустимый источник отправки. Обновите страницу.'})
   cookie=dict(x.strip().split('=',1) for x in environ.get('HTTP_COOKIE','').split(';') if '=' in x)
   if not valid_token(environ.get('HTTP_X_CSRF_TOKEN',''),cookie.get('form_session','')):return respond(403,{'error':'Сессия формы истекла. Обновите страницу и отправьте ещё раз.'})
   if environ.get('CONTENT_TYPE','').split(';')[0]!='application/json':return respond(415,{'error':'Неподдерживаемый формат запроса.'})
   try:size=int(environ.get('CONTENT_LENGTH','0'))
   except ValueError:size=0
   if size<=0 or size>MAX_BODY:return respond(413,{'error':'Слишком большой запрос. Файлы суммарно — до 10 МБ.'})
   try:payload=json.loads(environ['wsgi.input'].read(size))
   except (ValueError,UnicodeError):return respond(400,{'error':'Не удалось прочитать форму.'})
   try:lead,attachments=validate(payload)
   except Invalid as e:return respond(400,{'error':str(e)})
   ip=environ.get('REMOTE_ADDR','')
   if os.getenv('TRUST_PROXY')=='1':ip=environ.get('HTTP_X_REAL_IP',ip)
   ip_hash=hmac.new(SECRET.encode(),ip.encode(),hashlib.sha256).hexdigest()
   with db() as con:
    con.execute('BEGIN IMMEDIATE')
    existing=con.execute('SELECT status FROM leads WHERE id=?',(lead['id'],)).fetchone()
    if existing:
     if existing['status'] in ('sent','preview'):return respond(200,{'ok':True,'preview':existing['status']=='preview','id':lead['id']})
     return respond(409,{'error':'Обращение уже сохранено, но отправка не подтверждена. Свяжитесь с нами по телефону, чтобы уточнить получение.'})
    count=con.execute('SELECT count(*) FROM leads WHERE ip_hash=? AND created>?',(ip_hash,time.time()-600)).fetchone()[0]
    if count>=5:return respond(429,{'error':'Слишком много обращений. Попробуйте через 10 минут или позвоните нам.'},extra=[('Retry-After','600')])
    con.execute('INSERT INTO leads VALUES (?,?,?,?,?,?)',(lead['id'],time.time(),'pending',json.dumps(lead,ensure_ascii=False),ip_hash,''))
   try:
    folder=DATA/'attachments'/lead['id'];folder.mkdir(parents=True,exist_ok=True)
    for i,a in enumerate(attachments):(folder/(str(i+1)+'_'+a['name'])).write_bytes(a['bytes'])
    send_email(lead,attachments)
   except Exception as e:
    with db() as con:con.execute('UPDATE leads SET status=?,last_error=? WHERE id=?',('failed',type(e).__name__,lead['id']))
    return respond(502,{'error':'Не удалось подтвердить отправку письма. Пожалуйста, позвоните +7 930 175 50 00 или напишите на obogrevsistem@yandex.ru.'})
   with db() as con:con.execute('UPDATE leads SET status=? WHERE id=?',('preview' if MODE=='preview' else 'sent',lead['id']))
   return respond(201,{'ok':True,'preview':MODE=='preview','id':lead['id']})
  if path.startswith('/api/'):return respond(405 if path in ['/api/config','/api/leads'] else 404,{'error':'Запрос не поддерживается.'})
  if method not in ('GET','HEAD'):return respond(405,'Метод не поддерживается','text/plain; charset=utf-8')
  if path=='/robots.txt':return respond(200,'User-agent: *\n'+('Disallow: /\n' if MODE!='production' else 'Disallow: /api/\nDisallow: /spasibo/\nSitemap: '+SITE+'/sitemap.xml\n'),'text/plain; charset=utf-8')
  if path=='/sitemap.xml':
   routes=json.loads((ROOT/'routes.json').read_text(encoding='utf-8'))
   xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+html.escape(SITE+r['path'])+'</loc></url>' for r in routes if r['path'] not in ['/404/','/spasibo/','/consent/'])+'</urlset>'
   return respond(200,xml,'application/xml; charset=utf-8')
  public=ROOT/'public';target=(public/path.lstrip('/')).resolve()
  if not target.is_relative_to(public) or any(p.startswith('.') for p in Path(path).parts):return respond(404,'Не найдено','text/plain; charset=utf-8')
  if target.is_dir():
   if not path.endswith('/'):return respond(301,'',extra=[('Location',path+'/')])
   target=target/'index.html'
  code=200
  if not target.is_file():target=public/'404/index.html';code=404
  raw=target.read_bytes();ctype=mimetypes.guess_type(target)[0] or 'application/octet-stream'
  if target.suffix=='.html':
   raw=raw.decode().replace('@@SITE_URL@@',html.escape(SITE,quote=True)).replace('@@ROBOTS@@','index,follow' if MODE=='production' and path not in ['/spasibo/','404/'] else 'noindex,nofollow').replace('@@LEGAL_OPERATOR@@',html.escape(os.getenv('LEGAL_OPERATOR','Оператор будет указан перед публикацией'))).replace('@@LEGAL_ADDRESS@@',html.escape(os.getenv('LEGAL_ADDRESS','Адрес будет указан перед публикацией'))).replace('@@LEGAL_NOTICE@@','' if os.getenv('LEGAL_APPROVED')=='1' else 'Проект документа для локальной проверки. Перед приёмом реальных заявок необходимо указать оператора, уточнить условия обработки и утвердить окончательную редакцию.')
   ctype='text/html; charset=utf-8'
  return respond(code,raw,ctype,extra=[('Cache-Control','public, max-age=3600' if path.startswith('/assets/') else 'no-cache')])
 except Exception:
  return respond(500,{'error':'Возникла ошибка. Свяжитесь с нами напрямую.'})

class ThreadedServer(ThreadingMixIn,WSGIServer):daemon_threads=True
class QuietHandler(WSGIRequestHandler):
 def log_message(self,*args):pass
 def handle(self):self.connection.settimeout(35);super().handle()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--open',action='store_true');args=parser.parse_args()
 host=os.getenv('HOST','127.0.0.1')
 with make_server(host,PORT,app,server_class=ThreadedServer,handler_class=QuietHandler) as httpd:
  print(f'ObogrevSistem: {SITE} | mode={MODE}',flush=True)
  if args.open and os.getenv('SITE_NO_BROWSER')!='1':
   import webbrowser
   threading.Timer(.5,lambda:webbrowser.open(SITE)).start()
  httpd.serve_forever()
