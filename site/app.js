/* ---------- champions ---------- */
const RAW="Aatrox:Aatrox,Ahri:Ahri,Akali:Akali,Akshan:Akshan,Alistar:Alistar,Ambessa:Ambessa,Amumu:Amumu,Anivia:Anivia,Annie:Annie,Aphelios:Aphelios,Ashe:Ashe,AurelionSol:Aurelion Sol,Aurora:Aurora,Azir:Azir,Bard:Bard,Belveth:Bel'Veth,Blitzcrank:Blitzcrank,Brand:Brand,Braum:Braum,Briar:Briar,Caitlyn:Caitlyn,Camille:Camille,Cassiopeia:Cassiopeia,Chogath:Cho'Gath,Corki:Corki,Darius:Darius,Diana:Diana,Draven:Draven,DrMundo:Dr. Mundo,Ekko:Ekko,Elise:Elise,Evelynn:Evelynn,Ezreal:Ezreal,Fiddlesticks:Fiddlesticks,Fiora:Fiora,Fizz:Fizz,Galio:Galio,Gangplank:Gangplank,Garen:Garen,Gnar:Gnar,Gragas:Gragas,Graves:Graves,Gwen:Gwen,Hecarim:Hecarim,Heimerdinger:Heimerdinger,Hwei:Hwei,Illaoi:Illaoi,Irelia:Irelia,Ivern:Ivern,Janna:Janna,JarvanIV:Jarvan IV,Jax:Jax,Jayce:Jayce,Jhin:Jhin,Jinx:Jinx,Kaisa:Kai'Sa,Kalista:Kalista,Karma:Karma,Karthus:Karthus,Kassadin:Kassadin,Katarina:Katarina,Kayle:Kayle,Kayn:Kayn,Kennen:Kennen,Khazix:Kha'Zix,Kindred:Kindred,Kled:Kled,KogMaw:Kog'Maw,KSante:K'Sante,Leblanc:LeBlanc,LeeSin:Lee Sin,Leona:Leona,Lillia:Lillia,Lissandra:Lissandra,Locke:Locke,Lucian:Lucian,Lulu:Lulu,Lux:Lux,Malphite:Malphite,Malzahar:Malzahar,Maokai:Maokai,MasterYi:Master Yi,Mel:Mel,Milio:Milio,MissFortune:Miss Fortune,MonkeyKing:Wukong,Mordekaiser:Mordekaiser,Morgana:Morgana,Naafiri:Naafiri,Nami:Nami,Nasus:Nasus,Nautilus:Nautilus,Neeko:Neeko,Nidalee:Nidalee,Nilah:Nilah,Nocturne:Nocturne,Nunu:Nunu & Willump,Olaf:Olaf,Orianna:Orianna,Ornn:Ornn,Pantheon:Pantheon,Poppy:Poppy,Pyke:Pyke,Qiyana:Qiyana,Quinn:Quinn,Rakan:Rakan,Rammus:Rammus,RekSai:Rek'Sai,Rell:Rell,Renata:Renata Glasc,Renekton:Renekton,Rengar:Rengar,Riven:Riven,Rumble:Rumble,Ryze:Ryze,Samira:Samira,Sejuani:Sejuani,Senna:Senna,Seraphine:Seraphine,Sett:Sett,Shaco:Shaco,Shen:Shen,Shyvana:Shyvana,Singed:Singed,Sion:Sion,Sivir:Sivir,Skarner:Skarner,Smolder:Smolder,Sona:Sona,Soraka:Soraka,Swain:Swain,Sylas:Sylas,Syndra:Syndra,TahmKench:Tahm Kench,Taliyah:Taliyah,Talon:Talon,Taric:Taric,Teemo:Teemo,Thresh:Thresh,Tristana:Tristana,Trundle:Trundle,Tryndamere:Tryndamere,TwistedFate:Twisted Fate,Twitch:Twitch,Udyr:Udyr,Urgot:Urgot,Varus:Varus,Vayne:Vayne,Veigar:Veigar,Velkoz:Vel'Koz,Vex:Vex,Vi:Vi,Viego:Viego,Viktor:Viktor,Vladimir:Vladimir,Volibear:Volibear,Warwick:Warwick,Xayah:Xayah,Xerath:Xerath,XinZhao:Xin Zhao,Yasuo:Yasuo,Yone:Yone,Yorick:Yorick,Yunara:Yunara,Yuumi:Yuumi,Zaahen:Zaahen,Zac:Zac,Zed:Zed,Zeri:Zeri,Ziggs:Ziggs,Zilean:Zilean,Zoe:Zoe,Zyra:Zyra";
const CHAMPS=RAW.split(",").map(s=>{const[id,name]=s.split(":");return{id,name}});
const norm=s=>String(s||"").toLowerCase().normalize("NFD").replace(/[^a-z0-9]/g,"");
const BY=new Map();CHAMPS.forEach(c=>{BY.set(norm(c.name),c);BY.set(norm(c.id),c)});
[["bardo","bard"],["nunuewillump","nunu"],["mundo","drmundo"],["tf","twistedfate"],["mf","missfortune"],["j4","jarvaniv"],["monkeyking","wukong"]].forEach(([a,b])=>{if(BY.get(b))BY.set(a,BY.get(b))});
const find=s=>BY.get(norm(s))||null;
/* Closest champion name for typos ("Caitlin" -> "Caitlyn"). */
function sugerir(s){
  const a=norm(s);if(a.length<2)return null;
  const dist=(x,y)=>{const m=x.length,n=y.length,d=Array.from({length:m+1},(_,i)=>[i,...Array(n).fill(0)]);for(let j=1;j<=n;j++)d[0][j]=j;
    for(let i=1;i<=m;i++)for(let j=1;j<=n;j++)d[i][j]=Math.min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(x[i-1]===y[j-1]?0:1));return d[m][n]};
  let best=null,bd=99;
  CHAMPS.forEach(c=>{const n=norm(c.name);const d=n.startsWith(a)?0:dist(a,n);if(d<bd){bd=d;best=c.name}});
  return bd<=Math.max(2,Math.floor(a.length/3))?best:null;
}
const naoReconheci=vals=>"Não reconheci: "+vals.map(v=>{const s=sugerir(v);return s?`"${v}" (você quis dizer ${s}?)`:`"${v}"`}).join(", ")+". Escolha um nome da lista.";
const slug=c=>c.id==="MonkeyKing"?"wukong":c.id.toLowerCase();
const ROLES=["TOP","JUNGLE","MID","ADC","SUPPORT"];
const ROLE_PT={TOP:"Top",JUNGLE:"Jungle",MID:"Mid",ADC:"ADC",SUPPORT:"Suporte"};
const EXAMPLE=["Darius","Viego","Yasuo","Kai'Sa","Thresh"];
const $=id=>document.getElementById(id);
/* Every call to the local server carries this header; the server refuses API calls without it,
   so other websites open in the browser cannot use this API (they cannot send custom headers to it). */
const api=(url,opts={})=>fetch(url,{...opts,headers:{...(opts.headers||{}),"X-CounterPick":"1"}});
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
const arr=v=>Array.isArray(v)?v.filter(Boolean):[];
const store={get:(k,d=null)=>{try{const v=localStorage.getItem(k);return v===null?d:v}catch{return d}},set:(k,v)=>{try{localStorage.setItem(k,v)}catch{}},del:k=>{try{localStorage.removeItem(k)}catch{}}};
const statusEl=$("status");
function setStatus(t,err){statusEl.textContent=t;statusEl.classList.toggle("err",!!err)}
CHAMPS.forEach(c=>{const o=document.createElement("option");o.value=c.name;$("champs").append(o)});

/* Empty-slot icons: lane glyphs on a map square (lane drawn bold, map faint) and crossed swords for an enemy of unknown lane. */
const MAP='<rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"/>';
const GLYPH={
  TOP:MAP+'<path d="M6 18V6h12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
  MID:MAP+'<path d="M6.5 17.5l11-11" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
  ADC:MAP+'<path d="M6 18h12V6" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
  JUNGLE:MAP+'<path d="M8 18c0-5 2-9 4.5-11M12 18c0-4 1.5-7 4-8.5M8.5 11c-1-1.5-1.5-3-1.2-4.6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>',
  SUPPORT:MAP+'<path d="M12 6.5l5 2v3.6c0 3-2.1 5.2-5 6-2.9-.8-5-3-5-6V8.5z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M12 9.5v5M9.5 12h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  ENEMY:'<circle cx="12" cy="12" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="1.8" fill="currentColor"/><path d="M12 2.5v4M12 17.5v4M2.5 12h4M17.5 12h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
};
const LANE_NAME={TOP:"Top",JUNGLE:"Jungle",MID:"Mid",ADC:"ADC",SUPPORT:"Suporte",ENEMY:"Inimigo"};
function phEl(kind,tone){const s=el("span","ph"+(tone?" "+tone:""));s.setAttribute("aria-hidden","true");setPh(s,kind);return s}
function setPh(s,kind){if(s.dataset.kind===kind)return;s.dataset.kind=kind;s.title=LANE_NAME[kind]||"";
  s.innerHTML='<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'+GLYPH[kind]+'</svg>'}
function iconEl(name,size){
  const img=document.createElement("img");img.className="ic"+(size?" "+size:"");img.alt="";img.loading="lazy";
  img.onerror=()=>{img.removeAttribute("src");img.hidden=true;if(img._ph)img._ph.hidden=false};
  setIcon(img,name);return img;
}
/* Shows the champion portrait, or the slot's placeholder glyph when there is no champion (never a broken image). */
function setIcon(img,name){
  const c=find(name);
  if(c){img.src="icons/"+c.id+".jpg";img.hidden=false}else{img.removeAttribute("src");img.hidden=!!img._ph}
  img.alt=c?c.name:"";
  if(img._ph)img._ph.hidden=!!c;
}

/* ---------- official item / rune lists (Riot Data Dragon) ---------- */
let ITEMS=[],TREES=[];const ITEM_BY=new Map(),RUNE_BY=new Map();
const SHARDS=["Força Adaptativa","Velocidade de Ataque","Aceleração de Habilidade","Velocidade de Movimento","Escalamento de Vida","Vida","Tenacidade e Resistência a Lentidão"];
const SPELLS=["Flash","Incendiar","Teleporte","Barreira","Exaustão","Curar","Golpear","Purificar","Fantasma"];
const SPELL_BY=new Map();
const dataReady=Promise.all([
  fetch("data/spells.json").then(r=>r.ok?r.json():[]).then(a=>a.forEach(s=>SPELL_BY.set(norm(s.n),s))).catch(()=>{}),
  fetch("data/items.json").then(r=>r.json()).then(a=>{ITEMS=a;a.forEach(i=>ITEM_BY.set(norm(i.n),i))}),
  fetch("data/runes.json").then(r=>r.json()).then(a=>{TREES=a;a.forEach(t=>{RUNE_BY.set(norm(t.n),{n:t.n,k:t.k,tree:t.n});t.slots.forEach(s=>s.forEach(r=>RUNE_BY.set(norm(r.n),{n:r.n,k:r.k,tree:t.n})))})})
]).catch(()=>{});
const treeOf=n=>TREES.find(t=>norm(t.n)===norm(n));
const rowOf=(t,n)=>t?t.slots.findIndex((s,i)=>i>0&&s.some(r=>norm(r.n)===norm(n))):-1;
const itemOk=(n,kinds)=>{const it=ITEM_BY.get(norm(n));return !!it&&(!kinds||kinds.includes(it.k))};
/* Anything not in this patch's official lists is dropped before it can be shown. */
function cleanBuild(p){
  const q=JSON.parse(JSON.stringify(p||{}));let removed=0;
  const ru=q.runes||{};const key=RUNE_BY.get(norm(ru.keystone));const tree=key&&treeOf(key.tree);
  if(!tree||!tree.slots[0].some(r=>norm(r.n)===norm(ru.keystone))){if(q.runes)removed++;q.runes=null}
  else{
    const p0=arr(ru.p);ru.p=p0.filter(n=>rowOf(tree,n)>0);removed+=p0.length-ru.p.length;
    const st=treeOf(ru.secondary);const s0=arr(ru.s);ru.s=st&&st!==tree?s0.filter(n=>rowOf(st,n)>0):[];removed+=s0.length-ru.s.length;
    const h0=arr(ru.shards);ru.shards=h0.filter(n=>SHARDS.some(s=>norm(s)===norm(n)));removed+=h0.length-ru.shards.length;
  }
  const f=(list,ok)=>{const a=arr(list);const b=a.filter(ok);removed+=a.length-b.length;return b};
  q.spells=f(q.spells,n=>SPELLS.some(s=>norm(s)===norm(n)));
  q.start=f(q.start,n=>itemOk(n));
  if(q.boots&&!itemOk(q.boots,["boots"])){q.boots=null;removed++}
  q.core=f(q.core,n=>itemOk(n,["full","boots"]));
  q.later=f(q.later,n=>itemOk(n,["full","boots"]));
  q._removed=removed;return q;
}

/* ---------- patch notes (data/patch_notes.json) ---------- */
let NOTES=null,SERVER_PATCH=null;
const notesOk=()=>NOTES&&SERVER_PATCH&&NOTES.patch===SERVER_PATCH;
const notesFor=n=>notesOk()?NOTES.changes.filter(x=>norm(x.c)===norm(n)):[];
fetch("data/patch_notes.json").then(r=>r.ok?r.json():null).then(j=>{NOTES=j;renderPatch()}).catch(()=>{});
function renderPatch(){
  const panel=$("patchPanel");
  if(!notesOk()){panel.hidden=true;return}
  panel.hidden=false;
  $("patchTag").textContent=`${NOTES.patch} · ${NOTES.date}`;
  $("patchIntro").replaceChildren(document.createTextNode("Campeões que mudaram nos dois últimos patches. Os que você joga aparecem em negrito. Passe o mouse para ver o detalhe. "));
  const a=el("a",null,"Notas oficiais da Riot");a.href=NOTES.url;a.target="_blank";a.rel="noopener";a.style.color="var(--accent)";$("patchIntro").append(a);
  const box=$("patchList");box.replaceChildren();
  const mine=new Set(PROFILE.champs.filter(c=>c.g>=3).map(c=>norm(c.n)));
  [...NOTES.changes].sort((x,y)=>(mine.has(norm(y.c))-mine.has(norm(x.c)))||y.p.localeCompare(x.p)).forEach(x=>{
    const s=el("span","pt "+x.t+(mine.has(norm(x.c))?" mine":""));s.title=x.d;
    s.append((x.t==="buff"?"▲ ":x.t==="nerf"?"▼ ":"◆ ")+x.c+" ",el("small",null,x.p));box.append(s);
  });
  $("patchItems").textContent=NOTES.items.length?"Itens: "+NOTES.items.join(" · "):"";
}

/* ---------- profiles ---------- */
/* Owner profile: snapshot used until the first refresh from op.gg; after that the fresh copy is kept in this browser. */
const OWNER_SNAPSHOT={id:"owner",owner:true,exemplo:true,name:"Exemplo#BR1",url:"",updated:"",
  rank:"Perfil de exemplo: coloque seu Riot ID no .env (COUNTERPICK_RIOT_ID) e clique em Atualizar",main:"MID",champs:[
  {n:"Ahri",r:["MID"],g:20,wr:55,kda:3.1},{n:"Orianna",r:["MID"],g:12,wr:50,kda:3.4},{n:"Viktor",r:["MID"],g:8,wr:50,kda:2.9},
  {n:"Jinx",r:["ADC"],g:6,wr:50,kda:2.8},{n:"Thresh",r:["SUPPORT"],g:4,wr:50,kda:2.6}]};
let OWNER=OWNER_SNAPSHOT;
try{const o=JSON.parse(store.get("cp_owner","null"));if(o&&Array.isArray(o.champs))OWNER={...o,id:"owner",owner:true}}catch{}
let SAVED=[];
try{SAVED=JSON.parse(store.get("cp_profiles","[]"));if(!Array.isArray(SAVED))SAVED=[]}catch{SAVED=[]}
SAVED=SAVED.filter(p=>p&&Array.isArray(p.champs)&&p.id!=="owner");
const allProfiles=()=>[OWNER,...SAVED];
let PROFILE=allProfiles().find(p=>p.id===store.get("cp_prof_active"))||OWNER;
const profFor=l=>PROFILE.champs.filter(c=>arr(c.r).includes(l)).sort((a,b)=>b.g-a.g);
const findProf=n=>PROFILE.champs.find(c=>norm(c.n)===norm(n));
const jogos=g=>`${g} jogo${g===1?"":"s"}`;
const statLine=c=>`${jogos(c.g)}, ${c.wr}% de vitória`;

function renderProfileHead(){
  $("profName").textContent=PROFILE.name;
  $("profRank").textContent=PROFILE.rank||"";
  const a=$("profLink");a.textContent=(PROFILE.fonte?PROFILE.fonte+" · ":"")+"dados de "+(PROFILE.updated||"-")+" · ver no op.gg";
  if(/^https:\/\/(www\.)?op\.gg\//.test(PROFILE.url||""))a.href=PROFILE.url;else a.removeAttribute("href");
  $("profDel").hidden=!!PROFILE.owner;
  const sel=$("profSel");sel.replaceChildren();
  allProfiles().forEach(p=>{const o=document.createElement("option");o.value=p.id;o.textContent=p.name+(p.owner?" (você)":"");o.selected=p===PROFILE;sel.append(o)});
}
function renderProfile(){
  const box=$("profChamps");box.replaceChildren();
  const list=profFor(lane).slice(0,6);
  if(!list.length){box.append(el("span","note",`Sem ranqueadas de ${ROLE_PT[lane]} nesta temporada.`));return}
  list.forEach(c=>{
    const d=el("div","pc"),t=el("div");t.append(el("b",null,c.n));
    t.append(el("span",c.g>=5?(c.wr>=55?"good":c.wr<45?"bad":""):"",`${c.wr}% · ${jogos(c.g)}`),el("span",null,"KDA "+c.kda));
    d.append(iconEl(c.n),t);box.append(d);
  });
}
function setProfile(p){
  PROFILE=p;store.set("cp_prof_active",p.id);
  renderProfileHead();poolTouched=false;store.del("cp_pool");
  setLane(ROLES.includes(p.main)?p.main:lane);renderPatch();
}
const saveProfiles=()=>store.set("cp_profiles",JSON.stringify(SAVED));
/* Profile by Riot ID: straight from Riot when the key is configured (last ~40 ranked games),
   otherwise op.gg (whole season). */
const lerJson=async r=>{try{return await r.json()}catch{return {}}};
async function fetchProfile(riotId,onStep){
  let r,j;
  try{r=await api("api/perfil_riot?riot_id="+encodeURIComponent(riotId));j=await lerJson(r)}
  catch{throw new Error("O sistema parou de responder. Confira se a janela preta do CounterPick continua aberta.")}
  if(r.status===404&&!j.erro)throw new Error("O CounterPick aberto está desatualizado. Feche a janela preta e abra o INICIAR.bat de novo.");
  if(r.status===412||r.status===401||r.status===403){
    if(onStep)onStep("Chave da Riot indisponível: buscando no op.gg…");
    r=await api("api/perfil_opgg?riot_id="+encodeURIComponent(riotId));j=await lerJson(r);j.fonte=j.fonte||"op.gg · temporada";
  }
  if(!r.ok)throw new Error(j.erro||"Não consegui buscar o perfil. Tente de novo em um minuto.");
  return {name:j.name,url:j.url,updated:new Date().toLocaleDateString("pt-BR"),rank:j.rank,main:j.main,champs:j.champs,fonte:j.fonte||""};
}
$("profSel").addEventListener("change",e=>{const p=allProfiles().find(x=>x.id===e.target.value);if(p)setProfile(p)});
$("profDel").addEventListener("click",()=>{if(PROFILE.owner)return;SAVED=SAVED.filter(p=>p!==PROFILE);saveProfiles();setProfile(OWNER);setStatus("Perfil removido.")});
$("profRefresh").addEventListener("click",async()=>{
  const b=$("profRefresh");b.disabled=true;b.textContent="Atualizando…";
  try{
    const fresh=await fetchProfile(PROFILE.name);
    if(PROFILE.owner){OWNER={...fresh,id:"owner",owner:true};store.set("cp_owner",JSON.stringify(OWNER));setProfile(OWNER)}
    else{const i=SAVED.indexOf(PROFILE);SAVED[i]={...fresh,id:PROFILE.id};saveProfiles();setProfile(SAVED[i])}
    setStatus(`Perfil de ${PROFILE.name} atualizado com o op.gg.`);
  }catch(e){setStatus(e.message,true)}
  finally{b.disabled=false;b.textContent="Atualizar"}
});
function parseRiotId(v){
  v=String(v||"").trim();
  const m=v.match(/op\.gg\/(?:[a-z]{2}(?:-[a-z]{2})?\/)?(?:lol\/)?summoners\/[a-z0-9]+\/([^/?#]+)/i);
  if(m){const s=decodeURIComponent(m[1]);const cut=s.lastIndexOf("-");return cut>0?s.slice(0,cut)+"#"+s.slice(cut+1).toUpperCase():null}
  return /^.{3,16}#[A-Za-z0-9]{2,5}$/.test(v)?v:null;
}
$("profAdd").addEventListener("click",()=>{$("impBox").hidden=false;$("impId").focus()});
$("impCancel").addEventListener("click",()=>{$("impBox").hidden=true;$("impStatus").textContent=""});
$("impId").addEventListener("keydown",e=>{if(e.key==="Enter")$("impGo").click()});
$("impGo").addEventListener("click",async()=>{
  const id=parseRiotId($("impId").value),st=$("impStatus");
  if(!id){st.textContent="Cole o link do op.gg ou escreva nome#TAG (ex.: Nome#BR1).";st.className="status err";return}
  st.className="status";st.textContent="Buscando na Riot (leva uns 20 a 30 segundos)…";$("impGo").disabled=true;
  try{
    const p=await fetchProfile(id,t=>{st.textContent=t});const pid="p_"+norm(p.name);
    if(norm(p.name)===norm(OWNER.name)){st.textContent="Esse é o seu perfil, ele já está na lista. Para puxar os dados mais recentes da Riot, use o botão Atualizar ao lado do seu nome.";return}
    SAVED=SAVED.filter(x=>x.id!==pid);const prof={...p,id:pid};SAVED.push(prof);saveProfiles();setProfile(prof);
    $("impBox").hidden=true;$("impId").value="";st.textContent="";setStatus(`${prof.name} adicionado: ${prof.champs.length} campeões.`);
  }catch(e){st.className="status err";st.textContent=e.message}
  finally{$("impGo").disabled=false}
});

/* ---------- teams ---------- */
function buildTeam(box,prefix,defaults,tone){
  ROLES.forEach((r,i)=>{
    const d=el("div","slot");d.dataset.role=r;
    const lab=el("label",null,ROLE_PT[r]);lab.htmlFor=prefix+i;
    const inp=document.createElement("input");inp.type="text";inp.id=prefix+i;inp.setAttribute("list","champs");inp.autocomplete="off";inp.spellcheck=false;
    inp.value=defaults?defaults[i]:"";
    const img=iconEl("");img._ph=phEl(r,tone);setIcon(img,inp.value);
    inp.addEventListener("input",()=>setIcon(img,inp.value));
    const row=el("div","pin");row.append(img,img._ph,inp);d.append(lab,row);box.append(d);
  });
  return [...box.querySelectorAll("input")];
}
function fillTeam(inputs,values){inputs.forEach((inp,i)=>{if(inp.disabled)return;inp.value=values[i]||"";inp.dispatchEvent(new Event("input"))})}
const team=$("team"),allyTeam=$("allyTeam");
const enemyInputs=buildTeam(team,"e",EXAMPLE,"enemy");
const allyInputs=buildTeam(allyTeam,"a",null,"ally");
const useAllies=$("useAllies");
const readTeam=inputs=>inputs.map((inp,i)=>{const c=!inp.disabled&&find(inp.value);return c?{role:ROLES[i],name:c.name}:null}).filter(Boolean);
const listOf=s=>String(s||"").split(/[,;\n]/).map(find).filter(Boolean).map(c=>c.name);
useAllies.addEventListener("change",()=>{$("allyBox").hidden=!useAllies.checked;store.set("cp_allies",useAllies.checked?"1":"")});
if(store.get("cp_allies")==="1"){useAllies.checked=true;$("allyBox").hidden=false}

/* ---------- lane, mode, draft ---------- */
let lane="ADC",mode="full",side="blue",pickNo=1,poolTouched=false;
const DRAFT_ORDER=["B1","R1","R2","B2","B3","R3","R4","B4","B5","R5"];
function draftState(){
  const me=(side==="blue"?"B":"R")+pickNo,at=DRAFT_ORDER.indexOf(me),et=side==="blue"?"R":"B";
  const before=DRAFT_ORDER.slice(0,at).filter(x=>x[0]===et).length,after=DRAFT_ORDER.slice(at+1).filter(x=>x[0]===et).length;
  return {me,before,after,last:after===0,blind:before===0};
}
function renderDraft(){
  document.querySelectorAll("#sideSeg button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.side===side)));
  document.querySelectorAll("#pickSeg button").forEach(b=>b.setAttribute("aria-pressed",String(+b.dataset.pick===pickNo)));
  const d=draftState(),info=$("draftInfo");info.replaceChildren();
  const txt=d.blind?"Primeiro pick: nenhum inimigo escolheu ainda. Vou priorizar campeões fortes e difíceis de counterar.":
    d.last?`Último pick: os ${d.before} inimigos já escolheram. Dá para counterar com tudo.`:
    `Antes da sua vez, ${d.before} inimigo${d.before===1?"":"s"} já ${d.before===1?"escolheu":"escolheram"}. Depois de você ainda ${d.after===1?"falta 1":`faltam ${d.after}`}, então o pick precisa aguentar counter.`;
  info.append(el("b",null,(side==="blue"?"Azul ":"Vermelho ")+pickNo+"º pick · "),document.createTextNode(txt));
  store.set("cp_draft",side+pickNo);
}
$("sideSeg").addEventListener("click",e=>{const b=e.target.closest("button");if(b){side=b.dataset.side;renderDraft()}});
$("pickSeg").addEventListener("click",e=>{const b=e.target.closest("button");if(b){pickNo=+b.dataset.pick;renderDraft()}});
{const s=store.get("cp_draft");if(s&&/^(blue|red)[1-5]$/.test(s)){side=s.slice(0,-1);pickNo=+s.slice(-1)}}

function markOpp(){
  const draft=mode==="draft";
  team.classList.toggle("draft-mode",draft);
  team.querySelectorAll(".slot").forEach((s,i)=>{
    setPh(s.querySelector(".ph"),draft?"ENEMY":s.dataset.role);
    s.classList.toggle("opp",!draft&&s.dataset.role===lane);
    s.querySelector("label").textContent=draft?"Inimigo "+(i+1):ROLE_PT[s.dataset.role]+(s.dataset.role===lane?" · oponente":"");
  });
  allyTeam.querySelectorAll(".slot").forEach(s=>{
    const me=s.dataset.role===lane;s.classList.toggle("me",me);
    const inp=s.querySelector("input");inp.disabled=me;inp.placeholder=me?"Você":"";
    s.querySelector("label").textContent=ROLE_PT[s.dataset.role]+(me?" · você":"");
    if(me){inp.value="";inp.dispatchEvent(new Event("input"))}
  });
}
function setMode(m){
  mode=m;
  document.querySelectorAll("#modes button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.mode===m)));
  team.classList.toggle("lane-only",m==="lane");
  $("draftBox").hidden=m!=="draft";
  $("teamNote").textContent=m==="lane"?"Só o seu oponente direto conta neste modo."
    :m==="draft"?"Coloque só os inimigos que já escolheram, em qualquer ordem. Não precisa saber a rota deles."
    :"O campo vermelho é o seu oponente direto. Os outros quatro ajudam a ler a comp inimiga.";
  markOpp();if(m==="draft")renderDraft();
  store.set("cp_mode",m);
}
$("modes").addEventListener("click",e=>{const b=e.target.closest("button");if(b)setMode(b.dataset.mode)});

const useProf=$("useProf"),poolIn=$("pool");
function autoPool(){if(!poolTouched)poolIn.value=useProf.checked?profFor(lane).filter(c=>c.g>=2&&c.wr>=40).map(c=>c.n).join(", "):""}
function setLane(l){
  lane=l;
  document.querySelectorAll("#lanes button").forEach(x=>x.setAttribute("aria-pressed",String(x.dataset.lane===l)));
  const mp=$("mineIc")._ph;if(mp)setPh(mp,l);
  markOpp();renderProfile();autoPool();
}
$("lanes").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;setLane(b.dataset.lane);store.set("cp_lane",lane)});
{const p=store.get("cp_pool");if(p){poolIn.value=p;poolTouched=true}}
poolIn.addEventListener("input",()=>{poolTouched=!!poolIn.value.trim()});
poolIn.addEventListener("change",e=>{if(e.target.value.trim())store.set("cp_pool",e.target.value);else store.del("cp_pool")});
useProf.addEventListener("change",autoPool);

const mineIn=$("mine"),go=$("go"),resBody=$("resBody");
{const img=$("mineIc");img._ph=phEl(lane,"ally");img.after(img._ph);img.onerror=()=>{img.removeAttribute("src");img.hidden=true;img._ph.hidden=false}}
function syncMine(){setIcon($("mineIc"),mineIn.value);go.textContent=find(mineIn.value)?"Avaliar minha escolha":"Recomendar counter"}
mineIn.addEventListener("input",syncMine);

renderProfileHead();
setLane(ROLES.includes(store.get("cp_lane"))?store.get("cp_lane"):(ROLES.includes(PROFILE.main)?PROFILE.main:"ADC"));
setMode(["lane","full","draft"].includes(store.get("cp_mode"))?store.get("cp_mode"):"full");
syncMine();

/* ---------- result cards ---------- */
function itemChip(name,cls){
  const it=ITEM_BY.get(norm(name));const c=el("span","chip"+(cls?" "+cls:"")+(it?"":" txt"));
  if(it){const i=document.createElement("img");i.src="icons/items/"+it.id+".png";i.alt="";i.loading="lazy";c.append(i)}
  c.append(document.createTextNode(it?it.n:String(name)));return c;
}
function runeChip(name,cls){
  const r=RUNE_BY.get(norm(name));const c=el("span","chip"+(cls?" "+cls:"")+(r?"":" txt"));
  if(r){const i=document.createElement("img");i.src="icons/runes/"+r.k+".png";i.alt="";i.loading="lazy";c.append(i)}
  c.append(document.createTextNode(r?r.n:String(name)));return c;
}
function spellChip(name){
  const s=SPELL_BY.get(norm(name));const c=el("span","chip"+(s?"":" txt"));
  if(s){const i=document.createElement("img");i.src="icons/spells/"+s.k+".png";i.alt="";i.loading="lazy";c.append(i)}
  c.append(document.createTextNode(s?s.n:String(name)));return c;
}
function group(label,nodes){const g=el("div","bgroup");g.append(el("span",null,label));const ch=el("div","chips");nodes.forEach(n=>n&&ch.append(n));g.append(ch);return g}
const ROTA_URL={TOP:"top",JUNGLE:"jungle",MID:"mid",ADC:"adc",SUPPORT:"support"};

function pickCard(raw,opp,buildOnly){
  const c=find(raw?.name);if(!c)return null;
  const p=cleanBuild(raw);
  const tier=["S","A","B"].includes(p.tier)?p.tier:"B";
  const card=el("article","pick enter");
  const t=el("div","tier "+tier,tier);t.title={S:"Melhor escolha agora",A:"Boa escolha",B:"Dá para jogar"}[tier];
  card.append(t);
  const body=el("div");body.style.minWidth="0";
  const h=el("h3",null,c.name);
  if(p.offPool&&!buildOnly)h.append(el("span","tag","fora da sua lista"));
  if(p.melhorDoPool)h.append(el("span","tag poolbest","★ melhor do seu pool"));
  const mine=useProf.checked&&findProf(c.name);
  if(mine)h.append(el("span","stat",(PROFILE.owner?"você: ":PROFILE.name.split("#")[0]+": ")+statLine(mine)));
  notesFor(c.name).forEach(x=>{const tg=el("span","ptag "+x.t,(x.t==="buff"?"▲ buff ":x.t==="nerf"?"▼ nerf ":"◆ ajuste ")+x.p);tg.title=x.d;h.append(tg)});
  const rk={baixo:"baixo",medio:"medio",alto:"alto"}[p.risk];
  if(rk)h.append(el("span","risk "+rk,"risco de counter: "+{baixo:"baixo",medio:"médio",alto:"alto"}[rk]));
  const tt=el("div","pick-title");tt.append(iconEl(c.name,"lg"),h);body.append(tt);
  if(p.why)body.append(el("span","k",buildOnly?"O confronto":"Por quê"),el("p",null,String(p.why)));
  const aj=arr(p.ajustes);
  if(aj.length){
    body.append(el("span","k","O que pesou nesta partida"));
    const ul=el("ul","ajustes");
    aj.forEach(a=>{const li=el("li",a.efeito>=0?"up":"down");const v=(a.efeito>=0?"+":"−")+(Math.abs(a.efeito)*100).toFixed(1).replace(".",",");
      li.append(el("b",null,v),document.createTextNode(" "+String(a.texto)));ul.append(li)});
    body.append(ul);
  }
  if(p.plan)body.append(el("span","k","Como jogar"),el("p",null,String(p.plan)));
  if(rk&&p.riskWhy)body.append(el("span","k","Cuidado com"),el("p",null,String(p.riskWhy)));

  const b=el("div","build"),ru=p.runes||{};
  if(ru.keystone){
    const rrow=el("div","brow");
    rrow.append(group(String(ru.primary||"Runas"),[runeChip(ru.keystone,"key"),...arr(ru.p).map(x=>runeChip(x))]));
    if(arr(ru.s).length)rrow.append(group(String(ru.secondary||"Secundária"),arr(ru.s).map(x=>runeChip(x))));
    if(arr(ru.shards).length)rrow.append(group("Fragmentos",arr(ru.shards).map(x=>el("span","chip txt",String(x)))));
    b.append(rrow);
  }
  const sk=skillBlock(p.order,p.max);if(sk)b.append(sk);
  const irow=el("div","brow");
  if(arr(p.spells).length)irow.append(group("Feitiços",arr(p.spells).map(x=>spellChip(x))));
  if(arr(p.start).length)irow.append(group("Itens iniciais",arr(p.start).map(x=>itemChip(x))));
  if(p.boots)irow.append(group("Botas",[itemChip(p.boots)]));
  if(irow.children.length)b.append(irow);
  if(arr(p.core).length)b.append(group("Build principal (nesta ordem)",arr(p.core).map((x,i)=>itemChip(x,i===0?"key":""))));
  if(arr(p.later).length)b.append(group("Opções depois, conforme o jogo",arr(p.later).map(x=>itemChip(x))));
  if(p.buildNote)b.append(el("p","note",String(p.buildNote)));
  b.append(el("span","src "+(p._removed?"partial":"ok"),p._removed?"Algum item ou runa que não existe mais no patch foi tirado desta build. Confira no op.gg.":"✓ Runas e itens conferidos com a lista oficial do patch atual."));
  if(b.children.length>1)body.append(b);

  const links=el("div","links");
  const add=(href,txt)=>{const a=el("a",null,txt);a.href=href;a.target="_blank";a.rel="noopener";links.append(a)};
  add(`https://op.gg/pt/lol/champions/${slug(c)}/build/${ROTA_URL[lane]}`,`${c.name} no op.gg`);
  const o=opp&&find(opp.name);
  if(o)add(`https://op.gg/pt/lol/champions/${slug(c)}/counters/${ROTA_URL[lane]}`,`Confrontos de ${c.name} no op.gg`);
  body.append(links);card.append(body);
  return card;
}
/* Skill order: which skill to level at each level (grid) + which to max first. */
function skillBlock(order,max){
  order=arr(order).map(x=>String(x).toUpperCase()).filter(x=>"QWER".includes(x)&&x.length===1);
  const prio=String(max||"").split(">").map(s=>s.trim().toUpperCase()).filter(x=>["Q","W","E"].includes(x));
  if(!order.length&&!prio.length)return null;
  const g=el("div","bgroup");g.append(el("span",null,"Habilidades"));
  if(prio.length){
    const pr=el("p","skillprio");
    pr.append(document.createTextNode("Maximize primeiro: "));
    prio.forEach((k,i)=>{if(i)pr.append(document.createTextNode(" → "));pr.append(el("b","sk "+k,k))});
    pr.append(document.createTextNode(" · "),el("b","sk R","R"),document.createTextNode(" sempre que puder (níveis 6, 11 e 16)"));
    g.append(pr);
  }
  if(order.length){
    const wrap=el("div","skillwrap");
    const grid=el("div","skillgrid");grid.style.setProperty("--n",order.length);
    grid.setAttribute("role","table");grid.setAttribute("aria-label","Ordem das habilidades por nível");
    grid.append(el("span","lvl hd",""));
    order.forEach((_,i)=>grid.append(el("span","lvl hd",String(i+1))));
    ["Q","W","E","R"].forEach(k=>{
      grid.append(el("span","lvl key sk "+k,k));
      order.forEach(x=>{const c=el("span","cell"+(x===k?" on sk "+k:""),x===k?k:"");grid.append(c)});
    });
    wrap.append(grid);g.append(wrap);
    g.append(el("p","note","Ordem mais usada no op.gg. Cada coluna é um nível: suba a habilidade marcada."));
  }
  return g;
}
/* Win-chance panel for "Minha escolha". */
function evalPanel(a,champ){
  if(!a)return null;
  const box=el("div","evalbox "+a.tom);
  const top=el("div","evaltop");
  top.append(iconEl(champ,"lg"));
  const t=el("div");
  t.append(el("span","k","Chance de vitória estimada"));
  const big=el("div","evalnum");big.append(el("b",null,Math.round(a.chance*100)+"%"),el("span","evalverd",a.veredito));
  t.append(big);top.append(t);box.append(top);
  if(arr(a.partes).length){const ul=el("ul","evallist");a.partes.forEach(x=>ul.append(el("li",null,String(x))));box.append(ul)}
  arr(a.alertas).forEach(x=>box.append(el("p","evalwarn",String(x))));
  if(a.aviso)box.append(el("p","note",String(a.aviso)));
  return box;
}
/* Red card: a pick NOT to use in this game (worst of the player's pool, or a popular pick that does badly here). */
function naoValeCard(n){
  const c=find(n.name);if(!c)return null;
  const card=el("article","pick naovale");
  card.append(el("div","tier X","✕"));
  const body=el("div");body.style.minWidth="0";
  body.append(el("span","k nvk",n.doPool?"Do seu pool, não use agora":"Popular, mas não use agora"));
  const h=el("h3",null,c.name);
  const mine=useProf.checked&&findProf(c.name);
  if(mine)h.append(el("span","stat",(PROFILE.owner?"você: ":PROFILE.name.split("#")[0]+": ")+statLine(mine)));
  const tt=el("div","pick-title");tt.append(iconEl(c.name,"lg"),h);body.append(tt);
  body.append(el("p","nvmotivo",String(n.motivo||"")));
  if(n.popular)body.append(el("p",null,String(n.popular)));
  if(n.posicao&&n.total)body.append(el("p","note",`Nesta partida ele ficou em ${n.posicao}º de ${n.total} campeões da rota.`));
  const aj=arr(n.ajustes).filter(a=>a.efeito<0);
  if(aj.length){
    const ul=el("ul","ajustes");
    aj.forEach(a=>{const li=el("li","down");li.append(el("b",null,"−"+(Math.abs(a.efeito)*100).toFixed(1).replace(".",",")),document.createTextNode(" "+String(a.texto)));ul.append(li)});
    body.append(ul);
  }
  if(n.why)body.append(el("p","note",String(n.why)));
  card.append(body);return card;
}
function renderAvoid(av){
  av=arr(av).filter(a=>find(a.name));if(!av.length)return;
  resBody.append(el("span","k","Evite contra esse oponente"));
  const box=el("div","avoid");
  av.forEach(a=>{const d=el("div"),s=el("span");s.append(el("b",null,find(a.name).name+": "),document.createTextNode(String(a.why||"")));d.append(iconEl(a.name,"sm"),s);box.append(d)});
  resBody.append(box);
}

/* ---------- recommend ---------- */
async function recommend(){
  await dataReady;
  const draft=mode==="draft",mineC=find(mineIn.value);
  if(mineIn.value.trim()&&!mineC){setStatus(naoReconheci([mineIn.value.trim()]),true);mineIn.focus();return}
  const bad=[...enemyInputs,...(useAllies.checked?allyInputs:[])].filter(i=>!i.disabled&&i.value.trim()&&!find(i.value));
  if(bad.length){setStatus(naoReconheci(bad.map(i=>i.value.trim())),true);bad[0].focus();return}
  const ini=enemyInputs.map((inp,i)=>{const c=find(inp.value);return c?{name:c.name,role:draft?"":ROLES[i]}:null}).filter(Boolean);
  const opp=draft?null:ini.find(e=>e.role===lane)||null;
  if(mode==="lane"&&!opp){setStatus(`Coloque o seu oponente de ${ROLE_PT[lane]} no campo vermelho.`,true);enemyInputs[ROLES.indexOf(lane)].focus();return}
  if(mode==="full"&&!ini.length&&!mineC){setStatus("Coloque pelo menos um campeão inimigo. Se ainda ninguém escolheu, use o modo Draft.",true);enemyInputs[0].focus();return}
  const body={rota:lane,modo:mode,inimigos:mode==="lane"?[opp]:ini,
    aliados:useAllies.checked?readTeam(allyInputs):[],
    pool:listOf(poolIn.value),perfil:useProf.checked?PROFILE.champs.map(c=>({n:c.n,g:c.g,wr:c.wr})):[],
    draft:draft?{after:draftState().after}:null,meu:mineC?mineC.name:null};
  resBody.replaceChildren();go.disabled=true;setStatus("");
  const think=el("div","thinking");think.append(el("span","dot"),el("span",null,mineC&&opp?"Buscando a build desse confronto no op.gg…":body.aliados.length?"Calculando… (aliado novo leva uns segundos na primeira vez: a sinergia vem do op.gg)":"Calculando…"));resBody.append(think);
  const t0=Date.now();
  try{
    const r=await api("api/recomendar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const j=await r.json();think.remove();
    if(!r.ok){resBody.append(el("p","summary",j.erro||"Não consegui calcular. Tente de novo."));return}
    resBody.append(el("p","summary",j.summary));
    if(mineC&&j.avaliacao){const ev=evalPanel(j.avaliacao,mineC.name);if(ev)resBody.append(ev)}
    const box=el("div","picks");resBody.append(box);
    arr(j.picks).forEach(p=>{const card=pickCard(p,opp,!!mineC);if(card)box.append(card)});
    if(!box.children.length)box.append(el("p","note","Nenhum campeão com dados suficientes para essa situação."));
    if(!mineC&&arr(j.mais).length){
      const extra=arr(j.mais).map(p=>{const card=pickCard(p,opp,false);if(card&&p.posicao)card.querySelector("h3")?.prepend(el("span","tag pos",p.posicao+"º"));return card}).filter(Boolean);
      if(extra.length){
        const mb=el("div","maisbox");mb.hidden=true;mb.id="maisbox";extra.forEach(c=>mb.append(c));
        const bt=el("button","ghost maisbtn",`Ver mais ${extra.length} opções`);bt.type="button";
        bt.setAttribute("aria-expanded","false");bt.setAttribute("aria-controls","maisbox");
        bt.addEventListener("click",()=>{mb.hidden=!mb.hidden;bt.setAttribute("aria-expanded",String(!mb.hidden));
          bt.textContent=mb.hidden?`Ver mais ${extra.length} opções`:"Esconder as opções extras"});
        resBody.append(bt,mb);
      }
    }
    if(!mineC&&j.exotico){
      const card=pickCard(j.exotico,opp,false);
      if(card){
        card.classList.add("exocard");
        const h=card.querySelector("h3");if(h&&j.exotico.aposta)h.append(el("span","tag aposta","aposta"));
        const head=el("div","poolhead");
        head.append(el("span","k exok","◆ Pick exótico que pode dar certo"),
          el("p",null,String(j.exotico.exoticoTexto||"")),
          el("p","note",`Se entrasse no ranking normal, ficaria em ${j.exotico.posicao}º lugar.`));
        card.children[1].prepend(head);
        resBody.append(card);
      }
    }
    if(!mineC&&j.melhorPool){
      const card=pickCard(j.melhorPool,opp,false);
      if(card){
        card.classList.add("poolcard");
        const body=card.children[1];
        const head=el("div","poolhead");
        head.append(el("span","k poolk","★ Do seu pool, a melhor opção agora"),
          el("p","poolnivel",String(j.melhorPool.nivelTexto||"")),
          el("p","note",`No ranking desta partida, ele ficou em ${j.melhorPool.posicao}º lugar.`));
        body.prepend(head);
        resBody.append(card);
      }
    }
    if(!mineC&&j.naoVale){const nv=naoValeCard(j.naoVale);if(nv)resBody.append(nv)}
    if(!mineC)renderAvoid(arr(j.avoid).filter(a=>!j.naoVale||norm(a.name)!==norm(j.naoVale.name)));
    const s=(Date.now()-t0)/1000;
    setStatus(s<0.5?"Pronto.":`Pronto em ${s.toFixed(1).replace(".",",")} s.`);
    $("result").scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});
  }catch{think.remove();resBody.append(el("p","summary","O sistema parou de responder. Confira se a janela preta do CounterPick continua aberta."))}
  finally{go.disabled=false}
}
go.addEventListener("click",recommend);

/* ---------- print reading (champion select / Tab), done on this PC ---------- */
const ROTA_IDX={top:0,jungle:1,mid:2,adc:3,support:4};
let ultimoPrint=null,invertido=false;
function marcar(inp,certeza){inp.classList.toggle("confira",!certeza);inp.title=certeza?"":"Confira este nome: a leitura não teve certeza."}
function aplicarPrint(){
  const r=ultimoPrint;if(!r)return;
  const ini=invertido?r.esquerda:r.direita, ali=invertido?r.direita:r.esquerda;
  const rIni=invertido?r.rotas_esquerda:r.rotas_direita, rAli=invertido?r.rotas_direita:r.rotas_esquerda;
  [...enemyInputs,...allyInputs].forEach(i=>marcar(i,true));
  // inimigos: no draft, na ordem; nos outros modos, cada um na rota mais provável
  const slotsIni=Array(5).fill(null);
  if(mode==="draft")ini.forEach((c,k)=>{slotsIni[k]=c});
  else ini.forEach(c=>{const k=ROTA_IDX[rIni[c.name]];if(k!==undefined&&!slotsIni[k])slotsIni[k]=c});
  fillTeam(enemyInputs,slotsIni.map(c=>c?c.name:""));
  slotsIni.forEach((c,k)=>{if(c)marcar(enemyInputs[k],c.certeza)});
  // aliados: cada um na rota mais provável; quem cair na SUA rota provavelmente é você
  let voce=null;const slotsAli=Array(5).fill(null);
  ali.forEach(c=>{const k=ROTA_IDX[rAli[c.name]];if(k===undefined)return;if(ROLES[k]===lane){voce=c;return}if(!slotsAli[k])slotsAli[k]=c});
  if(ali.length){useAllies.checked=true;$("allyBox").hidden=false;store.set("cp_allies","1")}
  fillTeam(allyInputs,slotsAli.map(c=>c?c.name:""));
  slotsAli.forEach((c,k)=>{if(c&&!allyInputs[k].disabled)marcar(allyInputs[k],c.certeza)});
  const total=ini.length+ali.length,duvida=[...ini,...ali].filter(c=>!c.certeza).length;
  let txt=total?`Li ${total} ${total===1?"campeão":"campeões"}`+(duvida?` (${duvida} para conferir, em amarelo)`:"")+". ":"Não achei campeões nesse print. ";
  if(voce)txt+=`No seu lugar (${ROLE_PT[lane]}) está ${voce.name}: se for você, coloque em "Minha escolha". `;
  if(total)txt+="Se os times vieram trocados, clique em Inverter times.";
  $("printStatus").textContent=txt;$("printTools").hidden=false;
  preparar();
}
async function lerPrint(file){
  if(!file||!/^image\/(png|jpeg|webp)$/.test(file.type)){$("printStatus").textContent="Mande um print em PNG ou JPG.";$("printTools").hidden=false;return}
  if(file.size>25*1024*1024){$("printStatus").textContent="Print grande demais (máximo 25 MB).";$("printTools").hidden=false;return}
  $("dropTitle").textContent="Lendo o print…";
  try{
    const r=await api("api/ler_print",{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:file});
    const j=await lerJson(r);
    if(!r.ok){$("printStatus").textContent=j.erro||"Não consegui ler esse print.";$("printTools").hidden=false;return}
    ultimoPrint=j;invertido=false;aplicarPrint();
  }catch{$("printStatus").textContent="O sistema parou de responder. A janela preta continua aberta?";$("printTools").hidden=false}
  finally{$("dropTitle").textContent="Cole o print aqui (Ctrl+V), arraste ou clique para escolher"}
}
const drop=$("drop");
drop.addEventListener("click",()=>$("printFile").click());
drop.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();$("printFile").click()}});
$("printFile").addEventListener("change",e=>{const f=e.target.files[0];e.target.value="";lerPrint(f)});
["dragenter","dragover"].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.add("over")}));
["dragleave","drop"].forEach(t=>drop.addEventListener(t,e=>{e.preventDefault();drop.classList.remove("over")}));
drop.addEventListener("drop",e=>{const f=[...e.dataTransfer.files].find(f=>f.type.startsWith("image/"));lerPrint(f)});
document.addEventListener("paste",e=>{const it=[...(e.clipboardData?.items||[])].find(i=>i.type.startsWith("image/"));if(it){e.preventDefault();lerPrint(it.getAsFile())}});
$("printSwap").addEventListener("click",()=>{invertido=!invertido;aplicarPrint()});
[...enemyInputs,...allyInputs].forEach(i=>i.addEventListener("input",()=>marcar(i,true)));
/* While the player is still typing, ask the server to fetch in the background what is slow the first time
   (ally synergy and the build for "Minha escolha" vs the lane opponent). By the time they click, it is ready. */
let _prepT=null;
function preparar(){
  clearTimeout(_prepT);
  _prepT=setTimeout(()=>{
    const opp=mode==="draft"?null:find(enemyInputs[ROLES.indexOf(lane)].value);
    const mineC=find(mineIn.value);
    const aliados=useAllies.checked?readTeam(allyInputs):[];
    if(!aliados.length&&!(mineC&&opp))return;
    api("api/preparar",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({rota:lane,aliados,meu:mineC?mineC.name:null,oponente:opp?opp.name:null})}).catch(()=>{});
  },700);
}
[...allyInputs,...enemyInputs,mineIn].forEach(i=>i.addEventListener("change",preparar));
[...allyInputs,mineIn].forEach(i=>i.addEventListener("input",preparar));
useAllies.addEventListener("change",preparar);
$("lanes").addEventListener("click",preparar);
$("clear").addEventListener("click",()=>{
  fillTeam(enemyInputs,[]);fillTeam(allyInputs,[]);mineIn.value="";syncMine();
  poolTouched=false;store.del("cp_pool");autoPool();
  resBody.replaceChildren(el("p","summary","Tudo limpo. Preencha os campeões e clique em Recomendar counter."));
  setStatus("");enemyInputs[mode==="lane"?ROLES.indexOf(lane):0].focus();
});

/* ---------- system data (op.gg sync, Riot) ---------- */
/* Friends (via Tailscale) can use everything except the owner's data controls. */
let DONO=true;
api("api/status").then(r=>r.json()).then(s=>{
  DONO=!!s.dono;
  // o Riot ID do dono vem do .env do próprio PC (nunca fica no código publicado)
  if(DONO&&s.dono_riot_id&&OWNER.exemplo){OWNER={...OWNER,exemplo:false,name:String(s.dono_riot_id),rank:"Clique em Atualizar para puxar seu perfil da Riot"};if(PROFILE.owner)setProfile(OWNER)}
  if(!DONO){
    ["dataSync","riotTest","riotCollect","riotQtd","riotStop"].forEach(id=>{const e=$(id);if(e)e.hidden=true});
    document.querySelectorAll("#sysPanel .sysblock .note:last-child").forEach(n=>n.textContent="Só o dono do sistema atualiza os dados e faz as coletas.");
  }
}).catch(()=>{});
async function refreshData(){
  let j;
  try{j=await (await api("api/dados/status")).json()}catch{$("dataBadge").textContent="Sistema desligado: abra pelo INICIAR.bat.";return}
  const s=j.sync||{},c=j.coleta||{};
  SERVER_PATCH=j.patch||null;renderPatch();
  const pronto=!!j.patch&&j.builds>0;
  $("dataBadge").textContent=pronto?`Patch ${j.patch} · dados de ${j.sincronizado_em}`:"Sem dados ainda";
  const ban=$("syncBanner");
  if(s.rodando){ban.hidden=false;ban.textContent=pronto
      ?`Saiu patch novo: atualizando as estatísticas (${s.feito}/${s.total||"…"}). Você pode usar enquanto isso; os números ainda são do patch anterior.`
      :`Primeira vez: baixando as estatísticas de todos os campeões (${s.feito}/${s.total||"…"}). Leva uns 10 minutos; os resultados aparecem quando terminar.`}
  else if(!pronto){ban.hidden=false;ban.textContent=s.erro?("Não consegui baixar as estatísticas: "+s.erro+" Confira a internet e clique em Dados do sistema > Atualizar agora."):"Ainda sem estatísticas. Abra Dados do sistema e clique em Atualizar agora."}
  else ban.hidden=true;
  $("dataState").textContent=s.rodando?`${s.etapa} ${s.total?`(${s.feito}/${s.total})`:""}`
    :(pronto?`Patch ${j.patch}: ${j.builds} campeões/rotas, atualizado em ${j.sincronizado_em}.`:"Sem dados.")+(s.erro?" "+s.erro:"");
  $("sysTag").textContent=pronto?`patch ${j.patch}`:"sem dados";
  const rs=$("riotState");
  const elos=Object.entries(c.por_elo||{}).map(([k,v])=>`${k} ${v}`).join(", ");
  rs.textContent=c.rodando?`Coletando: ${c.partidas}/${c.meta} partidas${elos?" ("+elos+")":""}…`
    :`${j.partidas_riot} partidas do patch atual já somadas.`+(c.erro?" Última coleta: "+c.erro:(c.etapa?" "+c.etapa:""));
  rs.className="note"+(c.erro?" status err":"");
  $("dataSync").disabled=!!s.rodando;$("riotCollect").disabled=!!c.rodando;$("riotStop").hidden=!c.rodando||!DONO;
  if(s.rodando||c.rodando)setTimeout(refreshData,2500);
}
$("dataSync").addEventListener("click",async()=>{await api("api/dados/atualizar",{method:"POST"});setTimeout(refreshData,400)});
$("riotCollect").addEventListener("click",async()=>{
  const r=await api("api/riot/coletar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({partidas:+$("riotQtd").value})});
  const j=await r.json();if(!r.ok){$("riotState").textContent=j.erro;$("riotState").className="note status err";return}
  setTimeout(refreshData,400);
});
$("riotStop").addEventListener("click",async()=>{await api("api/riot/parar",{method:"POST"});$("riotState").textContent="Parando a coleta (termina a partida atual)…"});
$("riotTest").addEventListener("click",async()=>{
  const out=$("riotOut"),st=$("riotState");out.replaceChildren();st.className="note";st.textContent="Testando a chave da Riot…";
  try{
    const r=await api("api/riot/perfil?regiao=br&riot_id="+encodeURIComponent(OWNER.name));const j=await r.json();
    if(!r.ok){st.className="note status err";st.textContent=j.erro||"A Riot não respondeu.";return}
    st.textContent=`Conexão com a Riot funcionando. ${j.riot_id} · ${j.elo}. Últimas ranqueadas:`;
    j.partidas.forEach(m=>{const d=el("div"),s=el("span");
      s.append(el("b",null,(m.venceu?"Vitória":"Derrota")+" · "),document.createTextNode(`KDA ${m.kda} · ${m.cs} CS · ${m.duracao_min} min · ${m.quando}`));
      d.append(iconEl(m.campeao,"sm"),s);out.append(d)});
  }catch{st.className="note status err";st.textContent="O sistema parou de responder. A janela preta continua aberta?"}
});
refreshData();
