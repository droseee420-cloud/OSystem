'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
let config=null;
const ready=fetch('/api/config',{credentials:'same-origin'}).then(r=>{if(!r.ok)throw Error('config');return r.json()}).then(c=>{config=c;setupAnalytics(c);return c}).catch(()=>null);
const menu=$('.menu-toggle'),nav=$('#navigation');
menu?.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));nav.classList.toggle('open',open)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&nav?.classList.contains('open')){nav.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.focus()}});
document.addEventListener('click',e=>{if(nav?.classList.contains('open')&&!e.target.closest('.header')){nav.classList.remove('open');menu.setAttribute('aria-expanded','false')}});
$$('[data-year]').forEach(e=>e.textContent=new Date().getFullYear());
$$('[data-filter]').forEach(button=>button.addEventListener('click',()=>{$$('[data-filter]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button))});let count=0;$$('[data-category]').forEach(c=>{c.hidden=button.dataset.filter!=='all'&&c.dataset.category!==button.dataset.filter;if(!c.hidden)count++});$('#filter-status').textContent=`Показано работ: ${count}`}));
const lightbox=$('.lightbox');let trigger=null;
$$('[data-photo]').forEach(button=>button.addEventListener('click',()=>{trigger=button;$('img',lightbox).src=button.dataset.photo;$('img',lightbox).alt=button.dataset.caption;$('p',lightbox).textContent=button.dataset.caption;lightbox.showModal()}));
$('.lightbox-close')?.addEventListener('click',()=>lightbox.close());
lightbox?.addEventListener('click',e=>{if(e.target===lightbox)lightbox.close()});
lightbox?.addEventListener('close',()=>trigger?.focus());
const store={get(key){try{return localStorage.getItem(key)}catch{return null}},set(key,value){try{localStorage.setItem(key,value)}catch{}}};
const tags=['utm_source','utm_medium','utm_campaign','utm_content','utm_term','yclid'];
let attribution={};
try{const saved=JSON.parse(sessionStorage.getItem('os-attribution')||'{}');if(saved&&typeof saved==='object')attribution=saved}catch{}
const params=new URLSearchParams(location.search);let fresh={};tags.forEach(k=>{if(params.has(k))fresh[k]=params.get(k).slice(0,200)});
if(Object.keys(fresh).length){attribution=fresh;try{sessionStorage.setItem('os-attribution',JSON.stringify(fresh))}catch{}}
function goal(name){if(config?.metrika&&store.get('os-analytics')==='yes'&&typeof window.ym==='function')window.ym(Number(config.metrika),'reachGoal',name)}
function startAnalytics(){if(!config?.metrika||window.ym)return;window.ym=function(){(window.ym.a=window.ym.a||[]).push(arguments)};window.ym.l=Date.now();const s=document.createElement('script');s.async=true;s.src='https://mc.yandex.ru/metrika/tag.js?id='+config.metrika;document.head.appendChild(s);window.ym(Number(config.metrika),'init',{ssr:true,clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:config.webvisor===true,ecommerce:'dataLayer',referrer:document.referrer,url:location.href});}
function setupAnalytics(c){if(!c.metrika)return;$$('[data-cookie-settings]').forEach(b=>b.hidden=false);const choice=store.get('os-analytics');if(choice==='yes')startAnalytics();else if(choice!=='no')$('.cookie-panel').hidden=false;}
$$('[data-cookie]').forEach(b=>b.addEventListener('click',()=>{const old=store.get('os-analytics');store.set('os-analytics',b.dataset.cookie);$('.cookie-panel').hidden=true;if(b.dataset.cookie==='yes')startAnalytics();else if(old==='yes')location.reload()}));
$$('[data-cookie-settings]').forEach(b=>b.addEventListener('click',()=>{$('.cookie-panel').hidden=false;$('.cookie-panel button').focus()}));
$$('a[href^="tel:"]').forEach(a=>a.addEventListener('click',()=>goal('phone_click')));
$$('a[href^="mailto:"]').forEach(a=>a.addEventListener('click',()=>goal('email_click')));
const mobile=$('.mobile-contact'),request=$('#request');
if(request&&mobile){let inForm=false;const update=()=>mobile.classList.toggle('is-hidden',inForm||!!document.activeElement?.closest('input,textarea'));new IntersectionObserver(entries=>{inForm=entries[0].isIntersecting;update()},{threshold:.05}).observe(request);document.addEventListener('focusin',update);document.addEventListener('focusout',()=>setTimeout(update,100));}
function clientId(){return new Promise(resolve=>{if(!config?.metrika||store.get('os-analytics')!=='yes'||!window.ym)return resolve('');let done=false;const finish=v=>{if(!done){done=true;resolve(v||'')}};setTimeout(()=>finish(''),600);window.ym(Number(config.metrika),'getClientID',finish)})}
function fileData(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({name:file.name,data:reader.result.split(',')[1]});reader.onerror=()=>reject(Error('Не удалось прочитать файл. Попробуйте приложить его снова.'));reader.readAsDataURL(file)})}
$$('.lead-form').forEach(form=>{
 let started=false,id=crypto.randomUUID(),success=false;
 form.addEventListener('focusin',()=>{if(!started){goal('form_start');started=true}},{once:true});
 form.addEventListener('input',()=>{if(success){id=crypto.randomUUID();success=false}});
 form.addEventListener('submit',async e=>{
  e.preventDefault();const status=$('.form-status',form),button=$('button[type=submit]',form);status.classList.remove('error');status.textContent='';
  const contact=form.elements.contact.value.trim();
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact)&&!(/^[+\d()\s-]+$/.test(contact)&&contact.replace(/\D/g,'').length>=10&&contact.replace(/\D/g,'').length<=15)){status.textContent='Укажите корректный телефон или email.';status.classList.add('error');form.elements.contact.focus();return}
  const files=[...form.elements.files.files];
  if(files.length>3||files.reduce((s,f)=>s+f.size,0)>10*1024*1024){status.textContent='Можно приложить до 3 файлов суммарно до 10 МБ.';status.classList.add('error');status.focus();return}
  button.disabled=true;button.textContent='Отправляем…';
  try{
   const c=await ready;if(!c)throw Error('Не удалось подключиться к форме. Обновите страницу или свяжитесь с нами напрямую.');
   const payload={id,contact,name:form.elements.name.value,city:form.elements.city.value,message:form.elements.message.value,topic:form.dataset.topic,page:location.pathname,consent:form.elements.consent.checked,website:form.elements.website.value,attribution:{...attribution,client_id:await clientId()},files:await Promise.all(files.map(fileData))};
   const response=await fetch('/api/leads',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':c.csrf},body:JSON.stringify(payload)});let result;try{result=await response.json()}catch{throw Error('Сервер не подтвердил отправку. Попробуйте без вложений или свяжитесь с нами напрямую.')}
   if(!response.ok)throw Error(result.error||'Не удалось отправить. Позвоните нам или напишите на почту.');
   success=true;
   if(result.preview){status.textContent='Локальная проверка: заявка сохранена в тестовом почтовом ящике на компьютере. Письмо на Яндекс не отправлялось.';}
   else {goal('lead_sent');status.textContent='Заявка передана менеджеру. Мы свяжемся с вами по указанному контакту.';}
   form.reset();status.focus();
  }catch(err){status.textContent=err.message||'Не удалось отправить форму. Свяжитесь с нами напрямую.';status.classList.add('error');status.focus();}
  finally{button.disabled=false;button.textContent='Передать задачу менеджеру';}
 });
});
