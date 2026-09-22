from __future__ import annotations
import json, random, sqlite3, statistics, time, copy, os, os, re
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=Path(__file__).parent
DB=Path(os.environ.get('DB_PATH', str(ROOT/'calcul_mental.db')))
app=Flask(__name__, static_folder='static', static_url_path='')
app.secret_key=os.environ.get('SECRET_KEY','dev-only-change-me')

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS configs(profile_id INTEGER PRIMARY KEY, data TEXT NOT NULL, FOREIGN KEY(profile_id) REFERENCES profiles(id));
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,profile_id INTEGER NOT NULL,started_at TEXT DEFAULT CURRENT_TIMESTAMP,active_ms INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(profile_id) REFERENCES profiles(id));
    CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT,session_id INTEGER NOT NULL,position INTEGER NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,display TEXT NOT NULL,expected INTEGER NOT NULL,given_answer INTEGER,status TEXT NOT NULL,response_ms INTEGER,source TEXT NOT NULL,retry_from INTEGER,attempts INTEGER NOT NULL DEFAULT 0,had_error INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(session_id) REFERENCES sessions(id));
    ''')
    cols={r['name'] for r in c.execute('PRAGMA table_info(questions)')}
    if 'attempts' not in cols: c.execute('ALTER TABLE questions ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0')
    if 'had_error' not in cols: c.execute('ALTER TABLE questions ADD COLUMN had_error INTEGER NOT NULL DEFAULT 0')
    pcols={r['name'] for r in c.execute('PRAGMA table_info(profiles)')}
    if 'account_id' not in pcols: c.execute('ALTER TABLE profiles ADD COLUMN account_id INTEGER NOT NULL DEFAULT 1')
    c.commit(); c.close()

DEFAULT={
 'duration':300,'count':50,
 'categories':{
  'double':{'enabled':True,'pct':15,'min':1,'max':10,'display':'both'},
  'addition':{'enabled':True,'pct':20,'aMin':1,'aMax':10,'bMin':1,'bMax':10,'maxResult':100,'withCarry':True},
  'subtraction':{'enabled':True,'pct':15,'aMin':1,'aMax':10,'bMin':1,'bMax':10,'nonNegative':True},
  'decimal':{'enabled':False,'pct':0,'min':0,'max':20,'decimals':1,'withCarry':True},
  'multiplication':{'enabled':True,'pct':15,'tables':[2,3],'factorMin':1,'factorMax':10},
  'division':{'enabled':True,'pct':10,'tables':[2,3,4],'quotientMin':1,'quotientMax':10},
  'complement10':{'enabled':True,'pct':10},
  'tens':{'enabled':True,'pct':15,'startMin':10,'startMax':99,'mode':'10','multiples':[10,20,30,40,50,60,70,80,90],'maxResult':100}
 }}

def get_cfg(pid):
    c=db(); r=c.execute('SELECT data FROM configs WHERE profile_id=?',(pid,)).fetchone(); c.close()
    cfg=copy.deepcopy(DEFAULT)
    if not r: return cfg
    saved=json.loads(r['data'])
    cfg.update({k:v for k,v in saved.items() if k!='categories'})
    for kind, values in saved.get('categories',{}).items():
        if kind in cfg['categories'] and isinstance(values,dict): cfg['categories'][kind].update(values)
        else: cfg['categories'][kind]=values
    return cfg

def allocate(n,cats):
    vals=[]; used=0
    for k,v in cats.items():
        if v.get('enabled') and v.get('pct',0)>0:
            exact=n*v['pct']/100; base=int(exact); vals.append([k,base,exact-base]); used+=base
    vals.sort(key=lambda x:x[2], reverse=True)
    for i in range(n-used): vals[i%len(vals)][1]+=1
    return {k:b for k,b,_ in vals}

def gen(kind,cfg):
    if kind=='double':
        n=random.randint(cfg['min'],cfg['max']); mode=cfg.get('display','both'); mode=random.choice(['word','sum']) if mode=='both' else mode
        return {'n':n,'mode':mode}, (f'Double de {n} = __' if mode=='word' else f'{n} + {n} = __'), n*2
    if kind=='addition':
        # "Sans retenue" = aucune colonne décimale ne produit une somme >= 10.
        def no_carry(x,y):
            while x or y:
                if (x % 10) + (y % 10) >= 10: return False
                x//=10; y//=10
            return True
        candidates=[]
        for x in range(int(cfg['aMin']),int(cfg['aMax'])+1):
            for y in range(int(cfg['bMin']),int(cfg['bMax'])+1):
                if cfg.get('maxResult') and x+y>cfg['maxResult']: continue
                if cfg.get('withCarry',True) or no_carry(x,y): candidates.append((x,y))
        if not candidates: raise ValueError("Aucune addition possible avec ces réglages sans retenue")
        a,b=random.choice(candidates)
        return {'a':a,'b':b},f'{a} + {b} = __',a+b
    if kind=='subtraction':
        for _ in range(100):
            a=random.randint(cfg['aMin'],cfg['aMax']); b=random.randint(cfg['bMin'],cfg['bMax'])
            if not cfg.get('nonNegative',True) or a>=b: break
        if cfg.get('nonNegative',True) and a<b: a,b=max(a,b),min(a,b)
        return {'a':a,'b':b},f'{a} − {b} = __',a-b
    if kind=='decimal':
        # Addition de décimaux uniquement. Sans retenue, chaque colonne de chiffres
        # (partie décimale et partie entière) doit rester strictement inférieure à 10.
        decimals=max(1,min(2,int(cfg.get('decimals',1)))); scale=10**decimals
        lo=int(round(float(cfg.get('min',0))*scale)); hi=int(round(float(cfg.get('max',20))*scale))
        if hi<lo: lo,hi=hi,lo
        def no_carry_scaled(x,y):
            while x or y:
                if (x % 10) + (y % 10) >= 10: return False
                x//=10; y//=10
            return True
        candidates=[]
        # Random sampling avoids building an enormous Cartesian product for wide ranges.
        for _ in range(1200):
            x=random.randint(lo,hi); y=random.randint(lo,hi)
            if cfg.get('withCarry',True) or no_carry_scaled(x,y):
                candidates.append((x,y))
                if len(candidates)>=80: break
        if not candidates: raise ValueError("Aucune addition de décimaux possible avec ces réglages sans retenue")
        a,b=random.choice(candidates)
        av=a/scale; bv=b/scale; expected=(a+b)/scale
        fmt=lambda x: (f'{x:.{decimals}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'a':av,'b':bv,'op':'addition','decimals':decimals},f'{fmt(av)} + {fmt(bv)} = __',expected
    if kind=='multiplication':
        a=random.choice(cfg['tables']); b=random.randint(cfg['factorMin'],cfg['factorMax']); return {'a':a,'b':b},f'{a} × {b} = __',a*b
    if kind=='division':
        d=random.choice(cfg['tables']); q=random.randint(cfg['quotientMin'],cfg['quotientMax']); return {'dividend':d*q,'divisor':d},f'{d*q} : {d} = __',q
    if kind=='complement10':
        a=random.randint(1,9); return {'a':a},f'{a} + __ = 10',10-a
    if kind=='tens':
        for _ in range(100):
            a=random.randint(cfg['startMin'],cfg['startMax']); choices=[10] if cfg.get('mode')=='10' else cfg.get('multiples',[10])
            b=random.choice(choices)
            if not cfg.get('maxResult') or a+b<=cfg['maxResult']: break
        return {'a':a,'b':b},f'{a} + {b} = __',a+b

def previous_errors(pid):
    c=db(); s=c.execute('SELECT id FROM sessions WHERE profile_id=? ORDER BY id DESC LIMIT 1',(pid,)).fetchone()
    if not s: c.close(); return []
    rows=c.execute("SELECT id,kind,payload,display,expected FROM questions WHERE session_id=? AND status='INCORRECT' ORDER BY position",(s['id'],)).fetchall(); c.close(); return [dict(x) for x in rows]

def authenticated(): return isinstance(session.get('account_id'), int)
def current_account_id(): return session.get('account_id')
def require_auth():
    if not authenticated(): return ({'error':'Connexion requise'},401)
    return None
def owns_profile(pid):
    aid=current_account_id()
    c=db(); r=c.execute('SELECT id FROM profiles WHERE id=? AND account_id=?',(pid,aid)).fetchone(); c.close(); return bool(r)

def password_error(password):
    if len(password)<12: return 'Le mot de passe doit contenir au moins 12 caractères.'
    if not re.search(r'[a-z]',password) or not re.search(r'[A-Z]',password) or not re.search(r'\d',password) or not re.search(r'[^A-Za-z0-9]',password):
        return 'Utilise au moins une minuscule, une majuscule, un chiffre et un caractère spécial.'
    return None

@app.get('/')
def index(): return send_from_directory(ROOT/'static','index.html')
@app.get('/api/auth/status')
def auth_status():
    if not authenticated(): return {'authenticated':False}
    c=db(); a=c.execute('SELECT username FROM accounts WHERE id=?',(current_account_id(),)).fetchone(); c.close()
    if not a: session.clear(); return {'authenticated':False}
    return {'authenticated':True,'username':a['username']}
@app.post('/api/auth/register')
def auth_register():
    data=request.json or {}; username=(data.get('username') or '').strip(); password=str(data.get('password') or '')
    if len(username)<3 or len(username)>40: return {'error':'L’identifiant doit contenir entre 3 et 40 caractères.'},400
    if not re.fullmatch(r'[A-Za-z0-9._-]+',username): return {'error':'Identifiant : lettres, chiffres, point, tiret et underscore uniquement.'},400
    if (err:=password_error(password)): return {'error':err},400
    c=db()
    try:
        count=c.execute('SELECT COUNT(*) n FROM accounts').fetchone()['n']
        # Le premier compte créé récupère les profils historiques de la base V28 et antérieures.
        if count==0:
            c.execute('INSERT INTO accounts(id,username,password_hash) VALUES(1,?,?)',(username,generate_password_hash(password))); aid=1
        else:
            cur=c.execute('INSERT INTO accounts(username,password_hash) VALUES(?,?)',(username,generate_password_hash(password))); aid=cur.lastrowid
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); return {'error':'Cet identifiant existe déjà.'},409
    c.close(); session.clear(); session['account_id']=aid; return {'ok':True,'username':username}
@app.post('/api/auth/login')
def auth_login():
    data=request.json or {}; username=(data.get('username') or '').strip(); password=str(data.get('password') or '')
    c=db(); a=c.execute('SELECT id,username,password_hash FROM accounts WHERE username=? COLLATE NOCASE',(username,)).fetchone(); c.close()
    if not a or not check_password_hash(a['password_hash'],password): return {'error':'Identifiant ou mot de passe incorrect.'},401
    session.clear(); session['account_id']=a['id']; return {'ok':True,'username':a['username']}
@app.post('/api/auth/logout')
def auth_logout(): session.clear(); return {'ok':True}
@app.get('/api/profiles')
def profiles():
    if (e:=require_auth()): return e
    c=db(); rows=[dict(x) for x in c.execute('SELECT id,name,created_at FROM profiles WHERE account_id=? ORDER BY name',(current_account_id(),))]; c.close(); return jsonify(rows)
@app.post('/api/profiles')
def create_profile():
    if (e:=require_auth()): return e
    name=(request.json.get('name') or '').strip()
    if not name: return {'error':'Nom requis'},400
    try:
        c=db(); cur=c.execute('INSERT INTO profiles(name,account_id) VALUES(?,?)',(name,current_account_id())); pid=cur.lastrowid; c.execute('INSERT INTO configs(profile_id,data) VALUES(?,?)',(pid,json.dumps(DEFAULT))); c.commit(); c.close(); return {'id':pid,'name':name}
    except sqlite3.IntegrityError: return {'error':'Ce profil existe déjà'},409
@app.delete('/api/profiles/<int:pid>')
def delete_profile(pid):
    if (e:=require_auth()): return e
    c=db()
    p=c.execute('SELECT id,name FROM profiles WHERE id=? AND account_id=?',(pid,current_account_id())).fetchone()
    if not p:
        c.close(); return {'error':'Profil introuvable'},404
    session_ids=[r['id'] for r in c.execute('SELECT id FROM sessions WHERE profile_id=?',(pid,)).fetchall()]
    if session_ids:
        marks=','.join('?' for _ in session_ids)
        c.execute(f'DELETE FROM questions WHERE session_id IN ({marks})',session_ids)
    c.execute('DELETE FROM sessions WHERE profile_id=?',(pid,))
    c.execute('DELETE FROM configs WHERE profile_id=?',(pid,))
    c.execute('DELETE FROM profiles WHERE id=?',(pid,))
    c.commit(); c.close()
    return {'ok':True}
@app.get('/api/config/<int:pid>')
def config(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    return jsonify(get_cfg(pid))
@app.put('/api/config/<int:pid>')
def save_config(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    data=request.json; data['duration']=max(60,min(3600,int(data.get('duration',300)))); data['count']=max(1,min(500,int(data.get('count',50)))); cats=data.get('categories',{}); total=sum(v.get('pct',0) for v in cats.values() if v.get('enabled'))
    if total!=100: return {'error':f'Le total doit être 100 % (actuellement {total} %).'},400
    if cats.get('multiplication',{}).get('enabled') and not cats['multiplication'].get('tables'): return {'error':'Choisis au moins une table de multiplication.'},400
    if cats.get('division',{}).get('enabled') and not cats['division'].get('tables'): return {'error':'Choisis au moins une table de division.'},400
    c=db(); c.execute('INSERT INTO configs(profile_id,data) VALUES(?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data',(pid,json.dumps(data))); c.commit(); c.close(); return {'ok':True}
@app.post('/api/session/start/<int:pid>')
def start(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    cfg=get_cfg(pid); count=cfg.get('count',50); retries=previous_errors(pid)[:count]; remaining=count-len(retries); alloc=allocate(remaining,cfg['categories']) if remaining else {}
    # Une même opération ne doit apparaître qu'une seule fois dans une séance.
    # La clé ignore le mode d'affichage des doubles : « Double de 8 » et « 8 + 8 »
    # représentent le même fait numérique et ne peuvent donc pas coexister.
    def operation_key(kind, payload):
        if kind == 'double': return (kind, payload.get('n'))
        if kind in ('addition', 'subtraction', 'multiplication', 'tens'): return (kind, payload.get('a'), payload.get('b'))
        if kind == 'decimal': return (kind, payload.get('a'), payload.get('b'), payload.get('op'))
        if kind == 'division': return (kind, payload.get('dividend'), payload.get('divisor'))
        if kind == 'complement10': return (kind, payload.get('a'))
        return (kind, json.dumps(payload, sort_keys=True))

    qs=[]; seen=set()
    # Les reprises sont prioritaires. Si une ancienne séance contenait par hasard
    # deux fois le même calcul, on ne le remet qu'une fois.
    for r in retries:
        payload=json.loads(r['payload']); key=operation_key(r['kind'],payload)
        if key in seen: continue
        seen.add(key)
        qs.append({'kind':r['kind'],'payload':payload,'display':r['display'],'expected':r['expected'],'source':'RETRY','retry_from':r['id']})

    # Pour chaque nouvelle question, on régénère si le calcul existe déjà.
    # La limite évite toute boucle infinie lorsque la configuration contient
    # moins de combinaisons possibles que le nombre de questions demandé.
    for kind,n in alloc.items():
        added=0; tries=0; max_tries=max(500,n*100)
        while added<n and tries<max_tries:
            tries+=1
            payload,display,expected=gen(kind,cfg['categories'][kind]); key=operation_key(kind,payload)
            if key in seen: continue
            seen.add(key)
            qs.append({'kind':kind,'payload':payload,'display':display,'expected':expected,'source':'GENERATED','retry_from':None})
            added+=1
    random.shuffle(qs)
    c=db(); cur=c.execute('INSERT INTO sessions(profile_id) VALUES(?)',(pid,)); sid=cur.lastrowid
    for i,q in enumerate(qs): c.execute('INSERT INTO questions(session_id,position,kind,payload,display,expected,status,source,retry_from) VALUES(?,?,?,?,?,?,\'UNANSWERED\',?,?)',(sid,i,q['kind'],json.dumps(q['payload']),q['display'],q['expected'],q['source'],q['retry_from']))
    c.commit(); rows=[dict(x) for x in c.execute('SELECT id,position,kind,display,source FROM questions WHERE session_id=? ORDER BY position',(sid,))]; c.close(); return {'sessionId':sid,'duration':cfg.get('duration',300),'questions':rows}
@app.post('/api/session/<int:sid>/answer')
def answer(sid):
    if (e:=require_auth()): return e
    c0=db(); own=c0.execute('SELECT 1 FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone(); c0.close()
    if not own: return {'error':'Séance inconnue'},404
    qid=int(request.json['questionId']); given=float(request.json['answer']); ms=max(0,int(request.json.get('responseMs',0)))
    c=db(); q=c.execute('SELECT expected FROM questions WHERE id=? AND session_id=?',(qid,sid)).fetchone()
    if not q: c.close(); return {'error':'Question inconnue'},404
    oldq=c.execute('SELECT expected,attempts,had_error FROM questions WHERE id=? AND session_id=?',(qid,sid)).fetchone()
    attempts=(oldq['attempts'] or 0)+1
    ok=abs(given-float(oldq['expected'])) < 1e-9; had_error=bool(oldq['had_error']) or not ok
    # Une question reste statistiquement en erreur dès le premier essai faux, même si elle est corrigée ensuite.
    status=('INCORRECT' if had_error else 'CORRECT') if ok or attempts>=3 else 'UNANSWERED'
    c.execute('UPDATE questions SET given_answer=?,status=?,response_ms=?,attempts=?,had_error=? WHERE id=?',(given,status,ms,attempts,1 if had_error else 0,qid)); c.commit(); c.close(); return {'correct':ok,'expected':oldq['expected'],'attempts':attempts,'remaining':max(0,3-attempts)}
@app.delete('/api/session/<int:sid>')
def cancel_session(sid):
    if (e:=require_auth()): return e
    c0=db(); own=c0.execute('SELECT 1 FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone(); c0.close()
    if not own: return {'error':'Séance inconnue'},404
    c=db(); c.execute('DELETE FROM questions WHERE session_id=?',(sid,)); c.execute('DELETE FROM sessions WHERE id=?',(sid,)); c.commit(); c.close(); return {'ok':True}

@app.post('/api/session/<int:sid>/finish')
def finish(sid):
    if (e:=require_auth()): return e
    c0=db(); own=c0.execute('SELECT 1 FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone(); c0.close()
    if not own: return {'error':'Séance inconnue'},404
    ms=max(0,int(request.json.get('activeMs',0))); c=db(); c.execute('UPDATE sessions SET active_ms=? WHERE id=?',(ms,sid)); c.commit(); c.close(); return {'ok':True}
@app.get('/api/stats/<int:pid>')
def stats(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    c=db(); ss=[dict(x) for x in c.execute('SELECT id,started_at,active_ms FROM sessions WHERE profile_id=? ORDER BY id DESC LIMIT 30',(pid,))]
    out=[]
    for s in ss:
        qs=[dict(x) for x in c.execute('SELECT * FROM questions WHERE session_id=?',(s['id'],))]
        attempted=[q for q in qs if q['status']!='UNANSWERED']; correct=[q for q in attempted if q['status']=='CORRECT']; times=[q['response_ms'] for q in correct if q['response_ms'] is not None]
        out.append({'id':s['id'],'date':s['started_at'],'activeMs':s['active_ms'],'attempted':len(attempted),'correct':len(correct),'incorrect':len(attempted)-len(correct),'accuracy':round(100*len(correct)/len(attempted),1) if attempted else 0,'medianMs':int(statistics.median(times)) if times else None})
    c.close(); return {'sessions':out}

@app.get('/api/session/<int:sid>/stats')
def session_stats(sid):
    if (e:=require_auth()): return e
    c=db(); s=c.execute('SELECT id,profile_id,started_at,active_ms FROM sessions WHERE id=?',(sid,)).fetchone()
    if not s: c.close(); return {'error':'Séance inconnue'},404
    if not owns_profile(s['profile_id']): c.close(); return {'error':'Séance inconnue'},404
    qs=[dict(x) for x in c.execute("SELECT id,position,kind,display,expected,given_answer,status,response_ms,source,attempts,had_error FROM questions WHERE session_id=? AND status!='UNANSWERED' ORDER BY position",(sid,))]
    correct=[q for q in qs if q['status']=='CORRECT']; times=[q['response_ms'] for q in correct if q['response_ms'] is not None]
    kinds=[]
    for kind in dict.fromkeys(q['kind'] for q in qs):
        kqs=[q for q in qs if q['kind']==kind]; kc=sum(1 for q in kqs if q['status']=='CORRECT')
        kinds.append({'kind':kind,'attempted':len(kqs),'correct':kc,'incorrect':len(kqs)-kc,'accuracy':round(100*kc/len(kqs),1) if kqs else 0})
    result={'id':s['id'],'date':s['started_at'],'activeMs':s['active_ms'],'attempted':len(qs),'correct':len(correct),'incorrect':len(qs)-len(correct),'accuracy':round(100*len(correct)/len(qs),1) if qs else 0,'medianMs':int(statistics.median(times)) if times else None,'categories':kinds,'questions':qs}
    c.close(); return result

init_db()
if __name__=='__main__': app.run(host='127.0.0.1',port=5050,debug=True)
