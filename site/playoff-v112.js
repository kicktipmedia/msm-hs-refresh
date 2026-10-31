/* shared guardrails (next107): used by _worker.js (server) and playoff-v106.js (browser) */
var MSMG=(function(){
var BAN=/\b(predict(?:s|ed|ing|ion|ions|or)?|project(?:ed|ion|ions|s)?|forecasts?|forecasted|odds|chances?|likely|likelihood|will make|locks?|locked|percent(?:age)?|probabilit(?:y|ies)|bet|bets|betting|wager\w*|spreads?|moneyline|parlay\w*|sportsbook\w*|over\/under|vegas|favou?rite[sd]?|underdogs?|power rankings?|robbed|snub\w*|rigged|r\u00e9sum\u00e9|r\u00e9sume|resum\u00e9)\b/i;
var SCORE=/\b\d{1,3}\s*[-\u2013\u2014]\s*\d{1,3}\b|\bpoints?\b|\btouchdowns?\b/i;
var PROF=/\b(f+u+c+k\w*|sh[i1]t\w*|b[i1]tch\w*|a+ss+hole\w*|cunt\w*|d[i1]ck\w*|bastard\w*|slut\w*|whore\w*|fag\w*|n[i1]gg\w*|retard\w*|kill yourself|kys|stupid|idiot\w*|moron\w*|dumb\w*|suck\w*|trash)\b/i;
var INJ=/(ignore|disregard|forget)\b.{0,30}\b(instruction|prompt|rule|above|previous)|system prompt|you are now|jailbreak|<\/?[a-z]|https?:\/\/|\bjavascript:/i;
var FB=/\b(win|wins|won|beat|beats|lose|loses|lost|loss|champ|champion|title|conference|seed|bracket|playoff|ranked|rank|upset|undefeated|drops?|climbs?|jumps?|falls?|spots?)\b/i;
var BAD_FACT=/\b(injur\w*|quarterback|qb|coach\w*|player\w*|said|says|quote\w*|suspend\w*|transfer\w*)\b/i;
var CLAIM=/\b(no\.?\s*\d+|number\s+\d+|#\s*\d+|\d+(st|nd|rd|th)\b|top[- ]?\d+|ranked|unranked|ranking|rankings|rank|record|undefeated|unbeaten|winless|perfect season|poll|polls|ap|coaches|cfp|seeds?|seeded)\b|\d+\s*[-\u2013]\s*\d+/i;
function noClaims(s){ /* drop any sentence that states a rank, record or poll status; code adds those facts from our json */
  if(typeof s!=='string')return'';s=s.replace(/\b(no|nos)\.\s*(?=\d)/gi,'No ').replace(/(\d)\.(\d)/g,'$1,$2');return (s.match(/[^.!?]+[.!?]*/g)||[]).map(function(x){return x.trim()}).filter(function(x){return x&&!CLAIM.test(x)}).join(' ');
}
function clean(s,max){ /* plain text only; null when it trips a guard */
  if(typeof s!=='string')return'';if(/[<>]|\bon\w+\s*=|\bscript\b|alert\s*\(/i.test(s))return null;s=s.replace(/[\u0000-\u001f<>`{}\[\]]/g,' ').replace(/\s+/g,' ').trim();
  if(!s)return'';if(BAN.test(s)||SCORE.test(s)||PROF.test(s)||INJ.test(s)||BAD_FACT.test(s))return null;
  if(s.length>(max||140))s=s.slice(0,(max||140)-1).replace(/\s\S*$/,'')+'.';return s;
}
function screen(q){ /* input filter: returns code or '' */
  if(typeof q!=='string'||!q.trim())return'empty';if(q.length>200)return'long';
  if(PROF.test(q))return'profanity';if(INJ.test(q))return'offtopic';if(BAN.test(q))return'banned';return'';
}
/* validate AI JSON against our FBS team list; byS: lowercased short/full name -> team */
var CONF={acc:1,big10:1,big12:1,sec:1,American:1,usa:1,midam:1,mwest:1,pac12:1,belt:1};
var CALIAS={'acc':'acc','big ten':'big10','big 10':'big10','b1g':'big10','big10':'big10','big 12':'big12','big12':'big12','sec':'sec','american':'American','aac':'American','conference usa':'usa','c-usa':'usa','cusa':'usa','usa':'usa','mac':'midam','midam':'midam','mountain west':'mwest','mwest':'mwest','pac-12':'pac12','pac 12':'pac12','pac12':'pac12','sun belt':'belt','belt':'belt'};
/* FCS opponents we recognize (not ranked; strength uses the FCS conference value) */
var FCSL=['Southern Utah','Weber State','Utah Tech','Idaho State','Idaho','Montana','Montana State','Eastern Washington','Northern Arizona','Sacramento State','UC Davis','Portland State','Cal Poly','North Dakota State','South Dakota State','North Dakota','South Dakota','Northern Iowa','Abilene Christian','Tarleton State','Incarnate Word','Villanova','William & Mary','Richmond','Furman','Mercer','Chattanooga','Samford','Lehigh','Harvard','Yale','Princeton'];
var FCSO={};FCSL.forEach(function(n){FCSO[n.toLowerCase()]={n:n,s:n,c:'fcs',id:null,r:999,rec:'',fcs:1}});
function validate(o,byS){ /* next107: the AI only returns game results; code applies the Resume formula */
  if(!o||typeof o!=='object'||o.understood===false)return null;
  var out={games:[],solo:[],champs:{},notc:{},explain:''},n=0,seen={};
  var team=function(x){return typeof x==='string'?byS[x.toLowerCase().trim()]:null},teamF=function(x){return team(x)||(typeof x==='string'?FCSO[x.toLowerCase().trim()]:null)||null};
  (Array.isArray(o.games)?o.games.slice(0,6):[]).forEach(function(g){if(!g)return;var w=teamF(g.winner),l=teamF(g.loser);if(!w||!l||w===l||(w.fcs&&l.fcs))return;var k=[w.n,l.n].sort().join('|');if(seen[k])return;seen[k]=1;
    out.games.push({w:w.n,l:l.n,title:g.title===true&&w.c===l.c&&!w.fcs});n++});
  (Array.isArray(o.results)?o.results.slice(0,6):[]).forEach(function(r){if(!r)return;var t=team(r.team),res=String(r.result||'').toLowerCase();if(!t||['win','loss','wins_out'].indexOf(res)<0)return;
    if(out.games.some(function(g){return g.w===t.n||g.l===t.n})&&res!=='wins_out')return;var k=Math.round(Number(r.count))||1;out.solo.push({n:t.n,res:res,k:Math.max(1,Math.min(3,k))});n++});
  (Array.isArray(o.champs)?o.champs.slice(0,10):[]).forEach(function(c){if(!c)return;var cf=CALIAS[String(c.conference||'').toLowerCase().trim()]||(CONF[c.conference]?c.conference:null),t=team(c.team);if(cf&&t&&t.c===cf&&!out.champs[cf]){out.champs[cf]=t.n;n++}});
  var ex=clean(noClaims(o.explain),220);out.explain=ex||'';
  return n?out:null;
}
return{FCSO:FCSO,FCSL:FCSL,CLAIM:CLAIM,noClaims:noClaims,BAN:BAN,clean:clean,screen:screen,validate:validate,FB:FB,CALIAS:CALIAS};
})();
if(typeof module!=='undefined')module.exports=MSMG;
/* next107 MSM Playoff Picture: What If with an AI helper (server-side Workers AI at /api/whatif) and three views.
   The AI only reads the scenario into game results; the Resume formula (formula.part) moves teams; this file validates its JSON (MSMG.validate) and does all seeding with the CFP rules.
   If the AI is busy, errors or is rate limited, the simple rules parser below runs instead. Reads /data/msm-rankings.json and /data/ap-top25.json. */
(function(){
var root=document.getElementById('po');if(!root)return;
var CN={acc:'ACC',big10:'Big Ten',big12:'Big 12',sec:'SEC',American:'American',usa:'Conference USA',midam:'MAC',mwest:'Mountain West',pac12:'Pac-12',belt:'Sun Belt',ind:'Independent'};
var P4=['acc','big10','big12','sec'],G6=['American','usa','midam','mwest','pac12','belt'];
var UT={'BYU Cougars':'/team/byu/','Utah Utes':'/team/utah/','Utah State Aggies':'/team/usu/'};function UC(n){var u=UT[n];return u?'instate t-'+u.split('/')[2]:''}
/* ===== COPY CONSTANTS: swap wording here only (approved by Jared, Oct 23, 2026) ===== */
var C={
  LABEL:'Hypothetical: your scenario, not an MSM ranking or prediction',
  RULES_AI:'AI-generated what-if. It can be wrong. Check the official CFP rankings.',
  TABS:{msm:'Our Rankings',ap:'AP Poll',cm:'Committee Style'},
  CM_NOTE:'Based on how the committee handled the 2024 and 2025 seasons under the 12-team format. It is not what the committee will do.',
  PRESETS:['Utah wins out','BYU wins the Big 12','Utah beats BYU in the Big 12 title game','Utah State wins the Pac-12']
};
/* ===== end constants ===== */
var LABEL=C.LABEL,VN=C.TABS;var RS={},CMN=null,FLIP={},PCH={},ITAB='type'; /* input tabs: 'pick' (champions + flips) or 'type' (AI); never combined */
var D,T,AP=null,APR={},RD=0,VIEW='full',ZOOM=true,Q='',MSG=null,VW='msm',MODE=null,EXPL='',BUSY=false,BASE={};
function blank(){return{champ:{},notc:{},ops:[],lines:[],miss:[],why:[]}}
var SV={msm:blank(),ap:blank(),cm:blank()};
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function ord(n){var s=['th','st','nd','rd'],v=n%100;return n+(s[(v-20)%10]||s[v]||s[0])}
function byN(n){return T.filter(function(x){return x.n===n})[0]}
function baseOrder(v){
  var m=T.slice().sort(function(a,b){return a.r-b.r});if(v==='msm'||!AP)return m;
  var R=(v==='cm'&&AP.cfp_published&&AP.cfp&&AP.cfp.ranks&&AP.cfp.ranks.length)?AP.cfp.ranks:AP.ranks; /* data flag: switch the committee view to the official CFP rankings once published */
  var ranked=R.map(function(x){return T.filter(function(t){return t.id===x.id})[0]}).filter(Boolean);
  return ranked.concat(m.filter(function(t){return ranked.indexOf(t)<0}));
}
function order(v){
  var o=baseOrder(v),S=SV[v];
  S.ops.forEach(function(op){var i=o.indexOf(op.t);if(i<0)return;o.splice(i,1);var j=op.to!=null?op.to-1:i+op.d;j=Math.max(0,Math.min(o.length,j));o.splice(j,0,op.t)});
  if(v==='cm'&&typeof cmRules==='function')o=cmRules(o,S);
  return o.map(function(t,i){var c={};for(var k in t)c[k]=t[k];c.r=i+1;c.r0=t.r;c.src=t;return c});
}
function confChamp(W,c,S){var ex=S.notc[c]||[];if(S.champ[c]){var p=W.filter(function(x){return x.n===S.champ[c]})[0];if(p)return p}return W.filter(function(x){return x.c===c&&ex.indexOf(x.n)<0})[0]}
function build(v){
  v=v||VW;var S=SV[v],W=order(v),auto={};
  /* CFP rule: the five highest-ranked conference champions get bids (CFP, Dec. 7, 2025) */
  P4.concat(G6).map(function(c){var t=confChamp(W,c,S);return t?[t,c]:null}).filter(Boolean).sort(function(a,b){return a[0].r-b[0].r}).slice(0,5).forEach(function(x){auto[x[0].n]=CN[x[1]]+' champion'});
  var field=W.filter(function(x){return auto[x.n]});
  W.forEach(function(x){if(field.length<12&&!auto[x.n])field.push(x)});
  field.sort(function(a,b){return a.r-b.r});
  var top=field.filter(function(x){return x.r<=12||!auto[x.n]}),bot=field.filter(function(x){return x.r>12&&auto[x.n]});
  field=top.concat(bot);field.forEach(function(x,i){x.seed=i+1});
  var inF={};field.forEach(function(x){inF[x.n]=1});
  return{W:W,field:field,auto:auto,out:W.filter(function(x){return !inF[x.n]})};
}
/* ---------- plain-text scenario parser ---------- */
var AL=null,CA=[['big 12','big12'],['big12','big12'],['big xii','big12'],['b12','big12'],['b 12','big12'],['big ten','big10'],['big 10','big10'],['big10','big10'],['b1g','big10'],['acc','acc'],['sec','sec'],['mountain west','mwest'],['mwc','mwest'],['sun belt','belt'],['american','American'],['aac','American'],['mac','midam'],['conference usa','usa'],['c usa','usa'],['cusa','usa'],['pac 12','pac12'],['pac12','pac12']];
var XA={bama:'Alabama',osu:'Ohio State',tosu:'Ohio State',buckeyes:'Ohio State',nd:'Notre Dame',irish:'Notre Dame','the u':'Miami',canes:'Miami',usu:'Utah State',utes:'Utah',cougs:'BYU','the y':'BYU',jmu:'James Madison',ttu:'Texas Tech',uga:'Georgia',tamu:'Texas A&M','a m':'Texas A&M',unc:'North Carolina',ou:'Oklahoma',psu:'Penn State',fsu:'Florida State',uh:'Houston',zona:'Arizona',asu:'Arizona State',wake:'Wake Forest',ksu:'Kansas State',isu:'Iowa State',okst:'Oklahoma State',boise:'Boise State',wvu:'West Virginia',sdsu:'San Diego State',miss:'Ole Miss','miss state':'Mississippi State'};
var NW={one:1,two:2,three:3,four:4,five:5,six:6,seven:7,eight:8,nine:9,ten:10,eleven:11,twelve:12,fifteen:15,twenty:20,a:1,an:1};
function norm(s){return' '+String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[\u2019']s\b/g,'').replace(/#\s*/g,' no ').replace(/[^a-z0-9& ]+/g,' ').replace(/&/g,' ').replace(/\s+/g,' ').trim()+' '}
function aliases(){
  if(AL)return AL;var m={},add=function(k,t){k=norm(k).trim();if(k&&k.length>1&&!m[k])m[k]=t};
  var R=T.slice().sort(function(a,b){return a.r-b.r});
  R.forEach(function(t){add(t.s,t);add(t.n,t)});
  R.forEach(function(t){var nk=t.n.slice(t.s.length).trim();if(nk)add(nk,t)});
  MSMG.FCSL.forEach(function(n){add(n,MSMG.FCSO[n.toLowerCase()])});
  for(var k in XA){var t=R.filter(function(x){return x.s===XA[k]})[0];if(t)add(k,t)}
  AL=Object.keys(m).sort(function(a,b){return b.length-a.length}).map(function(k){return[k,m[k]]});return AL;
}
function scan(c){ /* teams and conference mentions in order of appearance */
  var s=c,hits=[];
  CA.forEach(function(a){var i=s.indexOf(' '+a[0]+' ');if(i>=0){hits.push({i:i,cf:a[1]});s=s.slice(0,i+1)+a[0].replace(/./g,'_')+s.slice(i+1+a[0].length)}});
  aliases().forEach(function(a){var i;while((i=s.indexOf(' '+a[0]+' '))>=0){hits.push({i:i,t:a[1]});s=s.slice(0,i+1)+a[0].replace(/[^ ]/g,'_')+s.slice(i+1+a[0].length)}});
  hits.sort(function(a,b){return a.i-b.i});
  return{teams:hits.filter(function(h){return h.t}).map(function(h){return h.t}),conf:(hits.filter(function(h){return h.cf})[0]||{}).cf,rest:s};
}
function num(s){var m=s.match(/ (\d{1,3}) /);if(m)return+m[1];for(var w in NW){if(new RegExp(' '+w+' (spots?|places?|positions?|slots?|teams?) ').test(s))return NW[w]}return null}
function parse(txt){
  var sc=newSc(),subj=null,raw=String(txt).trim();
  if(!raw)return sc;
  var parts=norm(raw.replace(/[,;.!?]+/g,' | ')).replace(/ (and then|and|then|but|while|plus|also) /g,' | ').split('|');
  parts.forEach(function(p){
    p=' '+p.trim()+' ';if(!p.trim())return;
    var S=scan(p),tm=S.teams,r=S.rest,cf=S.conf,a=tm[0]||subj,b=tm[1];
    if(a)subj=a;
    var lose2=/ (lose|loses|lost|losing|fall|falls|fell) (to|at|against|vs) | (upset|beaten|beat|stunned|knocked off) by /.test(r);
    var win2=/ (beat|beats|beating|defeat|defeats|defeated|upset|upsets|top|tops|stun|stuns|knock off|knocks off|knocked off|handle|handles|over|takes down|take down|win|wins|won) /.test(r);
    var w=null,l=null;
    if(a&&b&&a!==b&&!(a.fcs&&b.fcs)&&(lose2||win2)){if(lose2){l=a;w=b}else{w=a;l=b}}
    if(w&&l){
      var ttl=!!(cf&&/ (title|championship|ccg|final) /.test(r)&&w.c===cf&&l.c===cf);
      sc.games.push({w:w.src||w,l:l.src||l,title:ttl});sc.lines.push(w.s+' beats '+l.s+(ttl?' in the '+CN[cf]+' title game':''));
      if(ttl){sc.champ[cf]=w.n;sc.lines.push(w.s+' wins the '+CN[cf])}
      subj=w===a?a:a;return;
    }
    if(!a||a.fcs){sc.miss.push(p.trim());return}
    var t=a;
    if(cf){
      if(t.c!==cf){sc.miss.push(t.s+' is not in the '+CN[cf]);return}
      if(/ (lose|loses|lost|miss|misses|missed|fall|falls|fell|does not win|doesnt win|dont win) /.test(r)){(sc.notc[cf]=sc.notc[cf]||[]).push(t.n);if(sc.champ[cf]===t.n)delete sc.champ[cf];var tg=/ (title|championship|ccg|game) /.test(r);if(tg)sc.games.push({w:null,l:t,title:true,ref:nextBest(t,cf)});sc.lines.push(t.s+' does not win the '+CN[cf]+(tg?' (loses the title game)':''));return}
      if(/ (win|wins|won|take|takes|took|claim|claims|clinch|clinches|champ|champs|champion|champions|capture|captures) /.test(r)){sc.champ[cf]=t.n;sc.games.push({w:t,l:null,title:true,ref:nextBest(t,cf)});sc.lines.push(t.s+' wins the '+CN[cf]+' (wins the title game)');return}
    }
    var m=r.match(/ (no|number|rank|ranked|to) (\d{1,3}) /);
    if(m&&!/ (spot|spots|place|places|position|positions) /.test(r)){var to=Math.max(1,Math.min(T.length,+m[2]));sc.moves.push({t:t,to:to});sc.lines.push(t.s+' moves to No. '+to+' (your move, not the formula)');return}
    var n=num(r);
    if(n!=null&&/ (up|climb|climbs|jump|jumps|rise|rises|gain|gains|move up|moves up|higher) /.test(r)){sc.moves.push({t:t,d:-n});sc.lines.push(t.s+' moves up '+n+(n===1?' spot':' spots')+' (your move, not the formula)');return}
    if(n!=null&&/ (down|drop|drops|fall|falls|slide|slides|slip|slips|sink|sinks|lower|tumble|tumbles) /.test(r)){sc.moves.push({t:t,d:n});sc.lines.push(t.s+' drops '+n+(n===1?' spot':' spots')+' (your move, not the formula)');return}
    if(/ (win|wins|won|run|runs) (out|the table) | undefeated | unbeaten /.test(r)){solo(sc,t,'wins_out');return}
    var k=/ (twice|two games|2 games) /.test(r)?2:/ (three times|3 games|three games) /.test(r)?3:1;
    if(/ (lose|loses|lost|losing|stumble|stumbles|upset|upsets|slip|slips) /.test(r)){solo(sc,t,'loss',k);return}
    if(/ (win|wins|won) /.test(r)){solo(sc,t,'win',k);return}
    sc.miss.push(p.trim());
  });
  return sc;
}
/* ---------- next107: the MSM Resume formula. Deterministic and published on the page ("How teams move").
   Modeled on the CFB Ranks game-by-game method (cfbranks.com/methodology): base points for a win or loss, a location
   modifier, opponent strength from conference strength and opponent rank, bigger credit for beating strong teams,
   bigger penalties for losing to weak ones, quality-win bonuses and a conference title game adjustment.
   We leave out margin of victory and anything tied to betting lines. ---------- */
var FM={
  WIN:10,LOSS:10,                       /* base value of a win and of a loss */
  SITE:{home:[0.9,1.2],away:[1.2,0.8],neutral:[1.05,1.0]}, /* [win, loss] multipliers by location */
  CONF:{sec:1.2,big10:1.15,ind:1.0,big12:0.95,acc:0.85,American:0.6,usa:0.6,midam:0.6,mwest:0.6,pac12:0.6,belt:0.6},
  FCS_CONF:0.3,
  RANK_TOP:1.5,RANK_DECAY:0.97,MIX:0.5, /* opponent strength = 0.5 x conference + 0.5 x 1.5 x 0.97^(rank - 1) */
  WIN_ADD:0.3,                          /* win multiplier = 0.3 + opponent strength */
  LOSS_BASE:1.9,LOSS_SLOPE:0.9,         /* loss multiplier = 1.9 - 0.9 x opponent strength */
  Q:[[5,5],[10,3],[25,1.5]],            /* quality win bonus by opponent rank in this view */
  CM_Q:1.5,                             /* committee view: quality win bonus x 1.5 */
  TITLE_W:1.25,TITLE_L:0.5,             /* conference title game: win x 1.25, loss x 0.5 */
  SOS_W:20,                             /* schedule strength term: 20 x (opponent strength - schedule average) / (games + 1) */
  PER_SPOT:2.5,MAX:15                   /* 2.5 Resume = one spot; at most 15 spots per scenario */
};
var FPOS={};
function fpos(v){if(FPOS[v])return FPOS[v];var m={};baseOrder(v).forEach(function(t,i){m[t.n]=i+1});return FPOS[v]=m}
function rstr(r){return FM.RANK_TOP*Math.pow(FM.RANK_DECAY,Math.max(1,r)-1)}
function oppS(o,v){return FM.MIX*(o.fcs?FM.FCS_CONF:(FM.CONF[o.c]||0.6))+(1-FM.MIX)*rstr(fpos(v)[o.n]||T.length+1)}
function sosS(t){var r=RS[t.id];return FM.MIX*(FM.CONF[t.c]||0.6)+(1-FM.MIX)*rstr(r&&r.sos?r.sos:T.length/2)}
function gp(t){var r=RS[t.id];if(r&&r.gp)return r.gp;var m=String(t.rec).match(/\d+/g)||[];return m.reduce(function(a,b){return a+ +b},0)}
function site(t,o,title){if(title||!o)return'neutral';var r=RS[t.id],g=r&&r.rest?r.rest.filter(function(x){return x.o===o.id})[0]:null;return!g?'neutral':g.n?'neutral':g.h?'home':'away'}
function r1(x){return Math.round(x*10)/10}
function sg(x){x=r1(x);return(x>0?'+':x<0?'\u2212':'')+Math.abs(x).toFixed(1)}
/* one game for team t. o = opponent (moves too), ref = strength reference only (not moved), null = average opponent */
function gameF(t,o,won,v,title,ref){
  var so=o||ref,S=so?oppS(so,v):sosS(t),st=site(t,o,title),m=FM.SITE[st][won?0:1],pos=so?(fpos(v)[so.n]||999):999,q=0,base,mul;
  if(won){mul=FM.WIN_ADD+S;base=FM.WIN*m*mul;if(so)FM.Q.some(function(x){if(pos<=x[0]){q=x[1]*(v==='cm'?FM.CM_Q:1);return true}})}
  else{mul=Math.max(0.3,FM.LOSS_BASE-FM.LOSS_SLOPE*S);base=-FM.LOSS*m*mul}
  var tm=title?(won?FM.TITLE_W:FM.TITLE_L):1,res=(base+q)*tm,sos=so?FM.SOS_W*(S-sosS(t))/(gp(t)+1):0;
  return{t:t,o:so,ref:!o&&!!ref,won:won,S:S,st:st,m:m,mul:mul,base:base,q:q,pos:pos,tm:tm,res:res,sos:sos,pts:res+sos,title:title,v:v};
}
function gtxt(g){
  var who=g.o?(g.ref?'the next-best '+CN[g.o.c]+' team ('+g.o.s+')':g.o.s+(g.o.fcs?' (FCS)':'')):'an average opponent on its schedule';
  var a=(g.title?(g.won?'Title game win over ':'Title game loss to '):(g.won?'Win over ':'Loss to '))+who+': ';
  var p=[];p.push((g.won?'win 10':'loss 10')+' x '+g.st+' '+g.m+' x '+(g.won?'(0.3 + opponent strength '+g.S.toFixed(2)+')':'(1.9 - 0.9 x opponent strength '+g.S.toFixed(2)+')')+' = '+sg(g.base));
  if(g.q)p.push((g.pos<=5?'Top 5':g.pos<=10?'Top 10':'Top 25')+' win bonus '+sg(g.q));
  if(g.title)p.push('title game x '+g.tm);
  if(g.o&&Math.abs(g.sos)>=0.05)p.push('schedule strength '+sg(g.sos));
  return a+p.join(', ')+'.';
}
/* scenario: {games:[{w,l,title,ref}], champ, notc, moves:[{t,d}|{t,to}], lines, miss}; w or l may be null (unnamed opponent) */
function applyF(sc){
  ['msm','ap','cm'].forEach(function(v){
    var S=blank(),acc={},ord=[];for(var c in sc.champ)S.champ[c]=sc.champ[c];for(var c2 in sc.notc)S.notc[c2]=sc.notc[c2].slice();
    S.lines=sc.lines.slice();S.miss=sc.miss.slice();S.why=[];S.tl=[];S.tw=[];sc.games.forEach(function(g){if(!g.title)return;if(g.l&&!g.l.fcs)S.tl.push(g.l.n);if(g.w&&!g.w.fcs)S.tw.push(g.w.n)});
    var add=function(g){if(g.t.fcs)return;var n=g.t.n;if(!acc[n]){acc[n]={t:g.t,pts:0,gs:[]};ord.push(n)}acc[n].pts+=g.pts;acc[n].gs.push(g)};
    sc.games.forEach(function(g){if(g.w)add(gameF(g.w,g.l,true,v,g.title,g.ref));if(g.l)add(gameF(g.l,g.w,false,v,g.title,g.ref))});
    ord.forEach(function(n){var a=acc[n],x=a.pts,d=Math.round(Math.abs(x)/FM.PER_SPOT);if(Math.abs(x)>=0.5)d=Math.max(1,d);d=Math.min(FM.MAX,d)*(x>0?-1:1);
      if(d)S.ops.push({t:a.t,d:d});var gs=a.gs.slice().sort(function(p,q){return Math.abs(q.pts)-Math.abs(p.pts)}),more=gs.slice(3);S.why.push({t:a.t,d:d,pts:x,txt:gs.slice(0,3).map(gtxt).join(' ')+(more.length?' Plus '+more.length+' more result'+(more.length>1?'s':'')+', '+sg(more.reduce(function(s,g){return s+g.pts},0))+'.':'')+(Math.abs(d)===FM.MAX&&Math.abs(x)/FM.PER_SPOT>FM.MAX?' Capped at '+FM.MAX+' spots.':'')})});
    (sc.moves||[]).forEach(function(m){S.ops.push(m)});
    SV[v]=S;
  });
}
function rest(t){var r=RS[t.id];return r&&r.rest?r.rest.map(function(x){return T.filter(function(y){return y.id===x.o})[0]}).filter(Boolean):[]}
function nextBest(t,cf,v){return baseOrder(v||'msm').filter(function(x){return x.c===cf&&x.n!==t.n})[0]||null}
/* turn a single-team result into games with opponents from its remaining schedule; unnamed opponents count as average */
function solo(sc,t,res,k){
  var R=rest(t),cf=t.c;
  if(res==='wins_out'){R.forEach(function(o){sc.games.push({w:t,l:o})});if(CN[cf]&&cf!=='ind'&&P4.concat(G6).indexOf(cf)>=0){var nb=nextBest(t,cf);sc.games.push({w:t,l:null,title:true,ref:nb});sc.champ[cf]=t.n}
    sc.lines.push(t.s+' wins out'+(R.length?': wins over '+R.map(function(x){return x.s}).join(', '):'')+(sc.champ[cf]===t.n?', plus the '+CN[cf]+' title game':''));return}
  for(var i=0;i<k;i++){var o=R[i]||null;sc.games.push(res==='win'?{w:t,l:o}:{w:o,l:t})}
  sc.lines.push(t.s+(res==='win'?' wins':' loses')+(k>1?' '+k+' games':'')+(R.length?' ('+(res==='win'?'over ':'to ')+R.slice(0,k).map(function(x){return x.s}).join(', ')+', from its schedule)':' (opponent not named, counted as an average opponent)'));
}
function newSc(){return{games:[],champ:{},notc:{},moves:[],lines:[],miss:[]}}
/* ---------- next107: committee patterns (deterministic, from the 2024 and 2025 final CFP rankings in data/committee-notes.json) ---------- */
var CMR={
  titleloss:{t:'Title game loss',p:'A team that loses its conference title game does not fall below at-large teams it was ranked ahead of.',ids:['smu24','tlg24','bama25']},
  autobid:{t:'Champion bid',p:'The five highest-ranked conference champions get in, even from low in the rankings.',ids:['clem24','g625','asu24']},
  seed:{t:'Seeds follow the ranking',p:'Seeds follow the final ranking. The top four teams get byes, with or without a conference title.',ids:['seed25']},
  bubble:{t:'Bubble',p:'At the cut line, the higher-ranked team gets the last at-large spot. A title game loss can still leave a bubble team out.',ids:['mia25','byu25']}
};
function cmSrc(){return AP&&AP.cfp_published&&AP.cfp&&AP.cfp.ranks&&AP.cfp.ranks.length?{cfp:true,lab:'Official CFP rankings, '+AP.cfp.date}:{cfp:false,lab:'AP Top 25 (used until the official CFP rankings come out)'}}
function cmPrec(id){return CMN?CMN.precedents.filter(function(x){return x.id===id})[0]:null}
/* rule 1: title game losers keep their place ahead of at-large teams they led in the base order */
function cmRules(o,S){
  S.cmw=[];if(!S.tl||!S.tl.length)return o;
  var B=baseOrder('cm'),bi={};B.forEach(function(t,i){bi[t.n]=i});
  var ch={};for(var c in S.champ)ch[S.champ[c]]=1;(S.tw||[]).forEach(function(n){ch[n]=1});
  S.tl.forEach(function(n){
    var L=o.filter(function(t){return t.n===n})[0];if(!L||bi[n]==null)return;var li=o.indexOf(L);
    var pass=o.slice(0,li).filter(function(x){return bi[x.n]>bi[n]&&!ch[x.n]&&S.tl.indexOf(x.n)<0});
    if(!pass.length)return;var j=o.indexOf(pass[0]);o.splice(li,1);o.splice(j,0,L);
    S.cmw.push({n:n,rule:'titleloss',txt:L.s+' lost its title game but stays ahead of '+pass.map(function(x){return x.s}).slice(0,3).join(', ')+(pass.length>3?' and '+(pass.length-3)+' more':'')+', at-large team'+(pass.length>1?'s':'')+' it was ranked ahead of. Up '+(li-j)+' spot'+(li-j===1?'':'s')+' from the formula order.'});
  });
  return o;
}
/* notes for a built committee field: rules 2 to 4 */
function cmNotes(P){
  var S=SV.cm,N=(S.cmw||[]).slice(),A=P.auto,F=P.field,at=F.filter(function(x){return !A[x.n]});
  F.filter(function(x){return A[x.n]&&x.r>12}).forEach(function(x){N.push({n:x.n,rule:'autobid',txt:x.s+' is No. '+x.r+' but gets in as '+A[x.n]+', one of the five highest-ranked champions. Seeded No. '+x.seed+'.'})});
  F.filter(function(x){return x.seed<=4&&!A[x.n]}).forEach(function(x){N.push({n:x.n,rule:'seed',txt:x.s+' is No. '+x.r+' without a conference title and still gets a top-four seed and a bye.'})});
  var last=at[at.length-1],fo=P.out[0];
  if(last&&fo)N.push({n:fo.n,rule:'bubble',txt:'Cut line: '+last.s+' (No. '+last.r+') gets the last at-large spot over '+fo.s+' (No. '+fo.r+').'+((S.tl||[]).indexOf(fo.n)>=0?' '+fo.s+' lost its title game and sits just outside, like BYU in 2025.':'')});
  return N;
}
function cmLink(id){var p=cmPrec(id);if(!p)return'';return'<li>'+esc(p.text)+' <a class="txt" href="'+esc(p.url)+'" target="_blank" rel="noopener">Final CFP rankings, '+p.season+'</a></li>'}
function cmHtml(P){
  if(!CMN)return'';var N=cmNotes(P),src=cmSrc(),h='<section class="cmr" aria-labelledby="cmr-h"><h3 id="cmr-h">Committee patterns we apply</h3><p class="meta">Base order: '+esc(src.lab)+'. Every rule comes from the 2024 and 2025 final CFP rankings.</p><ol class="cmr-l">';
  ['titleloss','autobid','seed','bubble'].forEach(function(k){h+='<li><b>'+esc(CMR[k].t)+'.</b> '+esc(CMR[k].p)+'</li>'});
  h+='</ol>';
  if(N.length){h+='<p class="res-k">Where a rule moved or placed a team</p><ul class="cmr-w">'+N.map(function(x){return'<li data-rule="'+x.rule+'"><b>'+esc(CMR[x.rule].t)+':</b> '+esc(x.txt)+'<ul class="cmr-p">'+CMR[x.rule].ids.map(cmLink).join('')+'</ul></li>'}).join('')+'</ul>'}
  return h+'</section>';
}
/* ---------- next106 extras: precedents, why in/out, Resume, flips, ranking differences, share image ---------- */
function tid(t){return (t.src||t).id}
function prec(P){
  if(!CMN)return'';var S=SV.cm,tag='bubble',inF={};P.field.forEach(function(x){inF[x.n]=1});
  if(S.ops.some(function(o){return o.d>0&&inF[o.t.n]}))tag='titleloss';
  else if(P.field.some(function(x){return x.r>12}))tag='g6';
  else if(S.ops.some(function(o){return o.t.c==='big12'})||S.champ.big12)tag='big12';
  else if(Object.keys(S.champ).length)tag='champ';
  var p=CMN.precedents.filter(function(x){return x.tags.indexOf(tag)>=0})[0]||CMN.precedents[0];
  return'<p class="res-pc"><b>Past committee decision:</b> '+esc(p.text)+' <a href="'+esc(p.url)+'" target="_blank" rel="noopener">Final CFP rankings, '+p.season+'</a></p>';
}
function rsum(t){var r=RS[tid(t)];if(!r)return'';var a=[];a.push(r.w25.length+' Top 25 win'+(r.w25.length===1?'':'s'));if(r.bad.length)a.push(r.bad.length+' loss'+(r.bad.length===1?'':'es')+' outside the MSM top 50');if(r.sosr)a.push('schedule strength '+ord(r.sosr));return a.join(', ')}
function whyHtml(P,full){
  if(!full)return'';var F=P.field,A=P.auto,at=F.filter(function(x){return !A[x.n]}),h=[];
  var last=at[at.length-1],prev=at[at.length-2];
  [prev,last].forEach(function(x){if(x)h.push('<li><b>Why in: '+esc(x.s)+'.</b> '+esc('No. '+x.r+' in this order, one of the seven highest-ranked teams after the five conference champions. '+rsum(x)+'.')+'</li>')});
  F.filter(function(x){return A[x.n]&&x.r>12}).forEach(function(x){h.push('<li><b>Why in: '+esc(x.s)+'.</b> '+esc(A[x.n]+', one of the five highest-ranked conference champions, so it gets a bid at No. '+x.r+'.')+'</li>')});
  P.out.slice(0,2).forEach(function(x){h.push('<li><b>Why out: '+esc(x.s)+'.</b> '+esc('No. '+x.r+' in this order, '+(x.r-(last?last.r:12))+' spot'+(x.r-(last?last.r:12)===1?'':'s')+' behind '+(last?last.s:'the last team in')+' and not one of the five highest-ranked conference champions. '+rsum(x)+'.')+'</li>')});
  return'<h2>Bubble: why in, why out</h2><p class="meta">'+esc(anyAct()?VN[VW]+'.':'Written by our code from this week\'s order and our schedule data.')+'</p><ul class="why">'+h.join('')+'</ul>';
}
function games(){
  var seen={},g=[],lim=new Date(Date.now()+7*864e5).toISOString().slice(0,10);T.slice(0,40).forEach(function(t){var r=RS[t.id];if(!r||!r.next.length||r.next[0].d>lim)return;var n=r.next[0],o=T.filter(function(x){return x.id===n.o})[0];if(!o)return;var k=[t.id,o.id].sort().join('-');if(seen[k])return;seen[k]=1;g.push({k:k,a:n.h?o:t,b:n.h?t:o,d:n.d})});
  return g.sort(function(a,b){return a.d<b.d?-1:1}).slice(0,8);
}
function flipHtml(){
  var G=games();if(!G.length)return'<p class="meta">No games with top-40 teams this week.</p>';
  return'<div class="flp"><h3 id="flp-h">Flip a result</h3><p class="meta">This week\'s games with top-40 teams. Tap who wins. Tap again to clear.</p><div class="flg">'+G.map(function(g){
    var lab=g.a.s+' at '+g.b.s+', '+new Date(g.d+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'});
    return'<div class="fgm" role="group" aria-label="'+esc(lab)+'"><p>'+esc(lab)+'</p>'+[g.a,g.b].map(function(x){var on=FLIP[g.k]===x.id;return'<button type="button" class="flb" data-k="'+g.k+'" data-w="'+esc(x.id)+'" aria-pressed="'+on+'">'+esc(x.s)+' wins</button>'}).join('')+'</div>'}).join('')+'</div></div>';
}
/* Pick tab: champion picks and flips only. Builds one scenario and runs the Resume formula. */
function applyPicks(){
  reset();Q='';var G=games(),sc=newSc();
  Object.keys(PCH).forEach(function(c){var t=byN(PCH[c]);if(!t)return;sc.champ[c]=t.n;sc.games.push({w:t,l:null,title:true,ref:nextBest(t,c)});sc.lines.push(t.s+' wins the '+CN[c]+' (wins the title game)')});
  G.forEach(function(g){var w=FLIP[g.k];if(!w)return;var W1=w===g.a.id?g.a:g.b,L=W1===g.a?g.b:g.a;sc.games.push({w:W1,l:L});sc.lines.push(W1.s+' beats '+L.s)});
  if(sc.lines.length){applyF(sc);MODE='pick'}else MODE=null;
}
var RSEL='BYU Cougars';
function resumeHtml(){
  if(!RS||!Object.keys(RS).length)return'';var t=byN(RSEL)||T[0],r=RS[t.id]||{w25:[],bad:[]};
  var opts=T.slice().sort(function(a,b){return a.s<b.s?-1:1}).map(function(x){return'<option value="'+esc(x.n)+'"'+(x.n===t.n?' selected':'')+'>'+esc(x.s)+'</option>'}).join('');
  return'<section class="rsm" aria-labelledby="rsm-h"><h2 id="rsm-h">Resume</h2><label for="rsm-s" class="meta">Pick a team</label><select id="rsm-s">'+opts+'</select>'+
  '<div class="rsc'+(UT[t.n]?' '+UC(t.n):'')+'"><h3>'+esc(t.s)+' <small>'+esc(CN[t.c])+'</small></h3><dl>'+
  '<div><dt>Record</dt><dd>'+esc(t.rec)+'</dd></div><div><dt>The MSM Rankings</dt><dd>No. '+t.r+'</dd></div><div><dt>AP Top 25</dt><dd>'+esc(APR[t.id]?'No. '+APR[t.id]:'Unranked (AP)')+'</dd></div>'+
  '<div><dt>Top 25 wins</dt><dd>'+(r.w25.length?r.w25.length+': '+r.w25.map(esc).join(', '):'None')+'</dd></div>'+
  '<div><dt>Losses outside the MSM top 50</dt><dd>'+(r.bad.length?r.bad.map(esc).join(', '):'None')+'</dd></div>'+
  '<div><dt>Schedule strength</dt><dd>'+(r.sosr?ord(r.sosr)+' of '+T.length:'Not enough games')+'</dd></div></dl>'+
  '<p class="rsn">From our data: record from The MSM Rankings, '+esc(D.edition)+'. Top 25 means this week\'s MSM Top 25. Schedule strength is the average MSM rank of opponents played, 1st is toughest.</p></div></section>';
}
function biasHtml(P){
  if(!AP)return'';var cm=order('cm'),cr={};cm.forEach(function(x){cr[x.n]=x.r});
  var pick=T.filter(function(t){return UT[t.n]});T.slice(0,25).forEach(function(t){if(pick.length<10&&pick.indexOf(t)<0&&Math.abs(t.r-(APR[t.id]||26))>=4)pick.push(t)});
  var line=function(t){var a=APR[t.id];if(!a)return t.r<=25?'MSM ranks '+t.s+' No. '+t.r+'; AP does not rank them.':'Neither top 25 includes '+t.s+'.';var d=a-t.r;return d===0?'MSM and AP agree.':'MSM has '+t.s+' '+Math.abs(d)+' spot'+(Math.abs(d)===1?'':'s')+(d>0?' higher':' lower')+' than AP.'};
  var h='<section class="bias" aria-labelledby="bias-h"><h2 id="bias-h">Where the rankings differ</h2><p class="meta">The MSM Rankings, '+esc(apHead())+', and the committee view'+(anyAct()?' with your what-if':'')+'. The committee view starts from the AP Top 25 until the first official CFP rankings.</p><div class="tw"><table><thead><tr><th>Team</th><th>MSM</th><th>AP</th><th>Committee view</th></tr></thead><tbody>';
  pick.forEach(function(t){h+='<tr'+(UT[t.n]?' class="'+UC(t.n)+'"':'')+'><td>'+esc(t.s)+'<small class="bl">'+esc(line(t))+'</small></td><td>'+t.r+'</td><td>'+esc(APR[t.id]?String(APR[t.id]):'Unranked (AP)')+'</td><td>'+cr[t.n]+'</td></tr>'});
  h+='</tbody></table></div><h3>Teams in each top 25, by conference</h3><div class="tw"><table><thead><tr><th>Conference</th><th>MSM</th><th>AP</th><th>Committee view</th></tr></thead><tbody>';
  P4.concat(G6).concat(['ind']).forEach(function(c){var m=T.filter(function(t){return t.c===c&&t.r<=25}).length,a=T.filter(function(t){return t.c===c&&APR[t.id]}).length,k=cm.filter(function(t){return t.c===c&&t.r<=25}).length;if(m||a||k)h+='<tr><td>'+CN[c]+'</td><td>'+m+'</td><td>'+a+'</td><td>'+k+'</td></tr>'});
  return h+'</tbody></table></div></section>';
}
var LOGO=null;
function share(){ /* 1200x630 bracket image: navy field, white panels, current MSM lockup */
  var P=build(),F=P.field,cv=document.createElement('canvas'),W=1200,H=630;cv.width=W;cv.height=H;var x=cv.getContext('2d');
  var NV='#000E28',CR='#FBF3E4',GR='#5B6475',TN='#d9ccb2';
  x.fillStyle=NV;x.fillRect(0,0,W,H);x.textBaseline='middle';
  var lh=44;if(LOGO&&LOGO.naturalWidth){var lw=lh*LOGO.naturalWidth/LOGO.naturalHeight;x.drawImage(LOGO,40,28,lw,lh)}
  x.font='600 22px Oswald, "Arial Narrow", sans-serif';x.fillStyle='#F5B82E';x.textAlign='right';x.fillText((anyAct()?VN[VW]:'This week\'s bracket').toUpperCase(),W-40,50);x.textAlign='left';
  x.fillStyle=CR;x.fillRect(40,92,W-80,36);x.fillStyle=NV;x.font='600 18px Inter, Arial, sans-serif';x.fillText(LABEL,56,110);
  var cols=[['First round',40],['Quarterfinals',330],['Semifinals',620],['Final',910]],cw=250,rh=32;
  x.font='600 15px Oswald, "Arial Narrow", sans-serif';cols.forEach(function(c){x.fillStyle=CR;x.fillText(c[0].toUpperCase(),c[1],156)});
  var row=function(cx,cy,t,lab){x.fillStyle='#fff';x.fillRect(cx,cy,cw,rh);
    if(t){x.fillStyle=NV;x.fillRect(cx,cy,30,rh);x.fillStyle='#fff';x.font='700 15px Inter, Arial, sans-serif';x.textAlign='center';x.fillText(String(t.seed),cx+15,cy+rh/2);x.textAlign='left';x.fillStyle=NV;x.font='600 17px Inter, Arial, sans-serif';x.fillText(t.s,cx+40,cy+rh/2)}
    else{x.fillStyle=GR;x.font='italic 400 15px Inter, Arial, sans-serif';x.fillText(lab,cx+12,cy+rh/2)}};
  var game=function(cx,cy,a,b,la,lb){row(cx,cy,a,la);x.fillStyle=TN;x.fillRect(cx,cy+rh,cw,1);row(cx,cy+rh+1,b,lb)};
  var S=function(n){return F[n-1]},fo=[[8,9],[5,12],[7,10],[6,11]],qs=[1,4,2,3],y0=176,gh=2*rh+1,gap=(H-50-y0-4*gh)/3;
  fo.forEach(function(g,i){var cy=y0+i*(gh+gap);game(40,cy,S(g[0]),S(g[1]));game(330,cy,S(qs[i]),null,'','Winner '+g[0]+'/'+g[1])});
  [0,1].forEach(function(k){var cy=y0+(2*k+0.5)*(gh+gap);var SD={1:'1 / 8 / 9',4:'4 / 5 / 12',2:'2 / 7 / 10',3:'3 / 6 / 11'};game(620,cy,null,null,'No. '+SD[qs[2*k]]+' side','No. '+SD[qs[2*k+1]]+' side')});
  game(910,y0+1.5*(gh+gap),null,null,'Semifinal winner','Semifinal winner');
  x.fillStyle=TN;x.font='400 15px Inter, Arial, sans-serif';x.fillText('mtnsportsmedia.com/playoff',40,H-24);
  return cv;
}
function shareUI(){
  var w=root.querySelector('.shw');if(!w)return;var cv=share(),url=cv.toDataURL('image/png');
  w.innerHTML='<img class="shi" alt="Share image: the 12-team bracket for this view, labeled Hypothetical" src="'+url+'"><div class="shb"><a class="shd" href="'+url+'" download="msm-playoff-bracket.png">Download image</a>'+(navigator.canShare?'<button type="button" class="shs">Share</button>':'')+'</div>';
  var s=w.querySelector('.shs');if(s)s.addEventListener('click',function(){cv.toBlob(function(b){var f=new File([b],'msm-playoff-what-if.png',{type:'image/png'});var d={files:[f],text:LABEL+' mtnsportsmedia.com/playoff'};if(navigator.canShare(d))navigator.share(d).catch(function(){});})});
}
/* ---------- rendering ---------- */
function lg(t,z){z=z||28;return'<span class="lgw" data-i="'+esc(ini(t.s))+'">'+(t.id?'<img src="/rankings/logos/'+esc(t.id)+'.png" width="'+z+'" height="'+z+'" alt="'+esc(t.s)+' logo" decoding="async" onerror="this.remove()">':'')+'</span>'}
function ini(s){var w=String(s).split(/\s+/);return (w.length>1?w.map(function(x){return x[0]}).join(''):s.slice(0,3)).slice(0,3).toUpperCase()}
function rlab(t,v){var o=t.src||t;if((v||VW)==='msm')return'MSM #'+o.r;return APR[o.id]?'AP #'+APR[o.id]:'Unranked (AP)'}
function row(t,auto,lab){
  if(!t)return'<div class="tm tbd"><span class="sd"></span><span class="lgw"></span><span class="nm">'+esc(lab)+'</span><span class="rk"></span></div>';
  return'<div class="tm'+(UT[t.n]?' '+UC(t.n):'')+'"><span class="sd">'+t.seed+'</span>'+lg(t)+'<span class="nm">'+esc(t.s)+'<small>'+esc(auto[t.n]||'At-large')+' · '+esc(t.rec)+'</small></span><span class="rk">'+esc(rlab(t))+'</span></div>';
}
function frow(t,lab){if(!t)return'<div class="ft tbd"><span class="fs"></span><span class="fn">'+esc(lab)+'</span></div>';return'<div class="ft'+(UT[t.n]?' '+UC(t.n):'')+'"><span class="fs">'+t.seed+'</span>'+lg(t,18)+'<span class="fn">'+esc(t.s)+'</span></div>'}
function act(v){var S=SV[v||VW];return S.ops.length||Object.keys(S.champ).length||Object.keys(S.notc).length}
function anyAct(){return act('msm')||act('ap')||act('cm')}
var EX=C.PRESETS;
function apHead(){return AP?'AP Top 25, week '+AP.week+' (poll dated '+new Date(AP.date+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})+')':'AP Top 25'}
function viewNote(v){
  if(v==='msm')return'Starts from The MSM Rankings, '+D.edition+'.';
  if(v==='ap')return apHead()+'. Source: AP Top 25 via ESPN.';
  return'Based on how the committee handled the 2024 and 2025 seasons under the 12-team format. It is not what the committee will do. '+(cmSrc().cfp?'Starts from the '+cmSrc().lab+'. Source: collegefootballplayoff.com.':'Starts from the '+apHead()+' until the first official CFP rankings. Source: AP Top 25 via ESPN.');
}
function render(){
  var OPEN={};[].forEach.call(root.querySelectorAll('details.dx[open]'),function(d){OPEN[d.id]=1});
  var P=build(),F=P.field,A=P.auto,S=function(n){return F[n-1]},on=act(),any=anyAct();
  var fr=[[5,12],[6,11],[7,10],[8,9]],qf=[[1,'8/9',8,9],[4,'5/12',5,12],[2,'7/10',7,10],[3,'6/11',6,11]];
  var h='',dx=function(id,t,body){return body?'<details class="dx" id="'+id+'"'+(OPEN[id]?' open':'')+'><summary>'+esc(t)+'</summary><div class="dxb">'+body+'</div></details>':''};
  var rline='<p class="res-ai">'+(MODE==='ai'?esc(C.RULES_AI)+' The AI only reads your scenario. Teams move by our Resume formula.':MODE==='pick'?'Your picks. Teams move by our Resume formula. Check the official CFP rankings.':MODE==='rules'?'The AI helper is busy right now, so our code read your scenario. Teams move by the same Resume formula. Check the official CFP rankings.':'')+'</p>';
  /* 1) compact selector: input tabs + view tabs, one tight block */
  h+='<section class="wl sel" aria-label="What-if controls"><div class="selrow">';
  h+='<div class="itabs" role="tablist" aria-label="How to build your what-if">'+[['type','Type'],['pick','Pick']].map(function(x){return'<button type="button" role="tab" id="it-'+x[0]+'" data-i="'+x[0]+'" aria-controls="ip-'+x[0]+'" aria-selected="'+(ITAB===x[0])+'" tabindex="'+(ITAB===x[0]?0:-1)+'">'+x[1]+'</button>'}).join('')+'</div>';
  h+='<div class="vtabs" role="tablist" aria-label="Which view">'+['msm','ap','cm'].map(function(v){return'<button type="button" role="tab" id="vt-'+v+'" data-w="'+v+'" aria-controls="vp" aria-selected="'+(VW===v)+'" tabindex="'+(VW===v?0:-1)+'">'+esc(VN[v])+'</button>'}).join('')+'</div>';
  h+='</div><p class="sel-hy">'+esc(C.LABEL)+'</p>';
  if(ITAB==='pick'){
    h+='<div class="ipan" id="ip-pick" role="tabpanel" aria-labelledby="it-pick">';
    [['big12','Big 12 champion'],['pac12','Pac-12 champion']].forEach(function(cc){var cf=cc[0],L=T.filter(function(x){return x.c===cf}).slice(0,4);if(!L.length)return;
      h+='<div class="wl-b12"><span class="wl-q" id="wl-'+cf+'q">'+cc[1]+'</span><div class="chips" role="group" aria-labelledby="wl-'+cf+'q">'+L.map(function(t,i){return'<button type="button" class="chip" data-c="'+cf+'" data-n="'+esc(t.n)+'" aria-pressed="'+(PCH[cf]===t.n)+'">'+lg(t,24)+'<span>'+esc(t.s)+(i===0?' <small>top now</small>':'')+'</span></button>'}).join('')+'</div></div>'});
    h+=dx('d-flip','Flip a game',flipHtml())+'</div>';
  }else{
    h+='<div class="ipan" id="ip-type" role="tabpanel" aria-labelledby="it-type">';
    h+='<form class="ask" novalidate><label for="wl-in">Type a scenario <small class="ai">Built with AI</small></label><div class="ask-r"><input id="wl-in" type="text" autocomplete="off" enterkeyhint="go" maxlength="200" placeholder="BYU loses to Utah and wins the Big 12" value="'+esc(Q)+'"><button type="submit" class="runb'+(BUSY?' busy':'')+'"'+(BUSY?' disabled aria-busy="true"':'')+'>'+(BUSY?'<svg class="mtn" viewBox="0 0 120 80" width="34" height="22.67" aria-hidden="true" focusable="false"><g class="fl"><path d="M62 5L50 28L44 38L51 42L45 58L55 77L64 44L58 25Z" fill="#5B6475"/><path d="M28 42L3 77L15 77L26 57L32 47Z" fill="#5B6475"/><path d="M94 29L86 40L92 47L89 62L99 56L97 40Z" fill="#5B6475"/><path d="M62 5L54 20L58 21L56 26L61 22L65 27L68 19L71 21Z" fill="#FBF3E4"/><path d="M94 29L89 36L93 37L95 34L99 37Z" fill="#FBF3E4"/></g><path class="tr" pathLength="100" d="M3 77L28 42L36 51L50 28L62 5L74 25L84 39L94 29L117 62L117 77Z"/><path class="tr fc" pathLength="100" d="M62 5L58 25L64 44L55 77M94 29L97 40L99 56M28 42L32 47L26 57"/></svg><span class="vh">Running</span>':'Run it')+'</button></div><p class="runst vh" role="status" aria-live="polite">'+(BUSY?'Running your what-if':'')+'</p></form>';
    h+=dx('d-ex','Examples','<div class="ex" role="group" aria-label="One-tap scenarios">'+EX.map(function(e){return'<button type="button" class="exb">'+esc(e)+'</button>'}).join('')+'</div>')+'</div>';
  }
  h+='<div class="res" aria-live="polite">';
  if(MSG)h+='<p class="res-m">'+esc(MSG)+'</p>';
  else if(any){var SVv=SV[VW],F0=F;
    var B=BASE[VW],bi={};B.forEach(function(x){bi[x.n]=x.seed});var ni={};F.forEach(function(x){ni[x.n]=1});
    var inn=F.filter(function(x){return !bi[x.n]}),gone=B.filter(function(x){return !ni[x.n]});
    h+='<p class="res-io">'+(inn.length?'In: '+inn.map(function(x){return esc(x.s)}).join(', ')+'. ':'')+(gone.length?'Out: '+gone.map(function(x){return esc(x.s)}).join(', ')+'.':'')+(!inn.length&&!gone.length?'Same 12 teams, new seeds.':'')+'</p>';
    h+='<button type="button" class="reset">Start over</button>';
  }
  h+='</div></section>';
  /* 2) bracket right after the selector */
  var RT=[['First round','Round 1'],['Quarterfinals','Quarters'],['Semifinals','Semis'],['National Championship','Final']];
  h+='<section class="brk" aria-labelledby="po-br"><h2 id="po-br" tabindex="-1">'+(any?'Your what-if bracket':'This week\'s bracket')+' <small>'+esc(VN[VW])+'</small></h2>';
  h+='<div class="vt" role="group" aria-label="Bracket view"><button type="button" data-v="full" aria-pressed="'+(VIEW==='full')+'">Full bracket</button><button type="button" data-v="rd" aria-pressed="'+(VIEW==='rd')+'">By round</button></div>';
  var fo=[[8,9],[5,12],[7,10],[6,11]];
  h+='<div class="fbx'+(VIEW==='full'?' on':'')+(ZOOM?'':' fitd')+'"><p class="fcue" aria-hidden="true">Scroll sideways for every round &rarr;</p><div class="fbw'+(ZOOM?' zm':'')+'" tabindex="0" aria-label="Full bracket, scrolls sideways"><div class="fb" role="img" aria-label="Full 12-team bracket"><div class="fc"><h4>First round</h4>'+fo.map(function(g){return'<div class="fg">'+frow(S(g[0]))+frow(S(g[1]))+'</div>'}).join('')+'</div><div class="fc"><h4>Quarters</h4>'+qf.map(function(g){return'<div class="fg">'+frow(S(g[0]))+frow(null,'W '+g[1])+'</div>'}).join('')+'</div><div class="fc"><h4>Semis</h4><div class="fg">'+frow(null,'1/8/9 side')+frow(null,'4/5/12 side')+'</div><div class="fg">'+frow(null,'2/7/10 side')+frow(null,'3/6/11 side')+'</div></div><div class="fc"><h4>Final</h4><div class="fg">'+frow(null,'Semi A winner')+frow(null,'Semi B winner')+'</div></div></div></div><button type="button" class="zb" aria-pressed="'+ZOOM+'">'+(ZOOM?'Fit to screen':'Zoom in')+'</button></div>';
  h+='<div class="rdx'+(VIEW==='rd'?' on':'')+'"><div class="rtabs" role="tablist" aria-label="CFP round">'+RT.map(function(r,i){return'<button type="button" role="tab" id="rt-'+i+'" data-c="rd-'+i+'" aria-controls="rd-'+i+'" aria-selected="'+(i===RD)+'" tabindex="'+(i===RD?0:-1)+'">'+r[1]+'</button>'}).join('')+'</div>';
  h+='<div class="br"><div class="col'+(RD===0?' act':'')+'" id="rd-0" role="tabpanel" aria-labelledby="rt-0"><h3>First round</h3>';
  fr.forEach(function(g){h+='<div class="gm"><div class="lab">No. '+g[0]+' hosts No. '+g[1]+'</div>'+row(S(g[0]),A)+row(S(g[1]),A)+'</div>'});
  h+='</div><div class="col'+(RD===1?' act':'')+'" id="rd-1" role="tabpanel" aria-labelledby="rt-1"><h3>Quarterfinals</h3>';
  qf.forEach(function(g){h+='<div class="gm"><div class="lab">No. '+g[0]+' vs '+g[1]+' winner</div>'+row(S(g[0]),A)+row(null,A,'Winner of '+S(g[2]).s+' / '+S(g[3]).s)+'</div>'});
  h+='</div><div class="col sf'+(RD===2?' act':'')+'" id="rd-2" role="tabpanel" aria-labelledby="rt-2"><h3>Semifinals</h3><div class="gm"><div class="lab">Semifinal A</div>'+row(null,A,'No. 1 / 8 / 9 side')+row(null,A,'No. 4 / 5 / 12 side')+'</div><div class="gm"><div class="lab">Semifinal B</div>'+row(null,A,'No. 2 / 7 / 10 side')+row(null,A,'No. 3 / 6 / 11 side')+'</div></div><div class="col fn'+(RD===3?' act':'')+'" id="rd-3" role="tabpanel" aria-labelledby="rt-3"><h3>National Championship</h3><div class="gm"><div class="lab">Title game</div>'+row(null,A,'Semifinal A winner')+row(null,A,'Semifinal B winner')+'</div></div></div></div>';
  h+='<button type="button" class="shr">Share this bracket</button><div class="shw" aria-live="polite"></div></section>';
  /* 3) Utah teams, tight */
  h+='<div class="ut" aria-label="Utah teams">';
  ['BYU Cougars','Utah Utes','Utah State Aggies'].forEach(function(n){
    var t=P.W.filter(function(x){return x.n===n})[0];if(!t)return;var st,sub;
    if(t.seed){st='No. '+t.seed+' seed';sub=t.seed<=4?'First-round bye, straight to the quarterfinals':'Hosts No. '+(17-t.seed)+' '+S(17-t.seed).s+' in the first round';if(t.seed>8)sub='Plays at No. '+(17-t.seed)+' '+S(17-t.seed).s+' in the first round'}
    else{var k=P.out.indexOf(t)+1;st=k===1?'First team out':k<=8?ord(k)+' team out':'Outside the field';sub=k<=8?'Just outside the 12-team field':'Needs to climb into the top group'}
    var ss=t.seed?('No. '+t.seed+' seed · '+(t.seed<=4?'bye':t.seed<=8?'hosts No. '+(17-t.seed):'at No. '+(17-t.seed))):st;
    h+='<a href="'+UT[n]+'"'+(t.seed?' class="in"':'')+'><b>'+esc(t.s)+'</b><span class="st">'+st+'</span><span class="ss">'+ss+'</span><span class="mr">'+esc(rlab(t))+' · '+esc(t.rec)+'</span><span class="sub">'+esc(rlab(t))+' · '+esc(t.rec)+' · '+CN[t.c]+'</span><span class="sub">'+sub+'</span></a>';
  });
  h+='</div>';
  /* 4) everything that explains us: collapsed at the bottom */
  var c='';if(any&&!MSG){var SVv=SV[VW];c='';
    if(SVv.lines.length)c+='<p class="res-k">How we read it</p><ul class="res-l">'+SVv.lines.map(function(l){return'<li>'+esc(l)+'</li>'}).join('')+'</ul>';
    if(SVv.why&&SVv.why.length)c+='<p class="res-k">Why each team moved</p><ul class="res-w">'+SVv.why.map(function(w){var o=byN(w.t.n);return'<li'+(UT[w.t.n]?' class="'+UC(w.t.n)+'"':'')+'><b>'+esc(w.t.s)+': '+(w.d<0?'up '+(-w.d):w.d>0?'down '+w.d:'no change')+(Math.abs(w.d)===1?' spot':w.d?' spots':'')+'</b> <span class="rw-t">(Resume '+esc(sg(w.pts))+')</span> '+esc(w.txt)+'</li>'}).join('')+'</ul>';
    if(SVv.miss.length)c+='<p class="res-x">Skipped: '+SVv.miss.map(esc).join('; ')+'</p>';
    var B=BASE[VW],bi={};B.forEach(function(x){bi[x.n]=x.seed});var ni={};F.forEach(function(x){ni[x.n]=1});
    var inn=F.filter(function(x){return !bi[x.n]}),gone=B.filter(function(x){return !ni[x.n]});
    c+='<p class="res-k">The field</p><ol class="res-f">'+F.map(function(t){var b=bi[t.n],ch=!b?'<em>new</em>':b!==t.seed?'<em>was '+b+'</em>':'';return'<li'+(UT[t.n]?' class="'+UC(t.n)+'"':'')+'><span class="fs">'+t.seed+'</span>'+lg(t,20)+'<span class="fn">'+esc(t.s)+'<small>'+esc(rlab(t))+'</small></span>'+ch+'</li>'}).join('')+'</ol>';
    c+=(EXPL?'<p class="res-ex">'+esc(EXPL)+'</p>':'');c+='<p class="res-k">The field</p><ol class="res-f">'+F.map(function(t){var b=bi[t.n],ch=!b?'<em>new</em>':b!==t.seed?'<em>was '+b+'</em>':'';return'<li'+(UT[t.n]?' class="'+UC(t.n)+'"':'')+'><span class="fs">'+t.seed+'</span>'+lg(t,20)+'<span class="fn">'+esc(t.s)+'<small>'+esc(rlab(t))+'</small></span>'+ch+'</li>'}).join('')+'</ol>';}
  var t0=h;h='';
  h+='<div class="tw"><table><thead><tr><th>Seed</th><th>Team</th><th>'+(VW==='msm'?'MSM':'AP')+'</th><th class="hide-s">Conference</th><th>Bid</th></tr></thead><tbody>';
  F.forEach(function(t){h+='<tr'+(UT[t.n]?' class="'+UC(t.n)+'"':'')+'><td>'+t.seed+'</td><td><span class="tc">'+lg(t)+esc(t.s)+'</span></td><td>'+esc(rlab(t).replace('MSM ','').replace('AP ',''))+'</td><td class="hide-s">'+CN[t.c]+'</td><td>'+esc(A[t.n]||'At-large')+'</td></tr>'});
  h+='</tbody></table></div><p class="res-k">First four out</p><ul class="out">';
  P.out.slice(0,4).forEach(function(t){h+='<li'+(UT[t.n]?' class="'+UC(t.n)+'"':'')+'>'+esc(t.s)+' ('+esc(rlab(t))+')</li>'});
  P.out.slice(0,4).forEach(function(t){h+='<li'+(UT[t.n]?' class="'+UC(t.n)+'"':'')+'>'+esc(t.s)+' ('+esc(rlab(t))+')</li>'});
  var tbH=h+'</ul>';h=t0;
  h+='<div class="dxs">';
  h+=dx('d-chg','What changed',c);
  h+=dx('d-fld','Full field and first four out',tbH);
  h+=dx('d-how','How teams move',howHtml());
  h+=dx('d-cm','Committee rules and past decisions',cmHtml(build('cm')));
  h+=dx('d-why','Bubble: why in, why out',whyHtml(P,1));
  h+=dx('d-rsm','Resume cards',resumeHtml());
  h+=dx('d-bias','Bias check',biasHtml(P));
  h+=dx('d-src','Sources and notes',(any?rline:'')+'<p class="res-vn">'+esc(viewNote(VW))+'</p>'+'<p class="wl-n">How this works: an AI helper (Cloudflare Workers AI) reads your scenario into game results. Our code moves teams with the Resume formula above and builds the field with the CFP rules. The scenario text you type is sent to Cloudflare Workers AI for processing, and MSM does not store it. Leave out personal details. Team ranks and records shown here come from our data, not the AI. These are what-ifs, not picks.</p>');
  h+='</div>';
  root.innerHTML=h;wire();fit();
}
function fit(){
  var w=root.querySelector('.fbw'),b=root.querySelector('.fb');if(!w||!b)return;
  b.style.transform='';b.style.marginRight='';b.style.marginBottom='';if(!w.clientWidth)return;
  var bw=b.offsetWidth,bh=b.offsetHeight,s=ZOOM?1:Math.min(1,(w.clientWidth-2)/bw);
  s=Math.round(s*1000)/1000;b.dataset.s=s;if(s===1)return;
  b.style.transform='scale('+s+')';b.style.marginRight=(bw*s-bw)+'px';b.style.marginBottom=(bh*s-bh)+'px';
}
var BYS=null;
function bys(){if(BYS)return BYS;BYS={};T.slice().sort(function(a,b){return a.r-b.r}).forEach(function(t){[t.s,t.n].forEach(function(k){k=k.toLowerCase();if(!BYS[k])BYS[k]=t})});return BYS}
function facts(t){return'MSM No. '+t.r+', '+(APR[t.id]?'AP No. '+APR[t.id]:'Unranked (AP)')+', '+t.rec}
function fromAI(o){ /* re-validate on the client too; never render AI text as HTML. The AI gives results only; the formula moves teams */
  var v=MSMG.validate(o,bys());if(!v)return false;var sc=newSc();
  v.games.forEach(function(g){var w=byN(g.w)||MSMG.FCSO[g.w.toLowerCase()],l=byN(g.l)||MSMG.FCSO[g.l.toLowerCase()];sc.games.push({w:w,l:l,title:g.title});sc.lines.push(w.s+' beats '+l.s+(g.title?' in the '+CN[w.c]+' title game':''));if(g.title&&!w.fcs&&!v.champs[w.c]&&P4.concat(G6).indexOf(w.c)>=0)v.champs[w.c]=w.n});
  v.solo.forEach(function(r){solo(sc,byN(r.n),r.res,r.k)});
  Object.keys(v.champs).forEach(function(c){var t=byN(v.champs[c]);if(sc.champ[c]===t.n)return;sc.champ[c]=t.n;
    if(!sc.games.some(function(g){return g.title&&g.w===t}))sc.games.push({w:t,l:null,title:true,ref:nextBest(t,c)});sc.lines.push(t.s+' wins the '+CN[c])});
  applyF(sc);EXPL=v.explain;MODE='ai';return true;
}
function rules(text){var sc=parse(text);if(!sc.lines.length)return sc;applyF(sc);MODE='rules';EXPL='';return sc}
var FMSG={empty:'Type a scenario first, like "Utah beats BYU".',long:'Keep it under 200 characters.',profanity:'Let\'s keep it friendly. Try a scenario like "Utah beats BYU".',banned:'We only do what-ifs here, not picks or betting talk. Try "Utah wins the Big 12".',offtopic:'That does not look like a college football what-if. Try "Texas wins the SEC".',nomatch:'We could not match that to a team or result. Try a team name plus what happens, like "Utah beats BYU" or "Texas wins the SEC". Or tap an example below.'};
function reset(){SV={msm:blank(),ap:blank(),cm:blank()};MODE=null;EXPL='';MSG=null}
function run(text,fromChip){
  Q=String(text).slice(0,200);var g=MSMG.screen(Q);reset();
  if(g){if(g!=='empty')MSG=FMSG[g];render();return}
  if(!aliasHit(Q)){MSG=FMSG.offtopic;render();return}
  BUSY=true;render();
  var done=false,ctl=window.AbortController?new AbortController():null,tm=setTimeout(function(){if(ctl)ctl.abort()},20000);
  fetch('/api/whatif',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({q:Q}),signal:ctl?ctl.signal:undefined})
  .then(function(r){return r.json().catch(function(){return{ok:false,code:'busy'}})},function(){return{ok:false,code:'busy'}})
  .then(function(j){clearTimeout(tm);BUSY=false;
    if(j&&j.ok&&fromAI(j.result)){}
    else if(j&&['profanity','banned','offtopic','long','empty'].indexOf(j.code)>=0){MSG=FMSG[j.code]}
    else if(j&&j.ok){MSG=FMSG.nomatch}
    else if(j&&j.code==='nomatch'){MSG=FMSG.nomatch}
    else{var sc=rules(Q);if(!sc.lines.length){reset();MSG=FMSG.nomatch}}
    render();var r=root.querySelector('.res');if(r&&r.scrollIntoView&&!fromChip)r.scrollIntoView({block:'nearest'});
  });
}
function aliasHit(q){var s=scan(norm(q));return s.teams.length||s.conf}
function wire(){
  var rt=root.querySelector('.rtabs');
  if(rt){var bs=[].slice.call(rt.querySelectorAll('button'));var go=function(x,f){RD=bs.indexOf(x);bs.forEach(function(y){var o=y===x;y.setAttribute('aria-selected',o);y.tabIndex=o?0:-1;document.getElementById(y.dataset.c).classList.toggle('act',o)});if(f)x.focus()};bs.forEach(function(x,i){x.addEventListener('click',function(){go(x)});x.addEventListener('keydown',function(e){var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;if(k){e.preventDefault();go(bs[(i+k+bs.length)%bs.length],1)}})})}
  var vt=root.querySelector('.vtabs');
  if(vt){var vs=[].slice.call(vt.querySelectorAll('button'));vs.forEach(function(x,i){x.addEventListener('click',function(){VW=x.getAttribute('data-w');render();var f=root.querySelector('#vt-'+VW);if(f)f.focus()});x.addEventListener('keydown',function(e){var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;if(k){e.preventDefault();VW=vs[(i+k+3)%3].getAttribute('data-w');render();root.querySelector('#vt-'+VW).focus()}})})}
  [].forEach.call(root.querySelectorAll('.lgw img'),function(i){function f(){i.parentNode.classList.add('nolg');i.remove()}if(i.complete&&!i.naturalWidth)f();else i.addEventListener('error',f)});
  [].forEach.call(root.querySelectorAll('.lgw[data-i]'),function(w){if(!w.querySelector('img'))w.classList.add('nolg')});
  [].forEach.call(root.querySelectorAll('.wl .chip'),function(b){b.addEventListener('click',function(){var n=b.getAttribute('data-n'),cf=b.getAttribute('data-c');PCH[cf]=PCH[cf]===n?undefined:n;if(!PCH[cf])delete PCH[cf];applyPicks();render();var f=root.querySelector('.wl .chip[data-n="'+n.replace(/"/g,'')+'"]');if(f)f.focus()})});
  var it=root.querySelector('.itabs');
  if(it){var ib=[].slice.call(it.querySelectorAll('button'));var sw=function(k,f){if(k===ITAB){if(f)root.querySelector('#it-'+k).focus();return}if(BUSY)return;ITAB=k;Q='';FLIP={};PCH={};reset();render();root.querySelector('#it-'+k).focus()};
    ib.forEach(function(x,i){x.addEventListener('click',function(){sw(x.getAttribute('data-i'))});x.addEventListener('keydown',function(e){var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;if(k){e.preventDefault();sw(ib[(i+k+2)%2].getAttribute('data-i'),1)}})})}
  var fm=root.querySelector('.ask');if(fm)fm.addEventListener('submit',function(e){e.preventDefault();if(!BUSY)run(root.querySelector('#wl-in').value)});
  var inp=root.querySelector('#wl-in');if(inp)inp.addEventListener('input',function(){var c=root.querySelector('.cnt');if(c)c.textContent=inp.value.length+'/200'});
  [].forEach.call(root.querySelectorAll('.exb'),function(b){b.addEventListener('click',function(){if(!BUSY)run(b.textContent,1)})});
  var rs=root.querySelector('.reset');if(rs)rs.addEventListener('click',function(){Q='';FLIP={};PCH={};reset();render();var i=root.querySelector('#wl-in');if(i)i.focus()});
  [].forEach.call(root.querySelectorAll('.vt button'),function(b){b.addEventListener('click',function(){VIEW=b.getAttribute('data-v');render();var f=root.querySelector('.vt button[data-v="'+VIEW+'"]');if(f)f.focus()})});
  var sh=root.querySelector('.shr');if(sh)sh.addEventListener('click',function(){if(!LOGO){LOGO=new Image();LOGO.onload=shareUI;LOGO.onerror=shareUI;LOGO.src='/brand/header-lockup-dark@2x.png'}else shareUI()});
  [].forEach.call(root.querySelectorAll('.flb'),function(b){b.addEventListener('click',function(){var k=b.getAttribute('data-k'),w=b.getAttribute('data-w');FLIP[k]=FLIP[k]===w?null:w;applyPicks();render();var f=root.querySelector('.flb[data-k="'+k+'"][data-w="'+w+'"]');if(f)f.focus()})});
  var rsel=root.querySelector('#rsm-s');if(rsel)rsel.addEventListener('change',function(){RSEL=rsel.value;render();var f=root.querySelector('#rsm-s');if(f)f.focus()});
  var zb=root.querySelector('.zb');if(zb)zb.addEventListener('click',function(){ZOOM=!ZOOM;render();var f=root.querySelector('.zb');if(f)f.focus()});
}
addEventListener('resize',fit);
function howHtml(){
  var cf='SEC 1.2, Big Ten 1.15, Independents 1.0, Big 12 0.95, ACC 0.85, other FBS conferences 0.6, FCS 0.3';
  var L=['Each result counts for both teams. A win starts at '+FM.WIN+' and a loss at minus '+FM.LOSS+'.',
  'Opponent strength: half conference strength ('+cf+') and half opponent rank in that tab, from '+FM.RANK_TOP+' for No. 1 down 3% per spot.',
  'Win: '+FM.WIN+' x ('+FM.WIN_ADD+' + opponent strength). Loss: minus '+FM.LOSS+' x ('+FM.LOSS_BASE+' - '+FM.LOSS_SLOPE+' x opponent strength). Beating strong teams earns more. Losing to weak teams costs more.',
  'Location: road win x'+FM.SITE.away[0]+', neutral x'+FM.SITE.neutral[0]+', home x'+FM.SITE.home[0]+'. Road loss x'+FM.SITE.away[1]+', neutral x'+FM.SITE.neutral[1]+', home x'+FM.SITE.home[1]+'.',
  'Quality win bonus: Top 5 +'+FM.Q[0][1]+', Top 10 +'+FM.Q[1][1]+', Top 25 +'+FM.Q[2][1]+'. The committee tab counts it x'+FM.CM_Q+'.',
  'Conference title game: win x'+FM.TITLE_W+', loss x'+FM.TITLE_L+'.',
  'Schedule strength: plus '+FM.SOS_W+' x (opponent strength minus the team\'s schedule average), divided by games played plus 1.',
  'Every '+FM.PER_SPOT+' of Resume moves a team one spot, up to '+FM.MAX+'. Margin of victory does not count.'];
  return'<section class="htm" aria-labelledby="htm-h"><h3 id="htm-h">How teams move</h3><ul>'+L.map(function(x){return'<li>'+esc(x)+'</li>'}).join('')+'</ul><p class="meta">Modeled on the published CFB Ranks method. <a class="txt" href="https://www.cfbranks.com/methodology" target="_blank" rel="noopener">CFB Ranks methodology</a></p></section>';
}
function snap(v){return build(v).field.map(function(x){return{n:x.n,s:x.s,seed:x.seed}})}
Promise.all([fetch('/data/msm-rankings.json',{cache:'no-cache'}).then(function(r){return r.json()}),fetch('/data/resume.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null}).catch(function(){return null}),fetch('/data/committee-notes.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null}).catch(function(){return null}),fetch('/data/ap-top25.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null}).catch(function(){return null})])
.then(function(x){D=x[0];T=D.teams;RS=x[1]?x[1].teams:{};CMN=x[2];AP=x[3];if(AP)AP.ranks.forEach(function(a){APR[a.id]=a.r});BASE={msm:snap('msm'),ap:snap('ap'),cm:snap('cm')};render()})
.catch(function(e){root.innerHTML='<p class="meta">The Playoff Picture could not load. See <a class="txt" href="/rankings/">The MSM Top 25</a>.</p>';if(window.console)console.warn(e)});
})();
