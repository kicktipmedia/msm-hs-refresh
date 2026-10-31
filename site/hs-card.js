/* hs-card.js: kickoff countdown + NWS kickoff forecast for HS game cards (article.hsc[data-kickoff]). Logic copied from the college .c1 card script. */
(function(){
var A=[].slice.call(document.querySelectorAll('article.hsc[data-kickoff],article[data-level="hs"][data-kickoff],.g[data-kickoff]'));if(!A.length)return;
function pad(n){return(n<10?'0':'')+n}
function tick(){A.forEach(function(a){var k=a.dataset.kickoff;if(!k)return;var st=a.dataset.gameState;if(st==='live'||st==='final')return;
 var c=a.querySelector('.cd');if(!c)return;var d=Date.parse(k)-Date.now();
 if(d<=-5*36e5){a.dataset.gameState='final';c.innerHTML='<div class="lbl"><i>FINAL</i></div>';c.setAttribute('aria-label','Final');return}
 if(d<=0){if(st!=='kickoff'){a.dataset.gameState='kickoff';c.innerHTML='<div class="st"><b>KICKOFF</b></div>';c.setAttribute('aria-label','Kickoff')}return}
 var m=Math.floor(d/6e4),D=Math.floor(m/1440),H=Math.floor(m%1440/60),M=m%60,b=c.querySelectorAll('b');
 if(b.length>=3){b[0].textContent=D;b[1].textContent=pad(H);b[2].textContent=pad(M)}
 c.setAttribute('aria-label','Kickoff in '+D+' days '+H+' hours '+M+' minutes')})}
tick();setInterval(tick,3e4);
// weather: NWS hourly forecast at kickoff, within 7 days only; any failure stays hidden (space stays reserved)
var MAP=[[/snow|flurr|sleet/i,'snow'],[/rain|shower|thunder|drizzle/i,'rain'],[/breezy|windy/i,'wind'],[/partly|mostly sunny/i,'partly'],[/cloudy|overcast/i,'cloud'],[/sunny|clear/i,'sun']];
function ic(s){for(var i=0;i<MAP.length;i++)if(MAP[i][0].test(s))return MAP[i][1];return ''}
function ls(k,v,ttl){try{if(v===undefined){var o=JSON.parse(localStorage.getItem(k)||'null');return o&&(!o.x||o.x>Date.now())?o.v:null}localStorage.setItem(k,JSON.stringify({v:v,x:ttl?Date.now()+ttl:0}))}catch(e){return null}}
function get(u){return fetch(u,{headers:{Accept:'application/geo+json'}}).then(function(r){if(!r.ok)throw 0;return r.json()})}
if(window.fetch)A.forEach(function(a){var w=a.querySelector('.wx[data-wx-state="hidden"][data-lat]'),k=Date.parse(a.dataset.kickoff||'');if(!w||!k)return;
 var d=k-Date.now();if(d<0||d>7*864e5)return;var pk='msm-wxp-'+w.dataset.venue,fk='msm-wxf-'+w.dataset.venue;
 var p=ls(pk)?Promise.resolve(ls(pk)):get('https://api.weather.gov/points/'+w.dataset.lat+','+w.dataset.lon).then(function(j){var u=j.properties.forecastHourly;ls(pk,u,7*864e5);return u});
 p.then(function(u){var c=ls(fk);return c?c:get(u).then(function(j){var pp=j.properties.periods.map(function(x){return[x.startTime,x.endTime,x.temperature,x.shortForecast]});ls(fk,pp,36e5);return pp})})
 .then(function(pp){for(var i=0;i<pp.length;i++){if(Date.parse(pp[i][0])<=k&&k<Date.parse(pp[i][1])){var n=ic(pp[i][3]);if(!n)return;
  w.querySelector('use').setAttribute('href','#wx-'+n);w.querySelector('svg').setAttribute('aria-label',pp[i][3]);w.querySelector('.t,.t2').textContent=pp[i][2]+'°';w.dataset.wxIcon=n;w.dataset.wxState='forecast';return}}}).catch(function(){try{localStorage.removeItem(pk)}catch(e){}})})
})();

(function(){function go(){var h=location.hash.slice(1);if(!/^hs-/.test(h))return;var e=document.getElementById(h);if(!e)return;var p=e.closest('[role=tabpanel]');
if(p&&p.hidden){var t=document.querySelector('[aria-controls="'+p.id+'"]');if(t)t.click()}setTimeout(function(){e.scrollIntoView()},0)}
go();addEventListener('hashchange',go)})();
