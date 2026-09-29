(()=>{
'use strict';
const $=id=>document.getElementById(id);
const say=msg=>{const el=$('syncLog');if(el)el.textContent=msg};
const toastSafe=msg=>{try{toast(msg)}catch(_e){}};
const post=async(path,body={})=>typeof window.desktopPost==='function'?window.desktopPost(path,body):fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async r=>{const j=await r.json();if(!r.ok||j.ok===false)throw new Error(j.error||r.statusText);return j});

async function openLiveFolder(){
  const b=$('openLiveExcelFolder48182');
  const old=b?.textContent||'';
  try{
    if(b){b.disabled=true;b.textContent='جاري فتح فولدر Live Excel...'}
    const r=await post('/api/open-live-excel-folder',{});
    say(`تم فتح فولدر Live Excel\n${r.path||'—'}${r.refreshError?`\nملاحظة: تعذر تحديث ملف مفتوح حاليًا: ${r.refreshError}`:''}`);
    toastSafe(r.refreshError?'تم فتح فولدر Live — يوجد ملف Excel مفتوح منع تحديثه الآن':'تم فتح فولدر Live Excel');
  }catch(e){
    say('تعذر فتح فولدر Live Excel:\n'+(e?.message||e));
    toastSafe('تعذر فتح فولدر Live Excel: '+(e?.message||e));
  }finally{
    if(b){b.disabled=false;b.textContent=old||'فتح فولدر Live Excel'}
  }
}

function install(){
  const refresh=$('s77LiveExcel');
  if(!refresh)return false;
  const card=refresh.closest('.s77-card');
  if(!card)return false;
  card.classList.add('s77-excel-card','s77-excel-card-48182');
  refresh.textContent='تحديث Live Excel الآن';
  refresh.title='إعادة بناء ملفات Live Excel لكل الشركات والتحقق منها';

  const obsolete=card.querySelector('[data-open="live-excel"]');
  if(obsolete)obsolete.remove();

  const folder=card.querySelector('[data-open="excel-live-folder"]');
  if(folder){
    folder.removeAttribute('data-open');
    folder.id='openLiveExcelFolder48182';
    folder.textContent='فتح فولدر Live Excel';
    folder.title='يفتح Excel\\Live؛ داخله فولدر مستقل لكل شركة وملف Excel محدث';
    folder.onclick=openLiveFolder;
  }
  const excelRoot=card.querySelector('[data-open="excel"]');
  if(excelRoot)excelRoot.textContent='فتح فولدر Excel الرئيسي';
  const manual=$('s77ManualExcel');
  if(manual)manual.textContent='إنشاء Manual Excel + Reports الآن';

  let note=card.querySelector('.live-excel-note-48182');
  if(!note){
    note=document.createElement('div');
    note.className='mini live-excel-note-48182';
    note.innerHTML='<b>Live Excel:</b> داخل فولدر <b>Live</b> يوجد فولدر مستقل لكل شركة، وداخله ملف Excel واحد بنفس القالب المعتمد ويحتوي ورقتين فقط: <b>البنود</b> و<b>التفتيشات</b>. يتم تحديثه تلقائيًا بعد حفظ أي تغيير، ويمكن تحديثه يدويًا من الزر أعلاه.';
    card.appendChild(note);
  }
  return true;
}

const oldRenderSync=window.renderSync;
if(typeof oldRenderSync==='function'){
  window.renderSync=async function(...args){const r=await oldRenderSync.apply(this,args);install();return r};
}
let tries=0;const timer=setInterval(()=>{tries++;if(install()||tries>40)clearInterval(timer)},100);
})();
