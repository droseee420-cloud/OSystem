import os,sys,tempfile,unittest,json,io,uuid,base64,sqlite3
from pathlib import Path
from unittest.mock import patch,MagicMock
tmp=tempfile.TemporaryDirectory();os.environ['DATA_DIR']=tmp.name;os.environ['APP_MODE']='preview'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import server

class ServerTests(unittest.TestCase):
 def setUp(self):
  self.csrf=server.token();self.ip=str(uuid.uuid4())
 def call(self,path='/',method='GET',payload=None,**changes):
  raw=json.dumps(payload or {}).encode();env={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json','wsgi.input':io.BytesIO(raw),'HTTP_ORIGIN':server.SITE,'HTTP_X_CSRF_TOKEN':self.csrf,'HTTP_COOKIE':'form_session='+self.csrf,'REMOTE_ADDR':self.ip};env.update(changes);out={}
  body=b''.join(server.app(env,lambda status,headers:out.update(status=int(status[:3]),headers=dict(headers))));out['body']=body
  return out
 def lead(self,**changes):
  d={'id':str(uuid.uuid4()),'contact':'test@example.com','name':'Тест','city':'Тверь','message':'Локальная проверка','topic':'Кровля','page':'/resheniya/krovlya/','consent':True,'files':[],'attribution':{'yclid':'123456','utm_source':'yandex'}};d.update(changes);return d
 def test_preview_and_deduplication(self):
  p=self.lead();r=self.call('/api/leads','POST',p);self.assertEqual(r['status'],201);self.assertTrue(json.loads(r['body'])['preview']);self.assertTrue((server.DATA/'preview-mail'/(p['id']+'.eml')).exists());self.assertEqual(self.call('/api/leads','POST',p)['status'],200)
 def test_requires_consent(self):self.assertEqual(self.call('/api/leads','POST',self.lead(consent=False))['status'],400)
 def test_validates_contact(self):self.assertEqual(self.call('/api/leads','POST',self.lead(contact='no'))['status'],400)
 def test_phone(self):self.assertEqual(self.call('/api/leads','POST',self.lead(contact='+7 (930) 175-50-00'))['status'],201)
 def test_origin_and_csrf(self):
  self.assertEqual(self.call('/api/leads','POST',self.lead(),HTTP_ORIGIN='https://evil.test')['status'],403)
  self.assertEqual(self.call('/api/leads','POST',self.lead(),HTTP_X_CSRF_TOKEN='wrong')['status'],403)
 def test_invalid_body(self):self.assertEqual(self.call('/api/leads','POST',self.lead(),CONTENT_LENGTH=str(server.MAX_BODY+1))['status'],413)
 def test_file_delivery(self):
  p=self.lead(files=[{'name':'test.pdf','data':base64.b64encode(b'%PDF-1.4\nlocal test').decode()}]);self.assertEqual(self.call('/api/leads','POST',p)['status'],201);self.assertTrue((server.DATA/'attachments'/p['id']/'1_test.pdf').exists())
 def test_bad_files(self):
  for f in [{'name':'bad.exe','data':'AAAA'},{'name':'bad.pdf','data':base64.b64encode(b'not pdf').decode()}]:self.assertEqual(self.call('/api/leads','POST',self.lead(files=[f]))['status'],400)
 def test_rate_limit(self):
  for _ in range(5):self.assertEqual(self.call('/api/leads','POST',self.lead())['status'],201)
  self.assertEqual(self.call('/api/leads','POST',self.lead())['status'],429)
 def test_mail_error_is_not_success(self):
  p=self.lead()
  with patch.object(server,'send_email',side_effect=OSError('simulated')):self.assertEqual(self.call('/api/leads','POST',p)['status'],502)
  with server.db() as con:self.assertEqual(con.execute('SELECT status FROM leads WHERE id=?',(p['id'],)).fetchone()[0],'failed')
 def test_smtp_contract(self):
  lead=self.lead()
  with patch.object(server,'MODE','production'),patch.dict(os.environ,{'SMTP_USER':'test@example.com','SMTP_PASSWORD':'test-password'}),patch.object(server.smtplib,'SMTP_SSL') as smtp:
   server.send_email(lead,[]);smtp.return_value.__enter__.return_value.send_message.assert_not_called()
   smtp.return_value.login.assert_called_once_with('test@example.com','test-password');smtp.return_value.send_message.assert_called_once()
   msg=smtp.return_value.send_message.call_args.args[0];self.assertEqual(msg['To'],server.EMAIL);self.assertEqual(msg['Reply-To'],'test@example.com')
 def test_private_files_and_404(self):
  for path in ['/.env','/../server.py','/data/leads.sqlite3','/absent/']:
   r=self.call(path);self.assertEqual(r['status'],404);self.assertNotIn(b'SMTP_PASSWORD',r['body'])
 def test_seo_and_config(self):
  r=self.call('/');self.assertNotIn(b'@@',r['body']);self.assertIn(b'noindex',r['body']);self.assertEqual(self.call('/sitemap.xml')['status'],200)
  c=self.call('/api/config');self.assertIsNone(json.loads(c['body'])['metrika']);self.assertIn('HttpOnly',c['headers']['Set-Cookie'])
 def test_multiple_tabs_reuse_csrf(self):self.assertEqual(json.loads(self.call('/api/config')['body'])['csrf'],self.csrf)

if __name__=='__main__':unittest.main(verbosity=2)
