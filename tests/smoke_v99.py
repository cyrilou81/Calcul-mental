import os, tempfile, importlib.util, pathlib
dbfile=tempfile.NamedTemporaryFile(suffix=".db",delete=False); dbfile.close()
os.environ["DB_PATH"]=dbfile.name
os.environ["SECRET_KEY"]="test-secret"
os.environ["ADMIN_PASSWORD"]="Admin-Test-123!"
spec=importlib.util.spec_from_file_location("calc",pathlib.Path(__file__).parents[1]/"app.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
client=m.app.test_client()

# Account + auth
r=client.post("/api/auth/register",json={"username":"parent1","password":"MotDePasse-123!"}); assert r.status_code==200,r.data
# Admin protected until dedicated password entered
assert client.get("/api/admin/levels").status_code==403
assert client.post("/admin/login",data={"password":"Admin-Test-123!"}).status_code in (302,303)
assert client.get("/api/admin/levels").status_code==200

# Profile + config
r=client.post("/api/profiles",json={"name":"Paul","color":"#8fdff7","school_class":"CE1"}); assert r.status_code==200,r.data
pid=r.get_json()["id"]
cfg=client.get(f"/api/config/{pid}").get_json()
assert client.put(f"/api/config/{pid}",json=cfg).status_code==200

# Same profile name is allowed in another account.
client.post("/api/auth/logout")
r=client.post("/api/auth/register",json={"username":"parent2","password":"AutrePasse-123!"}); assert r.status_code==200
r=client.post("/api/profiles",json={"name":"Paul","color":"#8fdff7","school_class":"CP"}); assert r.status_code==200,r.data

# Stable challenge level survives reorder.
client.post("/api/auth/logout")
client.post("/api/auth/login",json={"username":"parent1","password":"MotDePasse-123!"})
c=m.db(); p=c.execute("SELECT challenge_level_id FROM profiles WHERE id=?",(pid,)).fetchone()
m.sync_profile_level(c,pid); c.commit()
p=c.execute("SELECT challenge_level,challenge_level_id FROM profiles WHERE id=?",(pid,)).fetchone()
stable_id=p["challenge_level_id"]
levels=m.challenge_levels_for(c,"CE1")
if len(levels)>1:
    a,b=levels[0],levels[1]
    c.execute("UPDATE challenge_levels SET position=-1 WHERE id=?",(a["id"],))
    c.execute("UPDATE challenge_levels SET position=? WHERE id=?",(a["position"],b["id"]))
    c.execute("UPDATE challenge_levels SET position=? WHERE id=?",(b["position"],a["id"]))
    c.commit(); m.sync_profile_level(c,pid); c.commit()
    p2=c.execute("SELECT challenge_level_id FROM profiles WHERE id=?",(pid,)).fetchone()
    assert p2["challenge_level_id"]==stable_id
c.close()
print("smoke_v99 OK")
