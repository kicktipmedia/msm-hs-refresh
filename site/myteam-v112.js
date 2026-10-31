/* next110: My team settings (localStorage only: no cookies, accounts or tracking) */
(function(){
var W=window,D=document,LS;try{LS=W.localStorage;LS.setItem('msm-t','1');LS.removeItem('msm-t')}catch(e){LS=null}
var K='msm-myteam',KB='msm-myteam-bar-dismissed';
var TEAMS=[['byu','BYU'],['utah','Utah'],['usu','Utah State'],['weber','Weber State'],['suu','Southern Utah'],['utech','Utah Tech']];
var IDS=TEAMS.map(function(t){return t[0]}),NAME={};TEAMS.forEach(function(t){NAME[t[0]]=t[1]});
var RX=[[/Southern Utah/,'suu'],[/Utah State/,'usu'],[/Utah Tech/,'utech'],[/Weber State/,'weber'],[/\bBYU\b/,'byu'],[/\bUtah\b/,'utah']];
function get(k){try{return LS?LS.getItem(k):null}catch(e){return null}}
function put(k,v){try{if(LS){if(v==null)LS.removeItem(k);else LS.setItem(k,v)}}catch(e){}}
function load(){var s;try{s=JSON.parse(get(K)||'null')}catch(e){s=null}
 if(!s||typeof s!=='object')return null;
 var t=(Array.isArray(s.teams)?s.teams:[]).filter(function(x,i,a){return IDS.indexOf(x)>=0&&a.indexOf(x)===i}).slice(0,6);
 if(!s.all&&!t.length)return null;return{v:1,all:!!s.all,teams:s.all?[]:t,showAll:!!s.showAll}}
var S=load();
function save(){if(S)put(K,JSON.stringify(S));else put(K,null);fire()}
function picks(){return S&&!S.all?S.teams:[]}
function filtering(){return picks().length>0&&!S.showAll}
/* team key from an element */
function txtKey(t){for(var i=0;i<RX.length;i++)if(RX[i][0].test(t))return RX[i][1];return null}
/* slugs used by stadium, storyline and gear links */
var SLUG={'lavell-edwards':'byu','rice-eccles':'utah','maverik':'usu','stewart':'weber','eccles-coliseum':'suu','greater-zion':'utech','utah-state':'usu','weber-state':'weber','utah-tech':'utech'};
function slugKey(s){if(!s)return null;return IDS.indexOf(s)>=0?s:(SLUG[s]||null)}
function hrefKey(el){var a=el.matches&&el.matches('a[href*="/team/"]')?el:el.querySelector&&el.querySelector('a[href*="/team/"]');if(a){var m=/\/team\/([a-z]+)\//.exec(a.getAttribute('href'));if(m&&IDS.indexOf(m[1])>=0)return m[1]}
 var hr=el.getAttribute&&el.getAttribute('href')||'',x;
 if((x=/\/stadiums\/([a-z-]+)/.exec(hr))||(x=/\/storylines\/[0-9-]+\/([a-z-]+)/.exec(hr))||(x=/^#g-([a-z]+)$/.exec(hr)))return slugKey(x[1]);
 if((x=/^g-([a-z]+)$/.exec(el.id||'')))return slugKey(x[1]);
 return null}
function keyOf(el,how){var k=el.getAttribute('data-team')||el.getAttribute('data-tm');if(k&&IDS.indexOf(k)>=0)return k;
 if(how==='tab'){k=(el.getAttribute('aria-controls')||'');return IDS.indexOf(k)>=0?k:null}
 if(how==='href')return hrefKey(el);
 if(how&&how.indexOf('text:')===0){var c=el.querySelector(how.slice(5));if(!c)return null;var f=c.firstChild;return txtKey(f&&f.nodeType===3&&f.textContent.trim()?f.textContent:c.textContent)}
 if(how==='text')return txtKey(el.textContent);
 return hrefKey(el)}
/* page configuration: f = filter + order, h = highlight only. strict: hide rows that are none of the six */
var P=location.pathname.replace(/index\.html$/,'');
var CFG={
 '/':{f:[['#slate .c1w .grid>article.card[data-team]'],['.schrow>a[href^="/team/"]','href'],['.rk2row','href',0,'keep'],['.pwgrid>article.pw','href'],['#storylines .styrow','href']],m:[['.rk2po>span','',1]]},
 '/game-day/':{f:[['.c1w .grid>article.card[data-team]'],['.gtabs [role=tab]','tab']]},
 '/rankings/':{m:[['main table tbody tr','td.tm']]},
 '/stadiums/':{f:[['.stlist>a.st','href']]},
 '/gear/':{f:[['.teamgrid>a.tile','href'],['.ghgrid>div[id^="g-"]','href']]},
 '/playoff/':{m:[['.ut>a','b'],['.bias tbody tr','td'],['.fbw .ft','.fn'],['.br .tm','.nm'],['.rdw .ft','.fn'],['.tw tbody tr','.tc'],['.chips .chip',''],['.fgm','p']]}
};
var C=CFG[P];
var BOUND='h1,h2,h3,h4,h5,h6,hr,.rk2hd,.rk2sep,[data-mt-sec]';
var busy=0,lastSig='',H0=location.hash.length>1;
function applyPage(){if(!C||busy)return;busy=1;
 var pk=picks(),on=filtering(),ord=pk.length>0;
 (C.f||[]).forEach(function(g){var els=[].slice.call(D.querySelectorAll(g[0]));if(!els.length)return;
  var groups=new Map();els.forEach(function(e){var p=e.parentNode;if(!groups.has(p))groups.set(p,[]);groups.get(p).push(e)});
  groups.forEach(function(list,par){
   list.forEach(function(e,i){if(e._mtI==null)e._mtI=i;e._mtK=keyOf(e,g[1])});
   var keyed=list.filter(function(e){return e._mtK});
   var vis=function(e){if(!on)return true;if(!e._mtK)return !g[2];return pk.indexOf(e._mtK)>=0};
   list.forEach(function(e){var v=vis(e);e.classList.toggle('mt-off',!v);e.classList.toggle('mt-pick',!!e._mtK&&pk.indexOf(e._mtK)>=0);e.classList.toggle('mt-top',!!e._mtK&&e._mtK===pk[0])});
   /* reorder the slots the keyed items occupy; ranking tables (g[3]='keep') stay in rank order */
   if(g[3]==='keep')return;
   var slots=keyed.slice().sort(function(a,b){return a._mtI-b._mtI});
   var want=keyed.slice().sort(function(a,b){var ra=ord?pk.indexOf(a._mtK):-1,rb=ord?pk.indexOf(b._mtK):-1;ra=ra<0?99:ra;rb=rb<0?99:rb;return ra-rb||a._mtI-b._mtI});
   /* sections: headers and separators split a parent into segments; items never cross them (FCS stays FCS) */
   var seg=0;[].forEach.call(par.children,function(c){if(keyed.indexOf(c)>=0)c._mtS=seg;else if(c.matches&&c.matches(BOUND))seg++});
   for(var s=0;s<=seg;s++){var inS=function(e){return e._mtS===s};
    var cur=[].slice.call(par.children).filter(function(e){return keyed.indexOf(e)>=0&&inS(e)}),ws=want.filter(inS);
    if(ws.some(function(e,i){return cur[i]!==e})){var marks=cur.map(function(e){var m=D.createComment('');par.insertBefore(m,e);return m});
     marks.forEach(function(m,i){par.insertBefore(ws[i],m)});marks.forEach(function(m){par.removeChild(m)})}}
  });
 });
 (C.h||[]).forEach(function(g){[].forEach.call(D.querySelectorAll(g[0]),function(e){var k=keyOf(e,g[1]);e.classList.toggle('mt-pick',!!k&&pk.indexOf(k)>=0);e.classList.toggle('mt-top',!!k&&k===pk[0])})});
 /* game day: keep a visible tab selected */
 var sel=D.querySelector('.gtabs [role=tab][aria-selected=true]');
 var sig=on?pk.join(','):'';if(on&&sel&&(sel.classList.contains('mt-off')||(sig!==lastSig&&!H0))){var f=D.querySelector('.gtabs [role=tab]:not(.mt-off)');if(f){var y=W.scrollY;f.click();W.scrollTo(W.scrollX,y)}}
 if(D.querySelector('.gtabs'))lastSig=sig;
 /* home: hide 'See all' when nothing is left to expand */
 [].forEach.call(D.querySelectorAll('.xbtn[data-x]'),function(b){var s=D.getElementById(b.getAttribute('data-x'));if(!s)return;var n=s.querySelectorAll('.c1w .grid>article:not(.mt-off),.styrow:not(.mt-off)').length;b.classList.toggle('mt-off',on&&n<=3)});
 (C.m||[]).forEach(function(g){[].forEach.call(D.querySelectorAll(g[0]),function(e){var n=g[1]?e.querySelector(g[1]):e;if(n)mark(n,pk,g[2])})});if(C.m)fit();
 busy=0}
/* next112: My team marker v2 (MSM mountain, lit facets + snow). Full mark at 15px and up, simple notch mark under 15px. Swap the glyph by editing MK only. */
var MK='<svg class="mt-mkg mt-mkf" viewBox="0 0 120 80" aria-hidden="true" focusable="false"><path class="a" d="M3 77L28 42L36 51L50 28L62 5L74 25L84 39L94 29L117 62L117 77Z"/><path class="l" d="M62 5L50 28L44 38L51 42L45 58L55 77L64 44L58 25Z"/><path class="l" d="M28 42L3 77L15 77L26 57L32 47Z"/><path class="l" d="M94 29L86 40L92 47L89 62L99 56L97 40Z"/><path class="s" d="M62 5L54 20L58 21L56 26L61 22L65 27L68 19L71 21Z"/><path class="s" d="M94 29L89 36L93 37L95 34L99 37Z"/><path class="o" d="M3 77L28 42L36 51L50 28L62 5L74 25L84 39L94 29L117 62L117 77Z"/></svg><svg class="mt-mkg mt-mks" viewBox="0 0 120 80" aria-hidden="true" focusable="false"><path class="a" d="M3 77L28 42L36 51L50 28L62 5L74 25L84 39L94 29L117 62L117 77Z"/><path class="n" d="M62 5L50 28L58 25Z"/></svg>';
var MRX=/Southern Utah|Utah State|Utah Tech|Weber State|\bBYU\b|\bUtah\b/g;
function dark(el){for(var e=el;e&&e.nodeType===1;e=e.parentElement){var c=getComputedStyle(e).backgroundColor,m=/rgba?\(([\d.]+), ?([\d.]+), ?([\d.]+)(?:, ?([\d.]+))?/.exec(c);if(m&&(m[4]===undefined||+m[4]>.5)){return(.2126*m[1]+.7152*m[2]+.0722*m[3])/255<.35}}return false}
function mark(n,pk,inl){var want=[],have=[].map.call(n.querySelectorAll(':scope>.mt-mkw'),function(w){return w.getAttribute('data-k')}).join();
 [].forEach.call(n.childNodes,function(t){if(t.nodeType===3)(t.textContent.match(MRX)||[]).forEach(function(x){var k=txtKey(x);if(pk.indexOf(k)>=0)want.push(k)})});
 [].forEach.call(n.querySelectorAll(':scope>.mt-mkw'),function(w){if(pk.indexOf(w.getAttribute('data-k'))>=0)want.push(w.getAttribute('data-k'))});
 var cur=[].map.call(n.querySelectorAll(':scope>.mt-mkw'),function(w){return w.getAttribute('data-k')});
 if(cur.length&&cur.every(function(k){return pk.indexOf(k)>=0})&&!hasUnmarked(n,pk))return;
 [].forEach.call(n.querySelectorAll(':scope>.mt-mkw'),function(w){w.parentNode.replaceChild(D.createTextNode(w.getAttribute('data-t')),w)});n.normalize();
 if(!pk.length)return;var nav=null;
 [].slice.call(n.childNodes).forEach(function(t){if(t.nodeType!==3)return;var s=t.textContent,re=new RegExp(MRX.source,'g'),m,last=0,frag=null;
  while((m=re.exec(s))){var k=txtKey(m[0]);if(pk.indexOf(k)<0)continue;frag=frag||D.createDocumentFragment();if(!inl&&end0(s)<=last)break;
   /* keep the last word and the marker together so the name never wraps away from it */
   var end=inl?m.index+m[0].length:s.replace(/\s+$/,'').length,ws=s.lastIndexOf(' ',end-1);ws=ws<m.index?m.index:ws+1;
   frag.appendChild(D.createTextNode(s.slice(last,ws)));if(nav===null)nav=dark(n);
   var w=D.createElement('span');w.className='mt-mkw'+(nav?' mt-mk-nv':'')+(inl?' mt-mk-in':'');w.setAttribute('data-k',k);w.setAttribute('data-t',s.slice(ws,end));
   w.innerHTML='';w.appendChild(D.createTextNode(s.slice(ws,end)));var mk=D.createElement('span');mk.className='mt-mk';mk.title='My team';mk.innerHTML=MK+'<span class="mt-vh"> (My team)</span>';w.appendChild(mk);frag.appendChild(w);last=end}
  if(frag){frag.appendChild(D.createTextNode(s.slice(last)));n.replaceChild(frag,t)}});fit()}
/* in a table cell too narrow for the glyph, let it take real width instead of spilling over the next cell */
function fit(){[].forEach.call(D.querySelectorAll('.mt-mkw'),function(w){w.classList.toggle('mt-mk-s',parseFloat(getComputedStyle(w).fontSize)*.9375<15)});[].forEach.call(D.querySelectorAll('.mt-mkw:not(.mt-mk-in)'),function(w){var c=w.closest('td,th');if(!c)return;w.classList.remove('mt-mk-fit');var g=w.lastChild.getBoundingClientRect(),r=c.getBoundingClientRect(),pr=parseFloat(getComputedStyle(c).paddingRight)||0;if(g.width&&g.right>r.right-pr/2+.5)w.classList.add('mt-mk-fit')})}
W.addEventListener('resize',function(){clearTimeout(fit.t);fit.t=setTimeout(fit,100)});W.addEventListener('load',fit);if(D.fonts&&D.fonts.ready)D.fonts.ready.then(fit);
function end0(s){return s.replace(/\s+$/,'').length}
function hasUnmarked(n,pk){var r=false;[].forEach.call(n.childNodes,function(t){if(t.nodeType===3)(t.textContent.match(MRX)||[]).forEach(function(x){if(pk.indexOf(txtKey(x))>=0)r=true})});return r}
var mo,tm;function watch(){if(!C||!W.MutationObserver)return;var root=D.querySelector('main')||D.body;mo=new MutationObserver(function(){if(busy)return;clearTimeout(tm);tm=setTimeout(function(){mo.disconnect();applyPage();mo.takeRecords();mo.observe(root,{childList:true,subtree:true})},40)});mo.observe(root,{childList:true,subtree:true})}
/* ---------- UI ---------- */
function h(tag,attrs,kids){var e=D.createElement(tag);for(var a in attrs||{}){if(a==='text')e.textContent=attrs[a];else if(a==='on')for(var ev in attrs.on)e.addEventListener(ev,attrs.on[ev]);else e.setAttribute(a,attrs[a])}(kids||[]).forEach(function(k){if(k)e.appendChild(typeof k==='string'?D.createTextNode(k):k)});return e}
var GEAR='<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="M19.4 13a7.5 7.5 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.6 7.6 0 0 0-1.7-1L15 3h-4l-.4 2.9a7.6 7.6 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.5 7.5 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.6 7.6 0 0 0 1.7 1L11 21h4l.4-2.9a7.6 7.6 0 0 0 1.7-1l2.5 1 2-3.5zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z" transform="translate(-1 0)"/></svg>';
/* settings registry: add more sections later with MSMSettings.add({id,title,render}) */
var SECTIONS=[];var API=W.MSMSettings={add:function(s){SECTIONS.push(s);if(dlg)renderPanel()},open:openPanel,get:function(){return S?JSON.parse(JSON.stringify(S)):null},teams:TEAMS.slice()};
var dlg,lastFocus;
function openPanel(){buildPanel();renderPanel();lastFocus=D.activeElement;if(dlg.showModal&&!dlg.open)dlg.showModal();else dlg.setAttribute('open','');var f=dlg.querySelector('.mt-x');f&&f.focus()}
function closePanel(){if(!dlg)return;if(dlg.close&&dlg.open)dlg.close();else dlg.removeAttribute('open')}
function buildPanel(){if(dlg)return;dlg=h('dialog',{'class':'mt-dlg',id:'mt-panel','aria-labelledby':'mt-h'});
 dlg.addEventListener('close',function(){if(lastFocus&&lastFocus.focus)lastFocus.focus()});
 dlg.addEventListener('click',function(e){if(e.target===dlg)closePanel()});
 D.body.appendChild(dlg)}
function renderPanel(){dlg.innerHTML='';
 var head=h('div',{'class':'mt-hd'},[h('h2',{id:'mt-h',text:'Settings'}),h('button',{type:'button','class':'mt-x','aria-label':'Close settings',on:{click:closePanel}},['Close'])]);
 var body=h('div',{'class':'mt-bd'});SECTIONS.forEach(function(s){var sec=h('section',{'class':'mt-sec','data-setting':s.id,'aria-labelledby':'mt-s-'+s.id},[h('h3',{id:'mt-s-'+s.id,text:s.title})]);s.render(sec);body.appendChild(sec)});
 dlg.appendChild(head);dlg.appendChild(body);dlg.appendChild(h('div',{'class':'mt-ft'},[h('button',{type:'button','class':'mt-go mt-save',on:{click:closePanel}},['Save'])]));
 dlg.appendChild(h('p',{'class':'mt-fine',text:'Saved on this device only. No account, no cookies, no tracking.'}))}
function teamSection(sec){
 var pk=picks(),all=!!(S&&S.all);
 sec.appendChild(h('p',{'class':'mt-help',text:'Pick up to six teams. Drag the grip to set the order. Your first team gets the spotlight.'}));
 var allBtn=h('button',{type:'button','class':'mt-all','aria-pressed':all?'true':'false',on:{click:function(){S={v:1,all:true,teams:[],showAll:false};save();renderPanel();focusSel('.mt-all')}}},['All teams']);
 sec.appendChild(allBtn);
 var order=pk.concat(IDS.filter(function(k){return pk.indexOf(k)<0}));
 var ul=h('ol',{'class':'mt-list'});
 order.forEach(function(k){var i=pk.indexOf(k),on=i>=0,id='mt-c-'+k;
  var cb=h('input',{type:'checkbox',id:id,'data-k':k});cb.checked=on;
  cb.addEventListener('change',function(){var t=picks().slice();if(cb.checked){if(t.indexOf(k)<0)t.push(k)}else t=t.filter(function(x){return x!==k});
   S=t.length?{v:1,all:false,teams:t,showAll:S?!!S.showAll:false}:null;save();renderPanel();focusSel('#'+id)});
  var grip=on?h('button',{type:'button','class':'mt-grip','aria-label':'Reorder '+NAME[k],'aria-describedby':'mt-dhelp','data-k':k},[]):h('span',{'class':'mt-gsp','aria-hidden':'true'});
  if(on){grip.innerHTML=GRIP;if(kb&&kb.k===k){grip.setAttribute('aria-pressed','true');grip.classList.add('mt-kgrab')}gripWire(grip,k)}
  ul.appendChild(h('li',{'class':'mt-row'+(on?' mt-sel':'')+(i===0?' mt-first':'')+(kb&&kb.k===k?' mt-kgrab':''),'data-k':k},[h('label',{'for':id},[cb,h('span',{'class':'mt-n',text:NAME[k]}),on?h('span',{'class':'mt-rk',text:i===0?'Top pick':'No. '+(i+1)}):null]),grip]))});
 sec.appendChild(h('p',{'class':'mt-vh',id:'mt-dhelp',text:'Press Space or Enter to pick up, arrow keys to move, Space or Enter to drop, Escape to cancel.'}));
 sec.appendChild(ul);
 if(S)sec.appendChild(h('button',{type:'button','class':'mt-clear',on:{click:function(){S=null;save();renderPanel();focusSel('.mt-all')}}},['Clear my teams']))}
var GRIP='<svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true" focusable="false"><g fill="currentColor"><circle cx="7" cy="4" r="1.8"/><circle cx="13" cy="4" r="1.8"/><circle cx="7" cy="10" r="1.8"/><circle cx="13" cy="10" r="1.8"/><circle cx="7" cy="16" r="1.8"/><circle cx="13" cy="16" r="1.8"/></g></svg>';
var kb=null,drag=null;
function say(m){var l=dlg&&dlg.querySelector('.mt-live');if(!l){l=h('p',{'class':'mt-live mt-vh',role:'status','aria-live':'polite'});dlg.appendChild(l)}l.textContent='';setTimeout(function(){l.textContent=m},30)}
function posMsg(k){var t=picks();var i=t.indexOf(k);return NAME[k]+', position '+(i+1)+' of '+t.length+(i===0?', top pick':'')}
function setOrder(t,persist){S.teams=t;if(persist)save();renderPanel()}
function focusGrip(k){var g=dlg.querySelector('.mt-grip[data-k='+k+']');g&&g.focus()}
function gripWire(g,k){
 g.addEventListener('keydown',function(e){var K=e.key;
  if(K===' '||K==='Enter'){e.preventDefault();if(!kb){kb={k:k,orig:picks().slice()};renderPanel();focusGrip(k);say(NAME[k]+' picked up. '+posMsg(k)+'. Use the arrow keys to move, Space or Enter to drop, Escape to cancel.')}else{var kk=kb.k;kb=null;setOrder(picks().slice(),true);focusGrip(kk);say(NAME[kk]+' dropped. '+posMsg(kk)+'.')}return}
  if(!kb)return;
  if(K==='Escape'){e.preventDefault();e.stopPropagation();var o=kb.orig,kk=kb.k;kb=null;setOrder(o,false);focusGrip(kk);say('Reorder cancelled. '+posMsg(kk)+'.');return}
  if(K==='ArrowUp'||K==='ArrowDown'||K==='ArrowLeft'||K==='ArrowRight'||K==='Home'||K==='End'){e.preventDefault();var t=picks().slice(),i=t.indexOf(kb.k),j=K==='Home'?0:K==='End'?t.length-1:i+((K==='ArrowUp'||K==='ArrowLeft')?-1:1);if(j<0||j>=t.length||j===i)return;t.splice(i,1);t.splice(j,0,kb.k);setOrder(t,false);focusGrip(kb.k);say(posMsg(kb.k)+'.')}});
 g.addEventListener('blur',function(){var kk=kb&&kb.k;setTimeout(function(){if(kb&&kb.k===kk&&dlg&&D.activeElement!==dlg.querySelector('.mt-grip[data-k='+kk+']')){kb=null;setOrder(picks().slice(),true)}},0)});
 g.addEventListener('pointerdown',function(e){if(e.button>0||drag)return;e.preventDefault();var row=g.closest('.mt-row'),list=row.parentNode,r=row.getBoundingClientRect();
  try{g.setPointerCapture(e.pointerId)}catch(_){}
  var pv=row.cloneNode(true);pv.removeAttribute('data-k');pv.className='mt-row mt-sel mt-preview';pv.setAttribute('aria-hidden','true');[].forEach.call(pv.querySelectorAll('[id]'),function(x){x.removeAttribute('id')});[].forEach.call(pv.querySelectorAll('input,button'),function(x){x.tabIndex=-1});
  pv.style.width=r.width+'px';pv.style.left=r.left+'px';pv.style.top=r.top+'px';dlg.appendChild(pv);
  var ind=h('li',{'class':'mt-drop','aria-hidden':'true'});row.classList.add('mt-dragging');
  drag={k:k,id:e.pointerId,g:g,row:row,list:list,pv:pv,ind:ind,dy:e.clientY-r.top,to:picks().indexOf(k)};dmove(e)});
 g.addEventListener('pointermove',function(e){if(drag&&e.pointerId===drag.id){e.preventDefault();dmove(e)}});
 g.addEventListener('pointerup',function(e){if(drag&&e.pointerId===drag.id)dend(true)});
 g.addEventListener('pointercancel',function(e){if(drag&&e.pointerId===drag.id)dend(false)});
 g.addEventListener('lostpointercapture',function(e){if(drag&&e.pointerId===drag.id)setTimeout(function(){drag&&dend(true)},0)})}
function dmove(e){var d=drag;d.pv.style.top=(e.clientY-d.dy)+'px';
 var rows=[].filter.call(d.list.querySelectorAll('.mt-row.mt-sel'),function(x){return x!==d.row}),to=rows.length;
 for(var i=0;i<rows.length;i++){var r=rows[i].getBoundingClientRect();if(e.clientY<r.top+r.height/2){to=i;break}}
 d.to=to;var ref=rows[to]||(rows.length?rows[rows.length-1].nextSibling:d.row.nextSibling);
 if(rows[to])d.list.insertBefore(d.ind,rows[to]);else d.list.insertBefore(d.ind,ref);
 var dl=dlg.querySelector('.mt-bd'),br=dl&&dl.getBoundingClientRect();if(br){if(e.clientY<br.top+30)dl.scrollTop-=8;else if(e.clientY>br.bottom-30)dl.scrollTop+=8}}
function dend(ok){var d=drag;drag=null;d.pv.remove();d.ind.remove();d.row.classList.remove('mt-dragging');
 if(!ok){focusGrip(d.k);return}
 var t=picks().slice(),i=t.indexOf(d.k);t.splice(i,1);t.splice(d.to,0,d.k);var ch=t.join()!==picks().join();
 setOrder(t,true);focusGrip(d.k);if(ch)say(NAME[d.k]+' moved. '+posMsg(d.k)+'.')}
function focusSel(a,b){var e=dlg.querySelector(a);if(!e||e.disabled)e=b&&dlg.querySelector(b);e&&e.focus()}
SECTIONS.push({id:'teams',title:'My teams',render:teamSection});
/* header button */
function headerBtn(){var inr=D.querySelector('header.top .in');if(!inr||inr.querySelector('.mtbtn'))return;
 var b=h('button',{type:'button','class':'mtbtn','aria-haspopup':'dialog','aria-controls':'mt-panel','aria-label':'My team',on:{click:openPanel}});b.innerHTML=GEAR+'<span class="mtbtn-t">My team</span>';
 var bg=inr.querySelector('.burger');if(bg)inr.insertBefore(b,bg);else inr.appendChild(b);var top=inr.parentNode;top.classList.add('mthd');fitHdr();if(W.ResizeObserver)new ResizeObserver(fitHdr).observe(inr);else W.addEventListener('resize',fitHdr);D.fonts&&D.fonts.ready&&D.fonts.ready.then(fitHdr)}
/* container check: drop to the 44px gear whenever the full label would crowd the wordmark or nav */
function hit(a,b){return a.left<b.right-.5&&b.left<a.right-.5&&a.top<b.bottom-.5&&b.top<a.bottom-.5}
function fitHdr(){var top=D.querySelector('header.top.mthd');if(!top)return;var br=top.querySelector('.brand'),b=top.querySelector('.mtbtn');if(!br||!b)return;top.classList.remove('mt-ico','mt-tight');
 function bad(pad){var r=[br,b].concat([].slice.call(top.querySelectorAll('#site-nav>a,#site-nav>.ndd'))).filter(function(e){return e.getClientRects().length&&getComputedStyle(e.closest('nav')||e).position!=='absolute'}).map(function(e){var q=e.getBoundingClientRect();return e===br?{left:q.left,top:q.top,bottom:q.bottom,right:q.right+(pad||0)}:q});for(var i=0;i<r.length;i++)for(var j=i+1;j<r.length;j++)if(hit(r[i],r[j]))return true;var ir=top.querySelector('.in').getBoundingClientRect();return br.getBoundingClientRect().left<ir.left-1||b.getBoundingClientRect().right>Math.min(ir.right,innerWidth)+1}
 if(bad(16))top.classList.add('mt-ico');if(bad(0))top.classList.add('mt-tight')}
/* first-visit bar and the filter strip live in the page flow (never fixed) */
var bar,strip;
function slot(el){var m=D.querySelector('main');if(m)m.insertBefore(el,m.firstChild);else{var t=D.querySelector('header.top');t&&t.parentNode.insertBefore(el,t.nextSibling)}}
function ui(){
 var showBar=!S&&get(KB)!=='1';
 if(showBar&&!bar){bar=h('div',{'class':'mt-bar',role:'region','aria-label':'Pick your teams'},[h('div',{'class':'mt-in'},[h('span',{'class':'mt-bt',text:'Follow your teams first.'}),h('button',{type:'button','class':'mt-go',on:{click:openPanel}},['Pick your teams']),h('button',{type:'button','class':'mt-dis','aria-label':'Dismiss',on:{click:function(){put(KB,'1');ui()}}},['Not now'])])]);slot(bar)}
 if(!showBar&&bar){bar.parentNode&&bar.parentNode.removeChild(bar);bar=null}
 var pk=picks(),needStrip=C&&C.f&&pk.length;
 if(needStrip){if(!strip){strip=h('div',{'class':'mt-strip',role:'region','aria-label':'My teams filter'});slot(strip)}
  strip.innerHTML='';var sw=h('button',{type:'button',role:'switch','class':'mt-sw','aria-checked':S.showAll?'true':'false',on:{click:function(){S.showAll=!S.showAll;save();var e=strip&&strip.querySelector('.mt-sw');e&&e.focus()}}},[h('span',{'class':'mt-tr','aria-hidden':'true'},[h('span',{'class':'mt-kn'})]),'Show all teams']);
  strip.appendChild(h('div',{'class':'mt-in'},[h('span',{'class':'mt-st'},[h('b',{text:S.showAll?'All teams':'My teams'}),S.showAll?'':': '+pk.map(function(k){return NAME[k]}).join(', ')]),sw,h('button',{type:'button','class':'mt-ed',on:{click:openPanel}},['Edit'])]))}
 else if(strip){strip.parentNode&&strip.parentNode.removeChild(strip);strip=null}
 D.documentElement.classList.toggle('mt-filtered',!!filtering())}
function fire(){ui();applyPage();try{W.dispatchEvent(new CustomEvent('msm:settings',{detail:API.get()}))}catch(e){}}
W.addEventListener('storage',function(e){if(e.key===K||e.key===KB){S=load();fire();if(dlg&&dlg.open)renderPanel()}});
function init(){headerBtn();ui();applyPage();watch()}
if(D.readyState==='loading')D.addEventListener('DOMContentLoaded',init);else init();
})();
