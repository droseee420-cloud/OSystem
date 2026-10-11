"""Temporary SpaceWeb cron: enable redirect only after valid public TLS.

Place outside public_html with deployment.json and https.htaccess.
Removes only its own marked cron line after success, conflict or timeout.
"""
from pathlib import Path
import hashlib,json,ssl,socket,time,subprocess,os

MARKER='osystem-enable-https-once'
def remove_own_job():
 result=subprocess.run(['crontab','-l'],capture_output=True,text=True)
 if result.returncode:return
 lines=result.stdout.splitlines(keepends=True)
 kept=[line for line in lines if MARKER not in line]
 if kept!=lines:subprocess.run(['crontab','-'],input=''.join(kept),text=True,check=True)
def valid_tls(host):
 with socket.create_connection((host,443),timeout=12) as raw:
  with ssl.create_default_context().wrap_socket(raw,server_hostname=host) as secure:
   return bool(secure.getpeercert())
def run(root):
 cfg=json.loads((root/'deployment.json').read_text())
 status=root/'https-status.json'
 def record(state,reason=''):
  status.write_text(json.dumps({'status':state,'checked_at':int(time.time()),'reason':reason}),encoding='utf-8')
  if state in ('enabled','conflict','expired'):remove_own_job()
 if status.exists() and json.loads(status.read_text()).get('status') in ('enabled','conflict','expired'):
  remove_own_job();return
 if time.time()>cfg['deadline']:record('expired','Certificate not ready within 24 hours');return
 try:
  for host in cfg['hosts']:
   if not valid_tls(host):record('pending');return
 except (OSError,ssl.SSLError) as e:record('pending',type(e).__name__);return
 target=root.parent/'public_html'/'.htaccess'
 content=target.read_bytes();next_content=(root/'https.htaccess').read_bytes()
 if content==next_content:record('enabled');return
 if hashlib.sha256(content).hexdigest()!=cfg['initial_sha256']:
  record('conflict','Hosting configuration changed after deployment; not overwritten');return
 temp=target.with_name('.htaccess.osystem-tmp')
 temp.write_bytes(next_content);os.chmod(temp,0o644);os.replace(temp,target)
 record('enabled')
if __name__=='__main__':run(Path(__file__).resolve().parent)
