"""Utilidades MySQL compartidas: conexión, carga de esquemas y ejecución de consultas."""
import subprocess
import pymysql

CFG = dict(host="127.0.0.1", port=3306, user="root", password="root", charset="utf8mb4")
CONTAINER = "mysql84"


def conectar(db=None, **kw):
    return pymysql.connect(database=db, **CFG, **kw)


def cargar_sql(db, ruta_sql):
    """Recrea la base `db` y ejecuta el archivo .sql completo con el cliente mysql del contenedor."""
    with conectar() as c, c.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
        cur.execute(f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    with open(ruta_sql, "rb") as f:
        r = subprocess.run(["docker", "exec", "-i", CONTAINER, "mysql", "-uroot", "-proot",
                            "--default-character-set=utf8mb4", db], stdin=f, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf8", "replace"))


def esquema(db):
    """Sentencias SHOW CREATE TABLE de todas las tablas, como las entrega el evaluador."""
    with conectar(db) as c, c.cursor() as cur:
        cur.execute("SHOW FULL TABLES WHERE Table_type='BASE TABLE'")
        tablas = [r[0] for r in cur.fetchall()]
        out = []
        for t in tablas:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            out.append(cur.fetchone()[1] + ";")
    return "\n\n".join(out)


def ejecutar(db, sql, max_filas=None, timeout_s=20):
    """Ejecuta `sql` en `db`. Devuelve dict ok/columnas/filas/error (formato del evaluador)."""
    try:
        with conectar(db, read_timeout=timeout_s) as c, c.cursor() as cur:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME={timeout_s * 1000}")
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            filas = cur.fetchall() if cur.description else []
            if max_filas is not None:
                filas = filas[:max_filas]
            return {"ok": True, "columnas": cols, "filas": [list(f) for f in filas], "error": None}
    except Exception as e:
        return {"ok": False, "columnas": [], "filas": [], "error": str(e)}
