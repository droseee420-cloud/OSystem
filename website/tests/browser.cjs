const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const root=path.join(__dirname,'..'),routes=JSON.parse(fs.readFileSync(path.join(root,'routes.json')));
const base=process.env.TEST_URL||'http://127.0.0.1:8766';
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});const issues=[],results=[];const assets=new Set(),links=new Set();
 for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
  const page=await browser.newPage({viewport:{width,height}});page.on('pageerror',e=>issues.push(name+': '+e.message));
  for(let i=0;i<routes.length;i++){
   const route=routes[i].path;const response=await page.goto(base+route);await page.evaluate(()=>document.fonts.ready);
   await page.locator('footer').scrollIntoViewIfNeeded();await page.waitForTimeout(60);await page.evaluate(()=>scrollTo(0,0));
   await page.evaluate(()=>Promise.all([...document.images].filter(i=>i.getAttribute('src')).map(i=>i.decode().catch(()=>{}))));
   const info=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,h1:document.querySelectorAll('h1').length,broken:[...document.images].filter(i=>i.getAttribute('src')&&(!i.complete||i.naturalWidth===0)).map(i=>i.src),links:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')),assets:[...document.querySelectorAll('img[src],script[src],link[href]')].map(a=>a.getAttribute('src')||a.getAttribute('href')),markers:document.body.innerText.includes('@@')}));
   if(response.status()!==200)issues.push(route+' status '+response.status());if(info.overflow)issues.push(name+' overflow '+route);if(info.h1!==1)issues.push(name+' h1='+info.h1+' '+route);if(info.broken.length)issues.push(name+' broken '+route+' '+info.broken);if(info.markers)issues.push('unresolved markers '+route);
   info.links.forEach(l=>links.add(l));info.assets.forEach(a=>assets.add(a));
   const stem=String(i+1).padStart(2,'0')+'-'+(route==='/'?'home':route.replaceAll('/','_'));
   await page.screenshot({path:path.join(root,'qa',name+'-'+stem+'.png'),fullPage:true});results.push({viewport:name,path:route,status:response.status(),...info,links:undefined,assets:undefined});
  }
  if(name==='mobile'){await page.goto(base);await page.getByRole('button',{name:/Меню/}).click();if(!await page.locator('#navigation').isVisible())issues.push('mobile menu');await page.keyboard.press('Escape');if(await page.locator('#navigation').isVisible())issues.push('escape menu');}
  await page.close();
 }
 const page=await browser.newPage();
 for(const href of new Set([...assets,...links].filter(v=>v?.startsWith('/')&&!v.startsWith('//')))){
  const u=new URL(href,base),r=await page.request.get(u.href);if(r.status()!==200)issues.push('broken link '+href+' '+r.status());
  if(u.hash){await page.goto(u.href);if(!await page.locator(u.hash).count())issues.push('missing anchor '+href);}
 }
 await page.goto(base+'/proekty/');await page.getByRole('button',{name:'Входные зоны',exact:true}).click();if(await page.locator('.project-card:visible').count()!==1)issues.push('project filter');await page.goto(base+'/proekty/vhodnaya-gruppa/');await page.locator('.gallery-item').first().click();if(!await page.locator('.lightbox').isVisible())issues.push('gallery open');await page.keyboard.press('Escape');if(await page.locator('.lightbox').isVisible())issues.push('gallery escape');
 await page.goto(base+'/?utm_source=yandex&utm_campaign=qa&yclid=123456');await page.locator('#contact').fill('test@example.com');await page.locator('textarea').fill('Автоматическая локальная проверка формы');await page.locator('details.more-fields summary').click();await page.locator('input[name=files]').setInputFiles({name:'test.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\n% local test\n')});await page.locator('input[name=consent]').check();await page.locator('button[type=submit]').click();await page.waitForFunction(()=>document.querySelector('.form-status').textContent.includes('Локальная проверка'));const formStatus=await page.locator('.form-status').innerText();
 const notFound=await page.goto(base+'/missing-page/');if(notFound.status()!==404)issues.push('404 status');
 await page.setViewportSize({width:320,height:800});await page.goto(base);if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))issues.push('320px overflow');
 await page.setViewportSize({width:1440,height:1000});await page.goto(base);await page.evaluate(()=>document.documentElement.style.fontSize='200%');if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))issues.push('200% text overflow');
 fs.writeFileSync(path.join(root,'qa/browser-report.json'),JSON.stringify({issues,results,formStatus,links:links.size,assets:assets.size},null,2));console.log(JSON.stringify({issues,pages:routes.length,viewports:2,links:links.size,assets:assets.size,formStatus}));await browser.close();if(issues.length)process.exitCode=1;
})();
