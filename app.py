from __future__ import annotations
import json
import random, sqlite3, statistics, time, copy, os, re
from pathlib import Path
from datetime import timedelta
from flask import Flask, request, jsonify, send_from_directory, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=Path(__file__).parent
DB=Path(os.environ.get('DB_PATH', str(ROOT/'calcul_mental.db')))
app=Flask(__name__, static_folder='static', static_url_path='')
_secret_key=os.environ.get('SECRET_KEY')
if not _secret_key:
    if os.environ.get('RENDER','').lower()=='true':
        raise RuntimeError("SECRET_KEY doit être défini sur Render")
    _secret_key='dev-only-change-me'
app.secret_key=_secret_key
app.config['PERMANENT_SESSION_LIFETIME']=timedelta(days=90)
app.config['SESSION_COOKIE_SAMESITE']='Lax'
app.config['SESSION_COOKIE_SECURE']=os.environ.get('RENDER','').lower()=='true'

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
    if 'first_wrong_answer' not in cols: c.execute('ALTER TABLE questions ADD COLUMN first_wrong_answer REAL')
    if 'last_answer' not in cols: c.execute('ALTER TABLE questions ADD COLUMN last_answer REAL')
    pcols={r['name'] for r in c.execute('PRAGMA table_info(profiles)')}
    if 'account_id' not in pcols: c.execute('ALTER TABLE profiles ADD COLUMN account_id INTEGER NOT NULL DEFAULT 1')
    if 'color' not in pcols: c.execute("ALTER TABLE profiles ADD COLUMN color TEXT NOT NULL DEFAULT '#8fdff7'")
    if 'school_class' not in pcols: c.execute("ALTER TABLE profiles ADD COLUMN school_class TEXT NOT NULL DEFAULT ''")
    if 'coins' not in pcols: c.execute('ALTER TABLE profiles ADD COLUMN coins INTEGER NOT NULL DEFAULT 0')
    if 'challenge_level' not in pcols: c.execute('ALTER TABLE profiles ADD COLUMN challenge_level INTEGER NOT NULL DEFAULT 1')
    if 'challenge_stars' not in pcols: c.execute('ALTER TABLE profiles ADD COLUMN challenge_stars INTEGER NOT NULL DEFAULT 0')
    if 'challenge_level_id' not in pcols: c.execute('ALTER TABLE profiles ADD COLUMN challenge_level_id INTEGER')
    # V99: l'ancien schéma imposait un nom de profil unique dans toute la base.
    # On migre vers une unicité par compte : deux comptes peuvent chacun avoir "Paul".
    profile_sql=c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='profiles'").fetchone()['sql']
    if 'name TEXT NOT NULL UNIQUE' in profile_sql:
        c.execute('ALTER TABLE profiles RENAME TO profiles_legacy_v99')
        c.execute('''CREATE TABLE profiles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            account_id INTEGER NOT NULL DEFAULT 1,
            color TEXT NOT NULL DEFAULT '#8fdff7',
            school_class TEXT NOT NULL DEFAULT '',
            coins INTEGER NOT NULL DEFAULT 0,
            challenge_level INTEGER NOT NULL DEFAULT 1,
            challenge_stars INTEGER NOT NULL DEFAULT 0,
            challenge_level_id INTEGER
        )''')
        c.execute('''INSERT INTO profiles(id,name,created_at,account_id,color,school_class,coins,challenge_level,challenge_stars,challenge_level_id)
                     SELECT id,name,created_at,account_id,color,school_class,coins,challenge_level,challenge_stars,challenge_level_id
                     FROM profiles_legacy_v99''')
        c.execute('DROP TABLE profiles_legacy_v99')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_account_name ON profiles(account_id,name COLLATE NOCASE)')
    scols={r['name'] for r in c.execute('PRAGMA table_info(sessions)')}
    if 'rewarded' not in scols: c.execute('ALTER TABLE sessions ADD COLUMN rewarded INTEGER NOT NULL DEFAULT 0')
    if 'mode' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'learning'")
    if 'challenge_class' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN challenge_class TEXT")
    if 'challenge_level' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN challenge_level INTEGER")
    if 'star_awarded' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN star_awarded INTEGER NOT NULL DEFAULT 0")
    if 'challenge_day' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN challenge_day TEXT")
    if 'daily_bonus_awarded' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN daily_bonus_awarded INTEGER NOT NULL DEFAULT 0")
    if 'challenge_level_id' not in scols: c.execute("ALTER TABLE sessions ADD COLUMN challenge_level_id INTEGER")
    c.executescript('''
    CREATE TABLE IF NOT EXISTS reward_progress(profile_id INTEGER PRIMARY KEY, current_card TEXT, revealed TEXT NOT NULL DEFAULT '[]', completed TEXT NOT NULL DEFAULT '[]', FOREIGN KEY(profile_id) REFERENCES profiles(id));
    CREATE TABLE IF NOT EXISTS challenge_levels(id INTEGER PRIMARY KEY AUTOINCREMENT, school_class TEXT NOT NULL, name TEXT NOT NULL, position INTEGER NOT NULL, data TEXT NOT NULL, UNIQUE(school_class, position));
    ''')
    c.commit(); c.close()

DEFAULT={
 'duration':300,'count':50,
 'categories':{
  'double':{'enabled':True,'pct':15,'min':1,'max':10,'display':'both'},
  'half':{'enabled':False,'pct':0,'tens':False},
  'addition':{'enabled':True,'pct':20,'aMin':1,'aMax':10,'bMin':1,'bMax':10,'maxResult':100,'withCarry':True},
  'subtraction':{'enabled':True,'pct':15,'aMin':1,'aMax':10,'bMin':1,'bMax':10,'nonNegative':True},
  'decimal':{'enabled':False,'pct':0,'min':0,'max':20,'decimals':1,'withCarry':True},
  'multiplication':{'enabled':True,'pct':15,'tables':[2,3],'factorMin':1,'factorMax':10},
  'division':{'enabled':True,'pct':10,'tables':[2,3,4],'quotientMin':1,'quotientMax':10},
  'complement10':{'enabled':True,'pct':10},
  'tens':{'enabled':True,'pct':15,'startMin':10,'startMax':99,'mode':'10','multiples':[10,20,30,40,50,60,70,80,90],'maxResult':100},
  'tens_sub':{'enabled':False,'pct':0,'startMin':20,'startMax':100,'mode':'10','multiples':[10,20,30,40,50,60,70,80,90],'nonNegative':True},
  'double_tens':{'enabled':False,'pct':0,'min':10,'max':100},
  'half_tens':{'enabled':False,'pct':0,'min':20,'max':100},
  'decimal_sub':{'enabled':False,'pct':0,'min':0,'max':20,'decimals':1,'withBorrow':True},
  'decimal_multiplication':{'enabled':False,'pct':0,'multipliers':[10,100,1000],'min':0.1,'max':20,'decimals':1},
  'decimal_division':{'enabled':False,'pct':0,'divisors':[10,100,1000],'min':1,'max':1000,'decimals':1}
 }}

# Défis centralisés : 5 paliers par classe.
# Les réglages sont volontairement côté serveur : aucun bouton de configuration
# n'est exposé à l'enfant dans le mode Défi.
def seed_challenge_cfg(school_class, level):
    school_class=(school_class or 'CP').upper()
    level=max(1,int(level or 1))
    level=max(1,min(5,level))
    cfg=copy.deepcopy(DEFAULT)
    cfg['duration']=300
    cfg['count']=50
    for v in cfg['categories'].values():
        v['enabled']=False; v['pct']=0

    def on(kind,pct,**kw):
        v=cfg['categories'][kind]; v.update(kw); v['enabled']=True; v['pct']=pct

    # Ces 25 templates constituent une première progression centrale facilement
    # ajustable ensuite sans modifier l'interface.
    if school_class=='CP':
        if level==1:
            on('addition',50,aMin=0,aMax=5,bMin=0,bMax=5,maxResult=10,withCarry=False)
            on('complement10',25); on('double',25,min=1,max=5,display='both')
        elif level==2:
            on('addition',45,aMin=0,aMax=10,bMin=0,bMax=10,maxResult=20,withCarry=False)
            on('subtraction',30,aMin=0,aMax=20,bMin=0,bMax=10,nonNegative=True)
            on('double',25,min=1,max=10,display='both')
        elif level==3:
            on('addition',40,aMin=0,aMax=20,bMin=0,bMax=10,maxResult=30,withCarry=True)
            on('subtraction',35,aMin=0,aMax=30,bMin=0,bMax=10,nonNegative=True)
            on('complement10',25)
        elif level==4:
            on('addition',40,aMin=0,aMax=30,bMin=0,bMax=20,maxResult=50,withCarry=True)
            on('subtraction',35,aMin=0,aMax=50,bMin=0,bMax=20,nonNegative=True)
            on('tens',25,startMin=10,startMax=39,mode='10',multiples=[10],maxResult=50)
        else:
            on('addition',40,aMin=0,aMax=50,bMin=0,bMax=30,maxResult=100,withCarry=True)
            on('subtraction',35,aMin=0,aMax=100,bMin=0,bMax=50,nonNegative=True)
            on('tens',25,startMin=10,startMax=89,mode='10',multiples=[10],maxResult=100)
    elif school_class=='CE1':
        if level==1:
            on('addition',30,aMin=1,aMax=30,bMin=1,bMax=20,maxResult=50,withCarry=True)
            on('subtraction',25,aMin=10,aMax=50,bMin=1,bMax=30,nonNegative=True)
            on('double',20,min=1,max=10,display='both'); on('complement10',10)
            on('tens',15,startMin=10,startMax=89,mode='10',multiples=[10],maxResult=100)
        elif level==2:
            on('addition',30,aMin=1,aMax=60,bMin=1,bMax=40,maxResult=100,withCarry=True)
            on('subtraction',25,aMin=10,aMax=100,bMin=1,bMax=60,nonNegative=True)
            on('double',15,min=1,max=20,display='both')
            on('tens',15,startMin=10,startMax=89,mode='10',multiples=[10],maxResult=100)
            on('multiplication',15,tables=[2,5,10],factorMin=1,factorMax=10)
        elif level==3:
            on('addition',25,aMin=10,aMax=90,bMin=1,bMax=90,maxResult=150,withCarry=True)
            on('subtraction',25,aMin=20,aMax=150,bMin=1,bMax=100,nonNegative=True)
            on('double',15,min=5,max=50,display='both')
            on('multiplication',20,tables=[2,3,4,5,10],factorMin=1,factorMax=10)
            on('division',15,tables=[2,5,10],quotientMin=1,quotientMax=10)
        elif level==4:
            on('addition',25,aMin=20,aMax=150,bMin=10,bMax=100,maxResult=250,withCarry=True)
            on('subtraction',25,aMin=30,aMax=250,bMin=1,bMax=150,nonNegative=True)
            on('multiplication',25,tables=[2,3,4,5,10],factorMin=1,factorMax=10)
            on('division',15,tables=[2,3,4,5,10],quotientMin=1,quotientMax=10)
            on('tens_sub',10,startMin=20,startMax=200,mode='10',multiples=[10],nonNegative=True)
        else:
            on('addition',25,aMin=20,aMax=250,bMin=10,bMax=200,maxResult=400,withCarry=True)
            on('subtraction',25,aMin=50,aMax=400,bMin=1,bMax=250,nonNegative=True)
            on('multiplication',25,tables=[2,3,4,5,6,10],factorMin=1,factorMax=10)
            on('division',20,tables=[2,3,4,5,10],quotientMin=1,quotientMax=10)
            on('double',5,min=10,max=100,display='both')
    elif school_class=='CE2':
        tables_by_level=[[2,3,4,5,10],[2,3,4,5,6,10],[2,3,4,5,6,7,10],[2,3,4,5,6,7,8,9,10],[2,3,4,5,6,7,8,9,10]]
        lim=[300,500,800,1000,1500][level-1]
        on('addition',25,aMin=20,aMax=lim//2,bMin=10,bMax=lim//2,maxResult=lim,withCarry=True)
        on('subtraction',25,aMin=50,aMax=lim,bMin=1,bMax=lim//2,nonNegative=True)
        on('multiplication',30,tables=tables_by_level[level-1],factorMin=1,factorMax=10)
        on('division',20,tables=tables_by_level[level-1],quotientMin=1,quotientMax=10)
    elif school_class=='CM1':
        lim=[1000,2000,5000,10000,20000][level-1]
        on('addition',20,aMin=100,aMax=lim//2,bMin=10,bMax=lim//2,maxResult=lim,withCarry=True)
        on('subtraction',20,aMin=100,aMax=lim,bMin=1,bMax=lim//2,nonNegative=True)
        on('multiplication',25,tables=[2,3,4,5,6,7,8,9,10],factorMin=1,factorMax=10)
        on('division',20,tables=[2,3,4,5,6,7,8,9,10],quotientMin=1,quotientMax=12)
        on('decimal',15,min=0,max=20*(level+1),decimals=1,withCarry=True)
    else: # CM2
        lim=[5000,10000,20000,50000,100000][level-1]
        on('addition',15,aMin=100,aMax=lim//2,bMin=10,bMax=lim//2,maxResult=lim,withCarry=True)
        on('subtraction',15,aMin=100,aMax=lim,bMin=1,bMax=lim//2,nonNegative=True)
        on('multiplication',20,tables=[2,3,4,5,6,7,8,9,10],factorMin=2,factorMax=12)
        on('division',15,tables=[2,3,4,5,6,7,8,9,10],quotientMin=2,quotientMax=15)
        on('decimal',15,min=0,max=100,decimals=1 if level<4 else 2,withCarry=True)
        on('decimal_sub',10,min=0,max=100,decimals=1 if level<4 else 2,withBorrow=True)
        on('decimal_multiplication',5,multipliers=[10,100,1000],min=0.1,max=50,decimals=1)
        on('decimal_division',5,divisors=[10,100,1000],min=1,max=1000,decimals=1)
    return cfg

def merged_cfg(saved):
    cfg=copy.deepcopy(DEFAULT)
    cfg.update({k:v for k,v in (saved or {}).items() if k!='categories'})
    for kind, values in (saved or {}).get('categories',{}).items():
        if kind in cfg['categories'] and isinstance(values,dict): cfg['categories'][kind].update(values)
        else: cfg['categories'][kind]=values
    return cfg

def get_cfg(pid):
    c=db(); r=c.execute('SELECT data FROM configs WHERE profile_id=?',(pid,)).fetchone(); c.close()
    return merged_cfg(json.loads(r['data'])) if r else copy.deepcopy(DEFAULT)

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
    if kind=='half':
        # Moitiés simples : 2, 4, 6, 8, 10. L'option « Dizaines » ajoute 20, 30, ... 100.
        choices=[2,4,6,8,10]
        if cfg.get('tens',False): choices += [20,30,40,50,60,70,80,90,100]
        n=random.choice(choices)
        return {'n':n}, f'Moitié de {n} = __', n//2
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
    if kind=='decimal_multiplication':
        m=random.choice(cfg.get('multipliers',[10,100,1000])); dec=max(1,min(2,int(cfg.get('decimals',1))))
        scale=10**dec; lo=max(1,int(round(float(cfg.get('min',0.1))*scale))); hi=max(lo,int(round(float(cfg.get('max',20))*scale)))
        ai=random.randint(lo,hi); x=ai/scale; expected=x*m
        fmt=lambda v: (f'{v:.{dec}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'a':x,'b':m},f'{fmt(x)} × {m} = __',expected
    if kind=='decimal_division':
        d=random.choice(cfg.get('divisors',[10,100,1000])); dec=max(0,min(2,int(cfg.get('decimals',1))))
        scale=10**dec; lo=max(1,int(round(float(cfg.get('min',1))*scale))); hi=max(lo,int(round(float(cfg.get('max',1000))*scale)))
        ai=random.randint(lo,hi); x=ai/scale; expected=x/d
        fmt=lambda v: (f'{v:.{dec}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'dividend':x,'divisor':d},f'{fmt(x)} : {d} = __',expected
    if kind=='complement10':
        a=random.randint(1,9); return {'a':a},f'{a} + __ = 10',10-a
    if kind=='tens':
        for _ in range(100):
            a=random.randint(cfg['startMin'],cfg['startMax']); choices=[10] if cfg.get('mode')=='10' else cfg.get('multiples',[10])
            b=random.choice(choices)
            if not cfg.get('maxResult') or a+b<=cfg['maxResult']: break
        return {'a':a,'b':b},f'{a} + {b} = __',a+b
    if kind=='tens_sub':
        choices=[10] if cfg.get('mode')=='10' else cfg.get('multiples',[10])
        candidates=[(x,y) for x in range(int(cfg['startMin']),int(cfg['startMax'])+1) for y in choices if (not cfg.get('nonNegative',True) or x>=y)]
        if not candidates: raise ValueError("Aucune soustraction de dizaines possible avec ces réglages")
        x,y=random.choice(candidates)
        return {'a':x,'b':y},f'{x} − {y} = __',x-y
    if kind=='double_tens':
        lo=max(10,int(cfg.get('min',10))); hi=max(lo,int(cfg.get('max',100)))
        choices=[n for n in range(lo,hi+1) if n%10==0]
        if not choices: raise ValueError("Aucune dizaine possible avec ces réglages")
        n=random.choice(choices)
        return {'n':n},f'Double de {n} = __',n*2
    if kind=='half_tens':
        lo=max(20,int(cfg.get('min',20))); hi=max(lo,int(cfg.get('max',100)))
        choices=[n for n in range(lo,hi+1) if n%20==0]
        if not choices: raise ValueError("Aucune dizaine avec une moitié entière possible avec ces réglages")
        n=random.choice(choices)
        return {'n':n},f'Moitié de {n} = __',n//2
    if kind=='decimal_sub':
        decimals=max(1,min(2,int(cfg.get('decimals',1)))); scale=10**decimals
        lo=int(round(float(cfg.get('min',0))*scale)); hi=int(round(float(cfg.get('max',20))*scale))
        if hi<lo: lo,hi=hi,lo
        def no_borrow_scaled(x,y):
            while x or y:
                if (x % 10) < (y % 10): return False
                x//=10; y//=10
            return True
        candidates=[]
        for _ in range(1600):
            x=random.randint(lo,hi); y=random.randint(lo,x)
            if cfg.get('withBorrow',True) or no_borrow_scaled(x,y):
                candidates.append((x,y))
                if len(candidates)>=80: break
        if not candidates: raise ValueError("Aucune soustraction de décimaux possible avec ces réglages")
        x,y=random.choice(candidates); xv=x/scale; yv=y/scale
        fmt=lambda v: (f'{v:.{decimals}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'a':xv,'b':yv,'op':'subtraction','decimals':decimals},f'{fmt(xv)} − {fmt(yv)} = __',(x-y)/scale

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
    c.close(); session.clear(); session['account_id']=aid; session.permanent=True; return {'ok':True,'username':username}

@app.post('/auth/login-form')
def auth_login_form():
    username=(request.form.get('username') or '').strip()
    password=str(request.form.get('password') or '')
    c=db(); acc=c.execute('SELECT id,username,password_hash FROM accounts WHERE username=? COLLATE NOCASE',(username,)).fetchone(); c.close()
    if not acc or not check_password_hash(acc['password_hash'],password):
        return redirect('/?login=error')
    session.clear(); session['account_id']=acc['id']; session.permanent=True
    return redirect('/?login=ok')

@app.post('/api/auth/login')
def auth_login():
    data=request.json or {}; username=(data.get('username') or '').strip(); password=str(data.get('password') or '')
    c=db(); a=c.execute('SELECT id,username,password_hash FROM accounts WHERE username=? COLLATE NOCASE',(username,)).fetchone(); c.close()
    if not a or not check_password_hash(a['password_hash'],password): return {'error':'Identifiant ou mot de passe incorrect.'},401
    session.clear(); session['account_id']=a['id']; session.permanent=True; return {'ok':True,'username':a['username']}
@app.post('/api/auth/logout')
def auth_logout(): session.clear(); return {'ok':True}
def admin_unlocked():
    admin_password=os.environ.get('ADMIN_PASSWORD')
    return authenticated() and (not admin_password or session.get('admin_unlocked') is True)

def require_admin():
    if not authenticated(): return ({'error':'Connexion requise'},401)
    if not admin_unlocked(): return ({'error':'Accès administrateur requis'},403)
    return None

@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if not authenticated(): return redirect('/')
    admin_password=os.environ.get('ADMIN_PASSWORD')
    if not admin_password:
        session['admin_unlocked']=True
        return redirect('/admin')
    error=''
    if request.method=='POST':
        supplied=str(request.form.get('password') or '')
        if supplied==admin_password:
            session['admin_unlocked']=True
            return redirect('/admin')
        error='<p style="color:#b42318;font-weight:700">Mot de passe incorrect.</p>'
    return f'''<!doctype html><html lang="fr"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Administration</title><body style="font-family:system-ui;background:#f4f8fb;margin:0;display:grid;place-items:center;min-height:100vh">
    <form method="post" style="background:white;padding:28px;border-radius:18px;box-shadow:0 8px 30px #0002;min-width:min(320px,80vw)">
    <h1 style="font-size:24px">Administration</h1>{error}<input name="password" type="password" autocomplete="current-password" placeholder="Mot de passe admin"
    style="box-sizing:border-box;width:100%;padding:12px;border:1px solid #ccd5df;border-radius:10px"><button style="width:100%;margin-top:14px;padding:12px;border:0;border-radius:10px;background:#269ee8;color:white;font-weight:800">Entrer</button></form></body></html>'''

@app.get('/admin')
def admin_page():
    if not authenticated(): return redirect('/')
    if not admin_unlocked(): return redirect('/admin/login')
    return send_from_directory(ROOT/'static','admin.html')


CLASSES=('CP','CE1','CE2','CM1','CM2')

def challenge_levels_for(c, school):
    return c.execute('SELECT id,name,position,data FROM challenge_levels WHERE school_class=? ORDER BY position',(school,)).fetchall()

def resolve_profile_level(c, profile):
    school=(profile['school_class'] or 'CP').upper()
    levels=challenge_levels_for(c,school)
    if not levels:
        return school,None,1,'Niveau 1'
    keys=profile.keys()
    level_id=profile['challenge_level_id'] if 'challenge_level_id' in keys else None
    row=next((x for x in levels if x['id']==level_id),None)
    if row is None:
        legacy=max(1,int(profile['challenge_level'] or 1)) if 'challenge_level' in keys else 1
        row=levels[min(legacy-1,len(levels)-1)]
    return school,row,row['position'],row['name']

def sync_profile_level(c, pid):
    p=c.execute('SELECT id,school_class,challenge_level,challenge_level_id FROM profiles WHERE id=?',(pid,)).fetchone()
    if not p: return None
    school,row,pos,name=resolve_profile_level(c,p)
    if row and (p['challenge_level_id']!=row['id'] or p['challenge_level']!=pos):
        c.execute('UPDATE profiles SET challenge_level_id=?,challenge_level=? WHERE id=?',(row['id'],pos,pid))
    return row

def validate_cfg_data(data):
    data=merged_cfg(data or {})
    data['duration']=max(60,min(3600,int(data.get('duration',300))))
    data['count']=max(1,min(500,int(data.get('count',50))))
    cats=data['categories']
    total=sum(int(v.get('pct',0) or 0) for v in cats.values() if v.get('enabled'))
    if total!=100: raise ValueError(f'Le total doit être 100 % (actuellement {total} %).')
    if cats.get('multiplication',{}).get('enabled') and not cats['multiplication'].get('tables'):
        raise ValueError('Choisis au moins une table de multiplication.')
    if cats.get('division',{}).get('enabled') and not cats['division'].get('tables'):
        raise ValueError('Choisis au moins une table de division.')
    if cats.get('decimal_multiplication',{}).get('enabled') and not cats['decimal_multiplication'].get('multipliers'):
        raise ValueError('Choisis au moins un multiplicateur décimal.')
    if cats.get('decimal_division',{}).get('enabled') and not cats['decimal_division'].get('divisors'):
        raise ValueError('Choisis au moins un diviseur décimal.')
    return data

@app.get('/api/admin/levels')
def admin_levels():
    if (e:=require_admin()): return e
    c=db(); rows=[dict(r) for r in c.execute('SELECT id,school_class,name,position FROM challenge_levels ORDER BY CASE school_class WHEN "CP" THEN 1 WHEN "CE1" THEN 2 WHEN "CE2" THEN 3 WHEN "CM1" THEN 4 ELSE 5 END,position')]; c.close(); return jsonify(rows)
@app.get('/api/admin/levels/<int:lid>')
def admin_level(lid):
    if (e:=require_admin()): return e
    c=db(); r=c.execute('SELECT * FROM challenge_levels WHERE id=?',(lid,)).fetchone(); c.close()
    if not r:return {'error':'Niveau introuvable'},404
    return {'id':r['id'],'school_class':r['school_class'],'name':r['name'],'position':r['position'],'config':merged_cfg(json.loads(r['data']))}
@app.post('/api/admin/levels')
def admin_level_create():
    if (e:=require_admin()): return e
    d=request.json or {}; school=(d.get('school_class') or '').upper(); name=(d.get('name') or '').strip(); source=d.get('copy_from')
    if school not in CLASSES or not name:return {'error':'Classe et nom requis.'},400
    c=db(); pos=c.execute('SELECT COALESCE(MAX(position),0)+1 n FROM challenge_levels WHERE school_class=?',(school,)).fetchone()['n']
    cfg=copy.deepcopy(DEFAULT)
    for v in cfg['categories'].values():v['enabled']=False;v['pct']=0
    if source:
        r=c.execute('SELECT data FROM challenge_levels WHERE id=?',(int(source),)).fetchone()
        if r:cfg=merged_cfg(json.loads(r['data']))
    cur=c.execute('INSERT INTO challenge_levels(school_class,name,position,data) VALUES(?,?,?,?)',(school,name,pos,json.dumps(cfg))); c.commit(); lid=cur.lastrowid;c.close();return {'ok':True,'id':lid}
@app.put('/api/admin/levels/<int:lid>')
def admin_level_save(lid):
    if (e:=require_admin()): return e
    d=request.json or {}; c=db(); old=c.execute('SELECT id FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not old:c.close();return {'error':'Niveau introuvable'},404
    try: cfg=validate_cfg_data(d.get('config',{}))
    except ValueError as ex:c.close();return {'error':str(ex)},400
    name=(d.get('name') or '').strip() or 'Niveau'; c.execute('UPDATE challenge_levels SET name=?,data=? WHERE id=?',(name,json.dumps(cfg),lid));c.commit();c.close();return {'ok':True}
@app.post('/api/admin/levels/<int:lid>/move')
def admin_level_move(lid):
    if (e:=require_admin()): return e
    direction=(request.json or {}).get('direction'); c=db(); r=c.execute('SELECT school_class,position FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not r:c.close();return {'error':'Niveau introuvable'},404
    target=r['position']+(-1 if direction=='up' else 1); other=c.execute('SELECT id FROM challenge_levels WHERE school_class=? AND position=?',(r['school_class'],target)).fetchone()
    if other:
        c.execute('UPDATE challenge_levels SET position=-1 WHERE id=?',(lid,));c.execute('UPDATE challenge_levels SET position=? WHERE id=?',(r['position'],other['id']));c.execute('UPDATE challenge_levels SET position=? WHERE id=?',(target,lid));c.commit()
    c.close();return {'ok':True}
@app.delete('/api/admin/levels/<int:lid>')
def admin_level_delete(lid):
    if (e:=require_admin()): return e
    c=db(); r=c.execute('SELECT school_class,position FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not r:c.close();return {'error':'Niveau introuvable'},404
    c.execute('DELETE FROM challenge_levels WHERE id=?',(lid,));c.execute('UPDATE challenge_levels SET position=position-1 WHERE school_class=? AND position>?',(r['school_class'],r['position']));c.commit();c.close();return {'ok':True}

@app.get('/api/profiles')
def profiles():
    if (e:=require_auth()): return e
    c=db()
    pids=[r['id'] for r in c.execute('SELECT id FROM profiles WHERE account_id=?',(current_account_id(),)).fetchall()]
    for pid in pids: sync_profile_level(c,pid)
    c.commit()
    rows=[dict(x) for x in c.execute('SELECT id,name,color,school_class,coins,challenge_level,challenge_level_id,challenge_stars,created_at FROM profiles WHERE account_id=? ORDER BY name',(current_account_id(),))]
    c.close(); return jsonify(rows)
@app.post('/api/profiles')
def create_profile():
    if (e:=require_auth()): return e
    data=request.json or {}
    name=(data.get('name') or '').strip()
    color=(data.get('color') or '#8fdff7').strip()
    school_class=(data.get('school_class') or '').strip()
    if not name: return {'error':'Nom requis'},400
    if school_class not in ('CP','CE1','CE2','CM1','CM2'): return {'error':'Classe requise'},400
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}',color): color='#8fdff7'
    c=db()
    if c.execute('SELECT 1 FROM profiles WHERE account_id=? AND name=? COLLATE NOCASE',(current_account_id(),name)).fetchone():
        c.close(); return {'error':'Ce profil existe déjà'},409
    try:
        cur=c.execute('INSERT INTO profiles(name,account_id,color,school_class) VALUES(?,?,?,?)',(name,current_account_id(),color,school_class)); pid=cur.lastrowid; c.execute('INSERT INTO configs(profile_id,data) VALUES(?,?)',(pid,json.dumps(DEFAULT))); c.commit(); c.close(); return {'id':pid,'name':name,'color':color,'school_class':school_class}
    except sqlite3.IntegrityError: return {'error':'Ce profil existe déjà'},409
@app.put('/api/profiles/<int:pid>')
def update_profile(pid):
    if (e:=require_auth()): return e
    data=request.json or {}
    name=(data.get('name') or '').strip()
    color=(data.get('color') or '#8fdff7').strip()
    school_class=(data.get('school_class') or '').strip()
    if not name: return {'error':'Nom requis'},400
    if school_class not in ('CP','CE1','CE2','CM1','CM2'): return {'error':'Classe requise'},400
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}',color): return {'error':'Couleur invalide'},400
    c=db()
    if not c.execute('SELECT id FROM profiles WHERE id=? AND account_id=?',(pid,current_account_id())).fetchone():
        c.close(); return {'error':'Profil introuvable'},404
    try:
        old_class=c.execute('SELECT school_class FROM profiles WHERE id=?',(pid,)).fetchone()['school_class']
        if old_class != school_class:
            clear_challenge_stats(c,pid)
            first=c.execute('SELECT id FROM challenge_levels WHERE school_class=? ORDER BY position LIMIT 1',(school_class,)).fetchone(); first_id=first['id'] if first else None; c.execute('UPDATE profiles SET name=?,color=?,school_class=?,challenge_level=1,challenge_level_id=?,challenge_stars=0 WHERE id=?',(name,color,school_class,first_id,pid))
        else:
            c.execute('UPDATE profiles SET name=?,color=?,school_class=? WHERE id=?',(name,color,school_class,pid))
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); return {'error':'Ce profil existe déjà'},409
    c.close(); return {'id':pid,'name':name,'color':color,'school_class':school_class}

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
    c.execute('DELETE FROM reward_progress WHERE profile_id=?',(pid,))
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
    try: data=validate_cfg_data(request.json or {})
    except (ValueError,TypeError) as ex: return {'error':str(ex)},400
    c=db(); c.execute('INSERT INTO configs(profile_id,data) VALUES(?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data',(pid,json.dumps(data))); c.commit(); c.close(); return {'ok':True}
@app.get('/api/challenge/<int:pid>')
def challenge_status(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    day=(request.args.get('date') or '')[:10]
    c=db(); p=c.execute('SELECT school_class,challenge_level,challenge_level_id,challenge_stars FROM profiles WHERE id=?',(pid,)).fetchone()
    school,row,current,level_name=resolve_profile_level(c,p); levels=challenge_levels_for(c,school); max_level=max(1,len(levels))
    # Répare aussi les profils déjà arrivés à 3 étoiles avant l'avancement automatique.
    if row and p['challenge_stars']>=3:
        next_row=next((x for x in levels if x['position']==current+1),None)
        if next_row:
            c.execute('UPDATE profiles SET challenge_level=?,challenge_level_id=?,challenge_stars=0 WHERE id=?',
                      (next_row['position'],next_row['id'],pid)); c.commit()
            row=next_row; current=next_row['position']; level_name=next_row['name']
            p=c.execute('SELECT school_class,challenge_level,challenge_level_id,challenge_stars FROM profiles WHERE id=?',(pid,)).fetchone()
    if row and (p['challenge_level_id']!=row['id'] or p['challenge_level']!=current):
        c.execute('UPDATE profiles SET challenge_level_id=?,challenge_level=? WHERE id=?',(row['id'],current,pid)); c.commit()
    done_today=False
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):
        done_today=bool(c.execute("SELECT 1 FROM sessions WHERE profile_id=? AND mode='challenge' AND rewarded=1 AND challenge_day=? LIMIT 1",(pid,day)).fetchone())
    c.close()
    return {'schoolClass':school,'level':current,'levelName':level_name,'stars':p['challenge_stars'],'maxLevel':max_level,'threshold':46,'doneToday':done_today,'levels':[{'id':x['id'],'name':x['name'],'position':x['position']} for x in levels]}

def clear_challenge_stats(c,pid):
    # Les questions n'ont pas de cascade FK garantie dans les anciennes BDD :
    # supprimer explicitement avant les séances.
    c.execute("DELETE FROM questions WHERE session_id IN (SELECT id FROM sessions WHERE profile_id=? AND mode='challenge')",(pid,))
    c.execute("DELETE FROM sessions WHERE profile_id=? AND mode='challenge'",(pid,))

@app.post('/api/challenge/<int:pid>/promote')
def challenge_promote(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    c=db(); p=c.execute('SELECT challenge_level,challenge_stars FROM profiles WHERE id=?',(pid,)).fetchone()
    if p['challenge_stars']<3:
        c.close(); return {'error':'Il faut 3 étoiles pour passer au niveau suivant.'},400
    school=c.execute('SELECT school_class FROM profiles WHERE id=?',(pid,)).fetchone()['school_class'] or 'CP'
    max_level=c.execute('SELECT COUNT(*) n FROM challenge_levels WHERE school_class=?',(school,)).fetchone()['n'] or 1
    if p['challenge_level']>=max_level:
        c.close(); return {'error':'C’est déjà le dernier niveau de cette classe.'},400
    level=p['challenge_level']+1
    next_row=c.execute('SELECT id FROM challenge_levels WHERE school_class=? AND position=?',(school,level)).fetchone()
    next_id=next_row['id'] if next_row else None
    clear_challenge_stats(c,pid)
    c.execute('UPDATE profiles SET challenge_level=?,challenge_level_id=?,challenge_stars=0 WHERE id=?',(level,next_id,pid))
    c.commit(); c.close()
    return {'ok':True,'level':level,'stars':0}

@app.post('/api/session/start/<int:pid>')
def start(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    mode=(request.args.get('mode') or 'learning').lower()
    if mode not in ('learning','challenge'): mode='learning'
    challenge_class=None; challenge_level=None; challenge_level_id=None
    if mode=='challenge':
        c0=db(); p0=c0.execute('SELECT school_class,challenge_level,challenge_level_id FROM profiles WHERE id=?',(pid,)).fetchone()
        challenge_class,row,challenge_level,_=resolve_profile_level(c0,p0); challenge_level_id=row['id'] if row else None
        if row:
            c0.execute('UPDATE profiles SET challenge_level=?,challenge_level_id=? WHERE id=?',(challenge_level,challenge_level_id,pid)); c0.commit()
            cfg=merged_cfg(json.loads(row['data']))
        else:
            cfg=copy.deepcopy(DEFAULT)
        c0.close()
    else:
        cfg=get_cfg(pid)
    count=cfg.get('count',50)
    active_kinds={k for k,v in cfg['categories'].items() if v.get('enabled') and v.get('pct',0)>0}
    # Un Défi doit rester standardisé : aucune reprise d'erreur d'une séance précédente.
    retries=[] if mode=='challenge' else [r for r in previous_errors(pid) if r['kind'] in active_kinds][:count]
    remaining=count-len(retries); alloc=allocate(remaining,cfg['categories']) if remaining else {}
    # Une même opération ne doit apparaître qu'une seule fois dans une séance.
    # La clé ignore le mode d'affichage des doubles : « Double de 8 » et « 8 + 8 »
    # représentent le même fait numérique et ne peuvent donc pas coexister.
    def operation_key(kind, payload):
        if kind in ('double','half'): return (kind, payload.get('n'))
        if kind in ('addition', 'subtraction', 'multiplication', 'decimal_multiplication', 'tens', 'tens_sub'): return (kind, payload.get('a'), payload.get('b'))
        if kind in ('decimal','decimal_sub'): return (kind, payload.get('a'), payload.get('b'), payload.get('op'))
        if kind in ('division','decimal_division'): return (kind, payload.get('dividend'), payload.get('divisor'))
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
    c=db(); cur=c.execute('INSERT INTO sessions(profile_id,mode,challenge_class,challenge_level,challenge_level_id) VALUES(?,?,?,?,?)',(pid,mode,challenge_class,challenge_level,challenge_level_id)); sid=cur.lastrowid
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
    oldq=c.execute('SELECT expected,given_answer,attempts,had_error,first_wrong_answer FROM questions WHERE id=? AND session_id=?',(qid,sid)).fetchone()
    attempts=(oldq['attempts'] or 0)+1
    ok=abs(given-float(oldq['expected'])) < 1e-9; had_error=bool(oldq['had_error']) or not ok
    # given_answer devient volontairement la PREMIÈRE réponse saisie et n'est plus jamais écrasée.
    first_answer=oldq['given_answer'] if oldq['given_answer'] is not None else given
    first_wrong=oldq['first_wrong_answer']
    if not ok and first_wrong is None: first_wrong=given
    # Une question reste statistiquement en erreur dès le premier essai faux, même si elle est corrigée ensuite.
    status=('INCORRECT' if had_error else 'CORRECT') if ok or attempts>=3 else 'UNANSWERED'
    c.execute('UPDATE questions SET given_answer=?,last_answer=?,first_wrong_answer=?,status=?,response_ms=?,attempts=?,had_error=? WHERE id=?',(first_answer,given,first_wrong,status,ms,attempts,1 if had_error else 0,qid)); c.commit(); c.close(); return {'correct':ok,'expected':oldq['expected'],'attempts':attempts,'remaining':max(0,3-attempts)}
@app.delete('/api/session/<int:sid>')
def cancel_session(sid):
    if (e:=require_auth()): return e
    c0=db(); own=c0.execute('SELECT 1 FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone(); c0.close()
    if not own: return {'error':'Séance inconnue'},404
    c=db(); c.execute('DELETE FROM questions WHERE session_id=?',(sid,)); c.execute('DELETE FROM sessions WHERE id=?',(sid,)); c.commit(); c.close(); return {'ok':True}

@app.post('/api/session/<int:sid>/finish')
def finish(sid):
    if (e:=require_auth()): return e
    data=request.json or {}; ms=max(0,int(data.get('activeMs',0)))
    local_day=str(data.get('localDate',''))[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',local_day): local_day=None
    c=db(); s=c.execute('SELECT s.id,s.profile_id,s.rewarded,s.mode,s.challenge_class,s.challenge_level,s.challenge_level_id,s.star_awarded,s.daily_bonus_awarded FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone()
    if not s: c.close(); return {'error':'Séance inconnue'},404
    earned=0
    if not s['rewarded']:
        earned=c.execute("SELECT COUNT(*) n FROM questions WHERE session_id=? AND status='CORRECT'",(sid,)).fetchone()['n']
        c.execute('UPDATE profiles SET coins=coins+? WHERE id=?',(earned,s['profile_id']))
        c.execute('UPDATE sessions SET active_ms=?,rewarded=1 WHERE id=?',(ms,sid))
    else:
        c.execute('UPDATE sessions SET active_ms=? WHERE id=?',(ms,sid))
    daily_bonus=0
    star_awarded=False
    if s['mode']=='challenge':
        # finish() n'est jamais appelé par STOP : seuls 50 calculs traités ou le timer écoulé valident le défi.
        already_done=bool(local_day and c.execute("SELECT 1 FROM sessions WHERE profile_id=? AND mode='challenge' AND rewarded=1 AND challenge_day=? AND id<>? LIMIT 1",(s['profile_id'],local_day,sid)).fetchone())
        c.execute('UPDATE sessions SET challenge_day=? WHERE id=?',(local_day,sid))
        if local_day and not already_done and not s['daily_bonus_awarded']:
            daily_bonus=10
            c.execute('UPDATE profiles SET coins=coins+10 WHERE id=?',(s['profile_id'],))
            c.execute('UPDATE sessions SET daily_bonus_awarded=1 WHERE id=?',(sid,))
    if s['mode']=='challenge' and not s['star_awarded']:
        correct=c.execute("SELECT COUNT(*) n FROM questions WHERE session_id=? AND status='CORRECT'",(sid,)).fetchone()['n']
        p=c.execute('SELECT school_class,challenge_level,challenge_level_id,challenge_stars FROM profiles WHERE id=?',(s['profile_id'],)).fetchone()
        # L'étoile ne compte que si le profil est toujours sur le même palier que le défi joué.
        same_level=(p['challenge_level_id']==s['challenge_level_id']) if s['challenge_level_id'] is not None else (p['challenge_level']==s['challenge_level']);
        if correct>45 and p['school_class']==s['challenge_class'] and same_level and p['challenge_stars']<3:
            new_stars=p['challenge_stars']+1
            c.execute('UPDATE profiles SET challenge_stars=? WHERE id=?',(new_stars,s['profile_id']))
            star_awarded=True
            # La 3e étoile valide immédiatement le niveau et débloque le suivant.
            if new_stars>=3:
                levels=challenge_levels_for(c,p['school_class'])
                next_row=next((x for x in levels if x['position']==p['challenge_level']+1),None)
                if next_row:
                    c.execute('UPDATE profiles SET challenge_level=?,challenge_level_id=?,challenge_stars=0 WHERE id=?',
                              (next_row['position'],next_row['id'],s['profile_id']))
        c.execute('UPDATE sessions SET star_awarded=1 WHERE id=?',(sid,))
    pstate=c.execute('SELECT coins,challenge_level,challenge_level_id,challenge_stars,school_class FROM profiles WHERE id=?',(s['profile_id'],)).fetchone()
    balance=pstate['coins']
    c.commit(); c.close(); return {'ok':True,'coinsEarned':earned,'dailyBonus':daily_bonus,'balance':balance,'starAwarded':star_awarded,'challenge':{'schoolClass':pstate['school_class'],'level':pstate['challenge_level'],'stars':pstate['challenge_stars']}}

@app.get('/api/rewards/<int:pid>')
def rewards(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    c=db(); p=c.execute('SELECT coins FROM profiles WHERE id=?',(pid,)).fetchone(); r=c.execute('SELECT current_card,revealed,completed FROM reward_progress WHERE profile_id=?',(pid,)).fetchone(); c.close()
    if r: state={'currentCard':r['current_card'],'revealed':json.loads(r['revealed'] or '[]'),'completed':json.loads(r['completed'] or '[]')}
    else: state={'currentCard':None,'revealed':[],'completed':[]}
    return {'coins':p['coins'],'cards':[{'id': 'robot-1', 'type': 'robot', 'label': 'Bolt', 'image': '/rewards/robot-1.jpg'},{'id': 'robot-2', 'type': 'robot', 'label': 'Rex', 'image': '/rewards/robot-2.jpg'},{'id': 'robot-3', 'type': 'robot', 'label': 'Orion', 'image': '/rewards/robot-3.jpg'},{'id': 'robot-4', 'type': 'robot', 'label': 'Z3RO', 'image': '/rewards/robot-4.jpg'},{'id': 'robot-5', 'type': 'robot', 'label': 'Pixel', 'image': '/rewards/robot-5.jpg'},{'id': 'robot-6', 'type': 'robot', 'label': 'Atlas', 'image': '/rewards/robot-6.jpg'},{'id': 'robot-7', 'type': 'robot', 'label': 'Moka', 'image': '/rewards/robot-7.jpg'},{'id': 'robot-8', 'type': 'robot', 'label': 'Teko', 'image': '/rewards/robot-8.jpg'},{'id': 'robot-9', 'type': 'robot', 'label': 'K-7', 'image': '/rewards/robot-9.jpg'},{'id': 'robot-10', 'type': 'robot', 'label': 'Orbi', 'image': '/rewards/robot-10.jpg'},{'id': 'fairy-1', 'type': 'fairy', 'label': 'Lunéa', 'image': '/rewards/fairy-1.jpg'},{'id': 'fairy-2', 'type': 'fairy', 'label': 'Églantine', 'image': '/rewards/fairy-2.jpg'},{'id': 'fairy-3', 'type': 'fairy', 'label': 'Nyméa', 'image': '/rewards/fairy-3.jpg'},{'id': 'fairy-4', 'type': 'fairy', 'label': 'Aélia', 'image': '/rewards/fairy-4.jpg'},{'id': 'fairy-5', 'type': 'fairy', 'label': 'Sélène', 'image': '/rewards/fairy-5.jpg'},{'id': 'fairy-6', 'type': 'fairy', 'label': 'Rosélia', 'image': '/rewards/fairy-6.jpg'},{'id': 'fairy-7', 'type': 'fairy', 'label': 'Feuille', 'image': '/rewards/fairy-7.jpg'},{'id': 'fairy-8', 'type': 'fairy', 'label': 'Maréa', 'image': '/rewards/fairy-8.jpg'},{'id': 'fairy-9', 'type': 'fairy', 'label': 'Étoile', 'image': '/rewards/fairy-9.jpg'},{'id': 'fairy-10', 'type': 'fairy', 'label': 'Violette', 'image': '/rewards/fairy-10.jpg'},{'id': 'dinosaur-1', 'type': 'dinosaur', 'label': 'Tyrannosaure', 'image': '/rewards/dinosaur-1.jpg'},{'id': 'dinosaur-2', 'type': 'dinosaur', 'label': 'Tricératops', 'image': '/rewards/dinosaur-2.jpg'},{'id': 'dinosaur-3', 'type': 'dinosaur', 'label': 'Vélociraptor', 'image': '/rewards/dinosaur-3.jpg'},{'id': 'dinosaur-4', 'type': 'dinosaur', 'label': 'Diplodocus', 'image': '/rewards/dinosaur-4.jpg'},{'id': 'dinosaur-5', 'type': 'dinosaur', 'label': 'Stégosaure', 'image': '/rewards/dinosaur-5.jpg'},{'id': 'dinosaur-6', 'type': 'dinosaur', 'label': 'Ankylosaure', 'image': '/rewards/dinosaur-6.jpg'},{'id': 'dinosaur-7', 'type': 'dinosaur', 'label': 'Spinosaurus', 'image': '/rewards/dinosaur-7.jpg'},{'id': 'dinosaur-8', 'type': 'dinosaur', 'label': 'Parasaurolophus', 'image': '/rewards/dinosaur-8.jpg'},{'id': 'dinosaur-9', 'type': 'dinosaur', 'label': 'Ptéranodon', 'image': '/rewards/dinosaur-9.jpg'},{'id': 'dinosaur-10', 'type': 'dinosaur', 'label': 'Brachiosaure', 'image': '/rewards/dinosaur-10.jpg'},{'id': 'animal-1', 'type': 'animal', 'label': 'Panda roux', 'image': '/rewards/animal-1.jpg'},{'id': 'animal-2', 'type': 'animal', 'label': 'Okapi', 'image': '/rewards/animal-2.jpg'},{'id': 'animal-3', 'type': 'animal', 'label': 'Fennec', 'image': '/rewards/animal-3.jpg'},{'id': 'animal-4', 'type': 'animal', 'label': 'Axolotl', 'image': '/rewards/animal-4.jpg'},{'id': 'animal-5', 'type': 'animal', 'label': 'Ornithorynque', 'image': '/rewards/animal-5.jpg'},{'id': 'animal-6', 'type': 'animal', 'label': 'Quokka', 'image': '/rewards/animal-6.jpg'},{'id': 'animal-7', 'type': 'animal', 'label': 'Capybara', 'image': '/rewards/animal-7.jpg'},{'id': 'animal-8', 'type': 'animal', 'label': 'Piranha', 'image': '/rewards/animal-8.jpg'},{'id': 'animal-9', 'type': 'animal', 'label': 'Toucan', 'image': '/rewards/animal-9.jpg'},{'id': 'animal-10', 'type': 'animal', 'label': 'Margay', 'image': '/rewards/animal-10.jpg'}],**state}

@app.post('/api/rewards/<int:pid>/choose')
def choose_reward(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    kind=(request.json or {}).get('type')
    if kind not in {'robot','fairy','dinosaur','animal'}: return {'error':'Type de récompense inconnu'},400
    c=db(); r=c.execute('SELECT current_card,completed FROM reward_progress WHERE profile_id=?',(pid,)).fetchone()
    if r and r['current_card']:
        c.close(); return {'error':'Termine d’abord la carte en cours.'},409
    completed=json.loads(r['completed'] or '[]') if r else []
    candidates=[f'{kind}-{i}' for i in range(1,11) if f'{kind}-{i}' not in completed]
    if not candidates:
        c.close(); return {'error':'Toutes les cartes de ce type sont déjà révélées.'},409
    card=random.choice(candidates)
    if r: c.execute("UPDATE reward_progress SET current_card=?,revealed='[]' WHERE profile_id=?",(card,pid))
    else: c.execute("INSERT INTO reward_progress(profile_id,current_card,revealed,completed) VALUES(?,?,'[]','[]')",(pid,card))
    c.commit(); c.close(); return {'ok':True,'card':card}


@app.post('/api/rewards/<int:pid>/reveal')
def reveal_reward(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    c=db(); p=c.execute('SELECT coins FROM profiles WHERE id=?',(pid,)).fetchone(); r=c.execute('SELECT current_card,revealed,completed FROM reward_progress WHERE profile_id=?',(pid,)).fetchone()
    if not r or not r['current_card']: c.close(); return {'error':'Choisis une carte.'},400
    if p['coins']<10: c.close(); return {'error':'Il faut 10 pièces.'},400
    revealed=json.loads(r['revealed'] or '[]'); remaining=[i for i in range(20) if i not in revealed]
    if not remaining: c.close(); return {'error':'Carte déjà terminée.'},400
    piece=random.choice(remaining); revealed.append(piece); completed=json.loads(r['completed'] or '[]'); card=r['current_card']; done=len(revealed)>=20
    c.execute('UPDATE profiles SET coins=coins-10 WHERE id=?',(pid,))
    if done:
        if card not in completed: completed.append(card)
        c.execute("UPDATE reward_progress SET current_card=NULL,revealed='[]',completed=? WHERE profile_id=?",(json.dumps(completed),pid))
    else: c.execute('UPDATE reward_progress SET revealed=? WHERE profile_id=?',(json.dumps(revealed),pid))
    balance=p['coins']-10; c.commit(); c.close(); return {'ok':True,'piece':piece,'done':done,'coins':balance,'revealed':([] if done else revealed),'completed':completed}
@app.get('/api/stats/<int:pid>')
def stats(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    mode=(request.args.get('mode') or 'learning').lower()
    if mode not in ('learning','challenge'): mode='learning'
    c=db(); ss=[dict(x) for x in c.execute('SELECT id,started_at,active_ms,mode FROM sessions WHERE profile_id=? AND mode=? ORDER BY id DESC',(pid,mode))]
    out=[]
    for s in ss:
        qs=[dict(x) for x in c.execute("SELECT * FROM questions WHERE session_id=? AND status!='UNANSWERED'",(s['id'],))]
        correct=[q for q in qs if q['status']=='CORRECT']
        times=[q['response_ms'] for q in qs if q['response_ms'] is not None]
        cats=[]
        for kind in dict.fromkeys(q['kind'] for q in qs):
            kqs=[q for q in qs if q['kind']==kind]; kc=sum(1 for q in kqs if q['status']=='CORRECT')
            kt=[q['response_ms'] for q in kqs if q['response_ms'] is not None]; cats.append({'kind':kind,'attempted':len(kqs),'correct':kc,'accuracy':round(100*kc/len(kqs),1) if kqs else 0,'medianMs':int(statistics.median(kt)) if kt else None})
        out.append({'id':s['id'],'date':s['started_at'],'activeMs':s['active_ms'],'attempted':len(qs),'correct':len(correct),'incorrect':len(qs)-len(correct),'accuracy':round(100*len(correct)/len(qs),1) if qs else 0,'medianMs':int(statistics.median(times)) if times else None,'avgMs':int(sum(times)/len(times)) if times else None,'categories':cats})
    c.close(); return {'sessions':out,'mode':mode}

@app.get('/api/session/<int:sid>/stats')
def session_stats(sid):
    if (e:=require_auth()): return e
    c=db(); s=c.execute('SELECT id,profile_id,started_at,active_ms FROM sessions WHERE id=?',(sid,)).fetchone()
    if not s: c.close(); return {'error':'Séance inconnue'},404
    if not owns_profile(s['profile_id']): c.close(); return {'error':'Séance inconnue'},404
    qs=[dict(x) for x in c.execute("SELECT id,position,kind,display,expected,given_answer,last_answer,first_wrong_answer,status,response_ms,source,attempts,had_error FROM questions WHERE session_id=? AND status!='UNANSWERED' ORDER BY position",(sid,))]
    correct=[q for q in qs if q['status']=='CORRECT']; times=[q['response_ms'] for q in correct if q['response_ms'] is not None]
    kinds=[]
    for kind in dict.fromkeys(q['kind'] for q in qs):
        kqs=[q for q in qs if q['kind']==kind]; kc=sum(1 for q in kqs if q['status']=='CORRECT')
        kinds.append({'kind':kind,'attempted':len(kqs),'correct':kc,'incorrect':len(kqs)-kc,'accuracy':round(100*kc/len(kqs),1) if kqs else 0})
    result={'id':s['id'],'date':s['started_at'],'activeMs':s['active_ms'],'attempted':len(qs),'correct':len(correct),'incorrect':len(qs)-len(correct),'accuracy':round(100*len(correct)/len(qs),1) if qs else 0,'medianMs':int(statistics.median(times)) if times else None,'categories':kinds,'questions':qs}
    c.close(); return result

init_db()
def seed_challenge_levels():
    c=db(); n=c.execute('SELECT COUNT(*) n FROM challenge_levels').fetchone()['n']
    if n==0:
        for school in CLASSES:
            for level in range(1,6):
                c.execute('INSERT INTO challenge_levels(school_class,name,position,data) VALUES(?,?,?,?)',(school,f'{school}-{level}',level,json.dumps(seed_challenge_cfg(school,level))))
        c.commit()
    c.close()
seed_challenge_levels()
def migrate_profile_level_ids():
    c=db()
    for r in c.execute('SELECT id FROM profiles').fetchall():
        sync_profile_level(c,r['id'])
    c.commit(); c.close()
migrate_profile_level_ids()
if __name__=='__main__': app.run(host='127.0.0.1',port=5050,debug=True)
