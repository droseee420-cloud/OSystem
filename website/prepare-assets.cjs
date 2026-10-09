const fs=require('node:fs'), path=require('node:path');
const sharp=require(process.env.SHARP_PATH || 'sharp');
const root=__dirname, dest=path.join(root,'public/assets');
const photoSource=process.env.PHOTO_SOURCE || path.join(root,'../кейсы');
const cases=[
 ['myagkaya-krovlya','Обогрев мягкой кровли',[2,3,6,7],'roof'],
 ['vnutrenniy-zhelob','Обогрев внутреннего желоба',[1,6,3,8],'roof'],
 ['voronki','Обогрев внутренних воронок',[9,7,4,5],'roof'],
 ['mansardnye-okna','Обогрев водосточной системы и мансардных окон',[4,2,6,3],'roof'],
 ['vhodnaya-gruppa','Обогрев входной группы',[2,1,5,3],'entrance'],
 ['kray-krovli','Обогрев края кровли',[16,12,15,18],'roof'],
 ['krovlya-i-okna','Обогрев края кровли и пожарных окон',[12,9,3,5],'roof'],
 ['teplyy-pol','Монтаж теплого пола на матах',[2,1],'floor'],
 ['shkafy-upravleniya','Шкафы управления электрообогревом',[6,7,5,2],'control']
];
(async()=>{fs.mkdirSync(dest,{recursive:true});
 const manifest=[];
 for(const [slug,title,indices,category] of cases){
  const photos=[];
  for(const n of indices){const src=path.join(photoSource,title,n+'.jpg'), name=`${slug}-${n}`;
   const meta=await sharp(src).metadata();
   await sharp(src).rotate().resize({width:1280,height:1280,fit:'inside',withoutEnlargement:true}).webp({quality:86}).toFile(path.join(dest,name+'.webp'));
   await sharp(src).rotate().resize({width:640,height:640,fit:'inside',withoutEnlargement:true}).webp({quality:82}).toFile(path.join(dest,name+'-640.webp'));
   photos.push({src:'/assets/'+name+'.webp',small:'/assets/'+name+'-640.webp',width:meta.width,height:meta.height,original:`кейсы/${title}/${n}.jpg`});
  } manifest.push({slug,title,category,photos});
 }
 fs.writeFileSync(path.join(root,'cases.json'),JSON.stringify(manifest,null,2));
 console.log('Prepared',manifest.length,'galleries; originals unchanged');
})();
