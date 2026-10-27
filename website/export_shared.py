"""Export public contact-only pages for shared hosting, without collecting leads.

The normal Python application and local preview keep their forms unchanged.
"""
import argparse,json,re,shutil
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--origin',default='https://obogrevsistem.ru')
parser.add_argument('--https',action='store_true')
parser.add_argument('--metrika-id',type=int,help='Public Yandex Metrika counter; loaded after visitor consent')
args=parser.parse_args();out=args.output.resolve();origin=args.origin.rstrip('/')
if not origin.startswith('https://'):raise SystemExit('Canonical origin must use HTTPS')
out.mkdir(parents=True,exist_ok=True)
excluded={'privacy','consent','spasibo'}
contact='''<div class="direct-request"><p class="eyebrow">Прямая связь с менеджером</p><h3>Расскажите о вашей задаче</h3><p>Позвоните или отправьте письмо. Укажите, что нужно обогреть, город объекта и удобный способ связи.</p><a class="button" href="tel:+79301755000">Позвонить: +7 930 175 50 00</a><a class="button secondary" href="mailto:obogrevsistem@yandex.ru">Написать на почту</a><p class="form-direct"><a href="mailto:obogrevsistem@yandex.ru">obogrevsistem@yandex.ru</a></p><p class="fine">Фото, размеры и техническое задание можно приложить к письму. Если материалов пока нет — начнём с разговора.</p></div>'''
for src in (ROOT/'public').rglob('*'):
 if not src.is_file():continue
 rel=src.relative_to(ROOT/'public')
 if rel.parts[0] in excluded:continue
 dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 if src.suffix!='.html':shutil.copy2(src,dest);continue
 text=src.read_text(encoding='utf-8')
 text=text.replace('@@SITE_URL@@',origin).replace('@@ROBOTS@@','noindex,follow' if rel.parts[0]=='404' else 'index,follow')
 text=re.sub(r'<form class="lead-form".*?</form>',lambda _:contact,text,flags=re.S)
 text=text.replace('Оставьте контакт и коротко опишите задачу. Менеджер уточнит детали и поможет определить следующий шаг.','Позвоните или напишите на почту. Менеджер уточнит детали объекта и поможет определить следующий шаг.')
 text=text.replace('Приложите к заявке — так разговор будет предметнее.','Пришлите на почту — так разговор будет предметнее.')
 text=text.replace('Позвоните, напишите на почту или оставьте заявку.','Позвоните или напишите на почту.')
 text=re.sub(r'<a href="/(?:privacy|consent)/"[^>]*>.*?</a>','',text)
 if args.metrika_id:
  text=text.replace('Аналитика помогает понять, какие разделы полезны. Разрешить Яндекс Метрику? ', 'Разрешить Яндекс Метрику и Вебвизор? Они используют cookie, собирают статистику посещений и записывают действия на страницах, чтобы улучшать сайт и рекламу. Выбор можно изменить в подвале сайта. ')
  text=text.replace('/assets/site.js"','/assets/site.js?v=metrika-113826221-1"')
 else:
  text=re.sub(r'<button class="link-button" data-cookie-settings hidden>.*?</button>','',text)
  text=re.sub(r'<div class="cookie-panel" hidden>.*?</div></div>','',text,flags=re.S)
 assert '@@' not in text and '<form' not in text and 'type="file"' not in text
 dest.write_text(text,encoding='utf-8',newline='\n')
with (out/'assets/site.css').open('a',encoding='utf-8') as f:
 f.write('\n.direct-request{align-self:center}.direct-request h3{font-size:28px}.direct-request .button{width:100%;margin:0 0 14px}.direct-request .fine{margin-top:24px}.direct-request .form-direct a{overflow-wrap:anywhere;white-space:normal}\n')
# Static configuration replaces the Python API; local previews never send analytics.
js=(out/'assets/site.js').read_text(encoding='utf-8')
counter=str(args.metrika_id) if args.metrika_id else 'null'
static_config="const ready=Promise.resolve({preview:false,metrika:['obogrevsistem.ru','www.obogrevsistem.ru'].includes(location.hostname)?"+counter+":null,webvisor:true}).then(c=>{config=c;setupAnalytics(c);return c});"
js=re.sub(r'const ready=fetch\(.*?\.catch\(\(\)=>null\);',lambda _:static_config,js,count=1)
start=js.index("const tags=['utm_source'");end=js.index('function goal(name)',start)
js=js[:start]+'let attribution={};\n'+js[end:]
(out/'assets/site.js').write_text(js,encoding='utf-8',newline='\n')
routes=json.loads((ROOT/'routes.json').read_text(encoding='utf-8'))
paths=[r['path'] for r in routes if r['path'].strip('/') not in excluded|{'404'}]
(out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(origin+p)+'</loc></url>' for p in paths)+'</urlset>',encoding='utf-8')
(out/'robots.txt').write_text('User-agent: *\nDisallow: /api/\nDisallow: /cgi-bin/\nDisallow: /404/\nSitemap: '+origin+'/sitemap.xml\n',encoding='utf-8')
ht='Options -Indexes\nDirectoryIndex index.html\nErrorDocument 404 /404/\nRewriteEngine On\n'
if args.https:
 ht+='RewriteCond %{REQUEST_URI} !^/\\.well-known/acme-challenge/\nRewriteCond %{HTTPS} !=on\nRewriteCond %{HTTP:X-Forwarded-Proto} !https [NC]\nRewriteRule ^ '+origin+'%{REQUEST_URI} [R=301,L]\nRewriteCond %{HTTP_HOST} !^obogrevsistem\\.ru$ [NC]\nRewriteCond %{REQUEST_URI} !^/\\.well-known/acme-challenge/\nRewriteRule ^ '+origin+'%{REQUEST_URI} [R=301,L]\n'
ht+='''<FilesMatch "^\\.">
Order allow,deny
Deny from all
</FilesMatch>
<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "DENY"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'none'"
</IfModule>
'''
if args.metrika_id:
 # Limit external resources to the exact Metrika host supplied by the owner.
 # Keep X-Frame-Options and frame-ancestors protection unchanged.
 ht=ht.replace("script-src 'self';", "script-src 'self' https://mc.yandex.ru;")
 ht=ht.replace("img-src 'self' data:;", "img-src 'self' data: https://mc.yandex.ru;")
 ht=ht.replace("connect-src 'self';", "connect-src 'self' https://mc.yandex.ru;")
(out/'.htaccess').write_text(ht,encoding='utf-8',newline='\n')
print(json.dumps({'pages':len(paths)+1,'files':sum(p.is_file() for p in out.rglob('*')),'mode':'direct-contact','https_redirect':args.https}))
