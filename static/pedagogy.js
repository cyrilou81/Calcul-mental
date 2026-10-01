// Source unique des méthodes pédagogiques : utilisée par le test ET par /admin.
(function(global){
function hfmt(n){
  if(n===undefined||n===null)return '';
  let x=Number(n); if(!Number.isFinite(x))return String(n);
  return String(Math.round(x*1000000)/1000000).replace('.',',');
}
function helpBox(content,tip){return {html:content,tip}}
function placeValueHelp(a,b,op){
  let au=Math.abs(a)%10, at=Math.floor(Math.abs(a)/10), bu=Math.abs(b)%10, bt=Math.floor(Math.abs(b)/10), r=op==='+'?a+b:a-b;
  let ru=Math.abs(r)%10, rt=Math.floor(Math.abs(r)/10);
  return `<div class="place-grid"><div class="place-head">Dizaines</div><div class="place-head">Unités</div><div class="place-cell">${at}</div><div class="place-cell">${au}</div><div class="place-cell">${op} ${bt}</div><div class="place-cell">${op} ${bu}</div><div class="place-cell changed">${rt}</div><div class="place-cell">${ru}</div></div><div class="help-step">${a} ${op} ${b} <span class="help-arrow">→</span> ${r}</div>`;
}
function contextualHelp(q){
  const p=q.payload||{}, k=q.kind, a=Number(p.a), b=Number(p.b), n=Number(p.n), d=Number(p.divisor), dividend=Number(p.dividend);
  if(k==='tens'||k==='tens_sub'){
    const op=k==='tens'?'+':'−', r=k==='tens'?a+b:a-b;
    return helpBox(placeValueHelp(a,b,k==='tens'?'+':'-'),`${b} représente ${Math.abs(b/10)} dizaine${Math.abs(b/10)>1?'s':''}. On change les dizaines, mais le chiffre des unités reste ${Math.abs(a)%10}.`);
  }
  if(k==='addition'){
    let to10=10-(a%10||10);
    if(a%10!==0 && b>to10 && to10>0){let rest=b-to10,r=a+b;return helpBox(`<div class="help-step"><span class="help-split">${b} = ${to10} + ${rest}</span></div><div class="help-step">${a} + ${to10} <span class="help-arrow">→</span> ${a+to10}</div><div class="help-step">${a+to10} + ${rest} <span class="help-arrow">→</span> ${r}</div>`,`On fabrique d’abord la dizaine ronde ${a+to10}. C’est souvent plus facile pour calculer de tête.`)}
    let tens=Math.floor(b/10)*10, units=b-tens,r=a+b;return helpBox(`<div class="help-step"><span class="help-split">${b} = ${tens} + ${units}</span></div><div class="help-step">${a} + ${tens} <span class="help-arrow">→</span> ${a+tens}</div>${units?`<div class="help-step">${a+tens} + ${units} <span class="help-arrow">→</span> ${r}</div>`:''}`,`Découpe le deuxième nombre en dizaines et unités, puis ajoute-les l’une après l’autre.`)
  }
  if(k==='subtraction'){
    let tens=Math.floor(b/10)*10, units=b-tens,r=a-b;
    if(b<10 && a%10<b){let down=a%10, rest=b-down;return helpBox(`<div class="help-step"><span class="help-split">${b} = ${down} + ${rest}</span></div><div class="help-step">${a} − ${down} <span class="help-arrow">→</span> ${a-down}</div><div class="help-step">${a-down} − ${rest} <span class="help-arrow">→</span> ${r}</div>`,`Descends d’abord jusqu’à la dizaine ronde, puis enlève ce qui reste.`)}
    return helpBox(`<div class="help-step"><span class="help-split">${b} = ${tens} + ${units}</span></div><div class="help-step">${a} − ${tens} <span class="help-arrow">→</span> ${a-tens}</div>${units?`<div class="help-step">${a-tens} − ${units} <span class="help-arrow">→</span> ${r}</div>`:''}`,`Enlève d’abord les dizaines, puis les unités.`)
  }
  if(k==='double'){
    let x=Number(n), tens=Math.floor(x/10)*10, units=x-tens;
    // Une seule pédagogie, déterminée par le nombre affiché et non par la catégorie
    // technique qui l'a généré. Ainsi un même type de double reçoit toujours la même aide.
    if(x>=10&&units){return helpBox(`<div class="help-step">${x} + ${x}</div><div class="help-step">= (${tens} + ${units}) + (${tens} + ${units})</div><div class="help-step">= ${tens} + ${tens} + ${units} + ${units}</div><div class="help-step">= double de ${tens} + double de ${units}</div><div class="help-step">= ${tens*2} + ${units*2} <span class="help-arrow">→</span> ${x*2}</div>`,`Sépare les dizaines et les unités : double les dizaines, double les unités, puis additionne les deux résultats.`)}
    if(x>=10){let d=x/10;return helpBox(`<div class="help-step">${x} = ${d} dizaine${d>1?'s':''}</div><div class="help-step">Double de ${d} dizaine${d>1?'s':''} = ${d*2} dizaines</div><div class="help-step">${d*2} dizaines <span class="help-arrow">→</span> ${x*2}</div>`,`Calcule le double pour les dizaines et ajoute le zéro des unités.`)}
    return helpBox(`<div class="help-step">${x} + ${x} <span class="help-arrow">→</span> ${x*2}</div>`,`Un double, c’est deux fois le même nombre.`)
  }
  if(k==='half'){
    let x=n,tens=Math.floor(x/10)*10,units=x-tens;
    // Pour une dizaine « impaire » (30, 50, 70, 90), on revient à la dizaine
    // précédente dont la moitié est immédiate, puis on ajoute la moitié de 10.
    if(x>=30 && x%20===10){let previous=x-10;return helpBox(`<div class="help-step"><span class="help-split">${x} = ${previous} + 10</span></div><div class="help-step">Moitié de ${x} = moitié de ${previous} + moitié de 10</div><div class="help-step">= ${previous/2} + 5 <span class="help-arrow">→</span> ${x/2}</div>`,`Prends la dizaine précédente : découpe ${x} en ${previous} + 10. Calcule la moitié de chaque morceau, puis additionne.`)}
    if(x>=20 && tens%20===0 && units%2===0){return helpBox(`<div class="help-step"><span class="help-split">${x} = ${tens} + ${units}</span></div><div class="help-step">${tens} ÷ 2 = ${tens/2}</div>${units?`<div class="help-step">${units} ÷ 2 = ${units/2}</div>`:''}<div class="help-step">${tens/2}${units?` + ${units/2}`:''} <span class="help-arrow">→</span> ${x/2}</div>`,`Partage chaque morceau en deux parts égales.`)}
    return helpBox(`<div class="groups"><span class="group-box">${x/2}</span><span class="group-box">${x/2}</span></div><div class="help-step">${x} ÷ 2 <span class="help-arrow">→</span> ${x/2}</div>`,`Cherche deux parts identiques qui, ensemble, redonnent ${x}.`)
  }
  if(k==='round_tens_add'){
    return helpBox(`<div class="help-step">${a} + ${b}</div><div class="help-step">${a} <span class="help-arrow">→</span> ${a+b}</div>`,`Pars de la dizaine ronde ${a} et ajoute ${b}.`)
  }
  if(k==='complement_tens'){
    let target=Number(p.target),missing=target-a;
    if(missing>10){let nextTen=Math.ceil(a/10)*10;if(nextTen===a)nextTen=a+10;let first=nextTen-a,second=target-nextTen;return helpBox(`<div class="help-jump"><div class="jump-label jump-label-1">+${first}</div><div class="jump-label jump-label-2">+${second}</div><div class="jump-line"><span>${a}</span><span class="jump-arrow">→</span><span>${nextTen}</span><span class="jump-arrow">→</span><span>${target}</span></div></div><div class="help-step">${first} + ${second} <span class="help-arrow">→</span> ${missing}</div><div class="help-step">${a} + ${missing} = ${target}</div>`,`Repère d’abord la dizaine supérieure à ${a} : c’est ${nextTen}. Saute de ${a} à ${nextTen} (+${first}), puis de ${nextTen} à ${target} (+${second}). Additionne les deux sauts.`)}
    return helpBox(`<div class="help-step">${a} <span class="help-arrow">→</span> ${target}</div><div class="help-step">Il manque <span class="help-split">${missing}</span></div><div class="help-step">${a} + ${missing} = ${target}</div>`,`Cherche l’écart entre ${a} et ${target}.`)
  }
  if(k==='place_value'){
    let f=p.factors||{}, order=(p.order||['m','c','d','u']).filter(x=>f[x]), parts=order.map(x=>`${f[x]}${x}`), values={m:1000,c:100,d:10,u:1};
    let detail=order.map(x=>`${f[x]} × ${values[x]} = ${f[x]*values[x]}`).join('<br>');
    return helpBox(`<div class="help-note"><strong>c</strong> = centaines, <strong>d</strong> = dizaines, <strong>u</strong> = unités.<br><strong>1c = 100 &nbsp; 1d = 10 &nbsp; 1u = 1</strong></div><div class="help-step">${parts.join(' ')}</div><div class="help-step">${detail}</div>`,`Lis chaque lettre avant de calculer : c vaut 100, d vaut 10 et u vaut 1.`)
  }
  if(k==='addition3'){
    let ns=p.numbers||[], x=Number(ns[0]),y=Number(ns[1]),z=Number(ns[2]);return helpBox(`<div class="help-step">${x} + ${y} = ${x+y}</div><div class="help-step">${x+y} + ${z} <span class="help-arrow">→</span> ${x+y+z}</div>`,`Additionne deux nombres, puis ajoute le troisième.`)
  }
  if(k==='multiple_of'){
    let factor=Number(p.factor)||(/Quadruple/i.test(q.display)?4:3), word=factor===3?'triple':'quadruple';
    let explanation=factor===3?'Tripler un nombre, c’est le multiplier par 3.':'Quadrupler un nombre, c’est le multiplier par 4.';
    return helpBox(`<div class="help-step">${factor} × ${n} <span class="help-arrow">→</span> ${factor*n}</div>`,explanation)
  }
  if(k==='fraction'){
    let divisor=Number(p.divisor)||(/Quart/i.test(q.display)?4:3), qn=n/divisor, word=divisor===3?'tiers':'quart';return helpBox(`<div class="help-step">${n} ÷ ${divisor} <span class="help-arrow">→</span> ${qn}</div>`,`Le ${word} d’un nombre, c’est le partager en ${divisor} parts égales.`)
  }
  if(k==='multiplication'){
    let x=a,y=b; if(x>y){let t=x;x=y;y=t} // x = petit facteur / stratégie
    if([10,100,1000].includes(x)||[10,100,1000].includes(y)){let m=[10,100,1000].includes(x)?x:y,base=m===x?y:x,steps=Math.round(Math.log10(m)),zeros='0'.repeat(steps);return helpBox(`<div class="help-step">${hfmt(base)} × ${m}</div><div class="decimal-track">${hfmt(base)} <span class="help-arrow">→</span> ${hfmt(base*m)}</div><div class="help-note">Ajoute ${steps} zéro${steps>1?'s':''} à droite.</div>`,`Pour multiplier un entier par ${m}, ajoute ${steps} zéro${steps>1?'s':''} à droite.`)};
    if(x===9){return helpBox(`<div class="help-step">10 × ${y} = ${10*y}</div><div class="help-step">${10*y} − ${y} <span class="help-arrow">→</span> ${9*y}</div>`,`× 9, c’est × 10 puis enlever une fois le nombre.`)}
    if(x===5){return helpBox(`<div class="help-step">10 × ${y} = ${10*y}</div><div class="help-step">Moitié de ${10*y} <span class="help-arrow">→</span> ${5*y}</div>`,`× 5, c’est la moitié de × 10.`)}
    if(x===4){return helpBox(`<div class="help-step">Double de ${y} = ${2*y}</div><div class="help-step">Double de ${2*y} <span class="help-arrow">→</span> ${4*y}</div>`,`× 4, c’est doubler deux fois.`)}
    if(x===6||x===7||x===8){let extra=x-5;return helpBox(`<div class="help-step">5 × ${y} = ${5*y}</div><div class="help-step">${extra} × ${y} = ${extra*y}</div><div class="help-step">${5*y} + ${extra*y} <span class="help-arrow">→</span> ${x*y}</div>`,`Pars de 5 × ${y}, puis ajoute ${extra} fois ${y}.`)}
    return helpBox(`<div class="groups">${Array.from({length:Math.min(x,10)},()=>`<span class="group-box">${y}</span>`).join('')}</div><div class="help-step">${x} groupes de ${y} <span class="help-arrow">→</span> ${x*y}</div>`,`Imagine ${x} groupes contenant chacun ${y}.`)
  }
  if(k==='division'){
    let qn=dividend/d;return helpBox(`<div class="help-step">${hfmt(dividend)} ÷ ${hfmt(d)} = ?</div><div class="help-step">${hfmt(d)} × ? = ${hfmt(dividend)}</div><div class="help-step">${hfmt(d)} × ${hfmt(qn)} = ${hfmt(dividend)}</div>`,`Retourne la division : cherche dans la table de ${hfmt(d)} le nombre qui donne ${hfmt(dividend)}.`)
  }
  if(k==='decimal_multiplication'){
    let m=b,steps=Math.round(Math.log10(m)); if([10,100,1000].includes(m)){
      if(Number.isInteger(a)){
        return helpBox(`<div class="help-step">${hfmt(a)} × ${m}</div><div class="decimal-track">${hfmt(a)} <span class="help-arrow">→</span> ${hfmt(a*m)}</div><div class="help-note">Ajoute ${steps} zéro${steps>1?'s':''} à droite.</div>`,`Pour multiplier un entier par ${m}, ajoute ${steps} zéro${steps>1?'s':''} à droite.`)
      }
      let vals=[a];for(let i=0;i<steps;i++)vals.push(vals[vals.length-1]*10);
      return helpBox(`<div class="decimal-track">${vals.map(hfmt).join('  →  ')}</div><div class="decimal-arrow">${'→ '.repeat(steps)}</div><div class="help-note">Déplace la virgule ${steps} fois vers la droite.</div>`,`Pour multiplier un nombre décimal par ${m}, déplace la virgule ${steps} fois vers la droite.`)
    }
  }
  if(k==='decimal_division'){
    let steps=Math.round(Math.log10(d)); if([10,100,1000].includes(d)){
      let vals=[dividend];for(let i=0;i<steps;i++)vals.push(vals[vals.length-1]/10);
      return helpBox(`<div class="decimal-track">${vals.map(hfmt).join('  →  ')}</div><div class="decimal-arrow">${'← '.repeat(steps)}</div><div class="help-note">${steps} déplacement${steps>1?'s':''} vers la gauche</div>`,`Diviser par ${d}, c’est déplacer la virgule de ${steps} rang${steps>1?'s':''} vers la gauche.`)
    }
  }
  if(k==='decimal'||k==='decimal_sub'){
    let op=k==='decimal'?'+':'−',r=k==='decimal'?a+b:a-b;
    return helpBox(`<div class="place-grid"><div class="place-head">Unités</div><div class="place-head">Après la virgule</div><div class="place-cell">${Math.trunc(a)}</div><div class="place-cell">${hfmt(Math.abs(a-Math.trunc(a))).replace('0,','0,')}</div><div class="place-cell">${Math.trunc(b)}</div><div class="place-cell">${hfmt(Math.abs(b-Math.trunc(b))).replace('0,','0,')}</div></div><div class="help-step">${hfmt(a)} ${op} ${hfmt(b)} <span class="help-arrow">→</span> ${hfmt(r)}</div>`,`Garde les virgules au même endroit : unités avec unités, dixièmes avec dixièmes.`)
  }
  return helpBox(`<div class="help-step">${q.display.replace(' = __','')}</div>`,`Décompose le calcul en petites étapes que tu connais déjà.`)
}


function pedagogicalCase(q){
  const p=q.payload||{}, k=q.kind, a=Number(p.a), b=Number(p.b);
  if(k==='complement_tens') return Number(p.target)-a>10?'gap_gt_10':'gap_le_10';
  if(k==='half'){
    const x=Number(p.n), tens=Math.floor(x/10)*10, units=x-tens;
    if(x>=30 && x%20===10) return 'odd_ten';
    if(x>=20 && tens%20===0 && units%2===0) return 'even_decomposition';
    return 'simple';
  }
  if(k==='addition'){const to10=10-(a%10||10);return a%10!==0&&b>to10&&to10>0?'bridge_10':'decompose'}
  if(k==='subtraction') return b<10&&a%10<b?'bridge_ten':'decompose';
  if(k==='double'){const x=Number(p.n);return x>=10&&x%10?'two_digits':(x>=10?'round_ten':'simple')}
  if(k==='multiplication'){
    const x=Math.min(a,b), y=Math.max(a,b);
    if([10,100,1000].includes(x)||[10,100,1000].includes(y))return 'power10';
    if(x===9)return 'x9'; if(x===5)return 'x5'; if(x===4)return 'x4'; return 'default';
  }
  if(k==='decimal_multiplication') return 'x'+p.b;
  if(k==='decimal_division') return 'div'+p.divisor;
  if(k==='multiple_of') return 'factor'+p.factor;
  if(k==='fraction') return 'divisor'+p.divisor;
  return 'default';
}
function Q(kind,payload,display){return {kind,payload,display}}
// Source unique des exemples d'aide. /admin affiche EXACTEMENT ces pools et le test tire dedans.
const EXAMPLE_POOLS={
  'addition:bridge_10':[Q('addition',{a:8,b:7},'8 + 7 = __'),Q('addition',{a:27,b:6},'27 + 6 = __'),Q('addition',{a:46,b:8},'46 + 8 = __')],
  'addition:decompose':[Q('addition',{a:23,b:14},'23 + 14 = __'),Q('addition',{a:41,b:26},'41 + 26 = __'),Q('addition',{a:32,b:15},'32 + 15 = __')],
  'subtraction:bridge_ten':[Q('subtraction',{a:32,b:7},'32 − 7 = __'),Q('subtraction',{a:51,b:6},'51 − 6 = __'),Q('subtraction',{a:43,b:8},'43 − 8 = __')],
  'subtraction:decompose':[Q('subtraction',{a:47,b:23},'47 − 23 = __'),Q('subtraction',{a:68,b:24},'68 − 24 = __'),Q('subtraction',{a:75,b:32},'75 − 32 = __')],
  'double:simple':[Q('double',{n:7},'Double de 7 = __'),Q('double',{n:8},'Double de 8 = __'),Q('double',{n:6},'Double de 6 = __')],
  'double:two_digits':[Q('double',{n:14},'Double de 14 = __'),Q('double',{n:12},'Double de 12 = __'),Q('double',{n:16},'Double de 16 = __')],
  'double:round_ten':[Q('double',{n:30},'Double de 30 = __'),Q('double',{n:40},'Double de 40 = __'),Q('double',{n:60},'Double de 60 = __')],
  'half:simple':[Q('half',{n:18},'Moitié de 18 = __'),Q('half',{n:16},'Moitié de 16 = __'),Q('half',{n:14},'Moitié de 14 = __')],
  'half:odd_ten':[Q('half',{n:30},'Moitié de 30 = __'),Q('half',{n:50},'Moitié de 50 = __'),Q('half',{n:70},'Moitié de 70 = __'),Q('half',{n:90},'Moitié de 90 = __')],
  'half:even_decomposition':[Q('half',{n:48},'Moitié de 48 = __'),Q('half',{n:64},'Moitié de 64 = __'),Q('half',{n:86},'Moitié de 86 = __')],
  'complement_tens:gap_le_10':[Q('complement_tens',{a:43,target:50},'43 + __ = 50'),Q('complement_tens',{a:54,target:60},'54 + __ = 60'),Q('complement_tens',{a:72,target:80},'72 + __ = 80')],
  'complement_tens:gap_gt_10':[Q('complement_tens',{a:37,target:50},'37 + __ = 50'),Q('complement_tens',{a:45,target:60},'45 + __ = 60'),Q('complement_tens',{a:58,target:70},'58 + __ = 70'),Q('complement_tens',{a:64,target:80},'64 + __ = 80'),Q('complement_tens',{a:76,target:90},'76 + __ = 90')],
  'multiplication:x4':[Q('multiplication',{a:4,b:7},'4 × 7 = __'),Q('multiplication',{a:4,b:6},'4 × 6 = __'),Q('multiplication',{a:4,b:8},'4 × 8 = __')],
  'multiplication:x5':[Q('multiplication',{a:5,b:7},'5 × 7 = __'),Q('multiplication',{a:5,b:6},'5 × 6 = __'),Q('multiplication',{a:5,b:8},'5 × 8 = __')],
  'multiplication:x9':[Q('multiplication',{a:9,b:7},'9 × 7 = __'),Q('multiplication',{a:9,b:6},'9 × 6 = __'),Q('multiplication',{a:9,b:8},'9 × 8 = __')],
  'multiplication:power10':[Q('multiplication',{a:10,b:7},'10 × 7 = __'),Q('multiplication',{a:100,b:6},'100 × 6 = __'),Q('multiplication',{a:1000,b:4},'1000 × 4 = __')],
  'multiplication:default':[Q('multiplication',{a:7,b:6},'7 × 6 = __'),Q('multiplication',{a:8,b:7},'8 × 7 = __'),Q('multiplication',{a:6,b:6},'6 × 6 = __')],
  'division:default':[Q('division',{dividend:42,divisor:6},'42 : 6 = __'),Q('division',{dividend:56,divisor:7},'56 : 7 = __'),Q('division',{dividend:72,divisor:8},'72 : 8 = __')],
  'tens:default':[Q('tens',{a:34,b:20},'34 + 20 = __'),Q('tens',{a:52,b:30},'52 + 30 = __'),Q('tens',{a:26,b:40},'26 + 40 = __')],
  'tens_sub:default':[Q('tens_sub',{a:54,b:20},'54 − 20 = __'),Q('tens_sub',{a:87,b:30},'87 − 30 = __'),Q('tens_sub',{a:69,b:40},'69 − 40 = __')],
  'round_tens_add:default':[Q('round_tens_add',{a:40,b:7},'40 + 7 = __'),Q('round_tens_add',{a:60,b:8},'60 + 8 = __'),Q('round_tens_add',{a:30,b:6},'30 + 6 = __')],
  'addition3:default':[Q('addition3',{numbers:[3,4,2]},'3 + 4 + 2 = __'),Q('addition3',{numbers:[5,2,3]},'5 + 2 + 3 = __'),Q('addition3',{numbers:[4,3,1]},'4 + 3 + 1 = __')],
  'decimal:default':[Q('decimal',{a:2.4,b:1.3},'2,4 + 1,3 = __'),Q('decimal',{a:3.2,b:2.5},'3,2 + 2,5 = __')],
  'decimal_sub:default':[Q('decimal_sub',{a:5.7,b:2.4},'5,7 − 2,4 = __'),Q('decimal_sub',{a:8.6,b:3.2},'8,6 − 3,2 = __')],
  'decimal_multiplication:x10':[Q('decimal_multiplication',{a:2.4,b:10},'2,4 × 10 = __'),Q('decimal_multiplication',{a:3.7,b:10},'3,7 × 10 = __')],
  'decimal_multiplication:x100':[Q('decimal_multiplication',{a:2.4,b:100},'2,4 × 100 = __'),Q('decimal_multiplication',{a:1.8,b:100},'1,8 × 100 = __')],
  'decimal_multiplication:x1000':[Q('decimal_multiplication',{a:2.4,b:1000},'2,4 × 1000 = __'),Q('decimal_multiplication',{a:1.3,b:1000},'1,3 × 1000 = __')],
  'decimal_division:div10':[Q('decimal_division',{dividend:24,divisor:10},'24 : 10 = __'),Q('decimal_division',{dividend:37,divisor:10},'37 : 10 = __')],
  'decimal_division:div100':[Q('decimal_division',{dividend:240,divisor:100},'240 : 100 = __'),Q('decimal_division',{dividend:370,divisor:100},'370 : 100 = __')],
  'decimal_division:div1000':[Q('decimal_division',{dividend:2400,divisor:1000},'2400 : 1000 = __'),Q('decimal_division',{dividend:3700,divisor:1000},'3700 : 1000 = __')],
  'multiple_of:factor3':[Q('multiple_of',{n:7,factor:3},'Triple de 7 = __'),Q('multiple_of',{n:8,factor:3},'Triple de 8 = __')],
  'multiple_of:factor4':[Q('multiple_of',{n:6,factor:4},'Quadruple de 6 = __'),Q('multiple_of',{n:7,factor:4},'Quadruple de 7 = __')],
  'fraction:divisor3':[Q('fraction',{n:18,divisor:3},'Tiers de 18 = __'),Q('fraction',{n:24,divisor:3},'Tiers de 24 = __')],
  'fraction:divisor4':[Q('fraction',{n:20,divisor:4},'Quart de 20 = __'),Q('fraction',{n:28,divisor:4},'Quart de 28 = __')]
};
function poolKey(q){return `${q.kind}:${pedagogicalCase(q)}`}
function poolFor(q){return EXAMPLE_POOLS[poolKey(q)]||EXAMPLE_POOLS[`${q.kind}:default`]||[]}
function sameQuestion(a,b){return String(a.display||'').replace(/\s/g,'')===String(b.display||'').replace(/\s/g,'')}
function exampleFor(q){
  const pool=poolFor(q), candidates=pool.filter(ex=>!sameQuestion(ex,q));
  const usable=candidates.length?candidates:pool;
  if(!usable.length)return q;
  return usable[Math.floor(Math.random()*usable.length)];
}
const catalog=[
 {id:'addition',name:'Additions',cases:[['Passage par 10','addition:bridge_10'],['Décomposition','addition:decompose']]},
 {id:'subtraction',name:'Soustractions',cases:[['Passage par la dizaine','subtraction:bridge_ten'],['Décomposition','subtraction:decompose']]},
 {id:'double',name:'Doubles',cases:[['Petit nombre','double:simple'],['Nombre à 2 chiffres','double:two_digits'],['Dizaine ronde','double:round_ten']]},
 {id:'half',name:'Moitiés',cases:[['Partage simple','half:simple'],['Dizaine impaire : 30 / 50 / 70 / 90','half:odd_ten'],['Décomposition paire','half:even_decomposition']]},
 {id:'complement_tens',name:'Compléments',cases:[['Écart ≤ 10','complement_tens:gap_le_10'],['Écart > 10','complement_tens:gap_gt_10']]},
 {id:'multiplication',name:'Multiplications',cases:[['× 4','multiplication:x4'],['× 5','multiplication:x5'],['× 6, 7, 8','multiplication:default'],['× 9','multiplication:x9'],['× 10 / 100 / 1000','multiplication:power10']]},
 {id:'division',name:'Divisions',cases:[['Multiplication inverse','division:default']]},
 {id:'tens',name:'Additions de dizaines',cases:[['Dizaines / unités','tens:default']]},
 {id:'tens_sub',name:'Soustractions de dizaines',cases:[['Dizaines / unités','tens_sub:default']]},
 {id:'decimal_multiplication',name:'Multiplications décimales',cases:[['× 10','decimal_multiplication:x10'],['× 100','decimal_multiplication:x100'],['× 1000','decimal_multiplication:x1000']]},
 {id:'decimal_division',name:'Divisions décimales',cases:[['÷ 10','decimal_division:div10'],['÷ 100','decimal_division:div100'],['÷ 1000','decimal_division:div1000']]}
];
global.Pedagogy={contextualHelp,pedagogicalCase,exampleFor,poolFor,poolKey,catalog,examplePools:EXAMPLE_POOLS};
})(window);
