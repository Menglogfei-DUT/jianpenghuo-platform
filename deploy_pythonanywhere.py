# -*- coding: utf-8 -*-
"""
PythonAnywhere one-shot deployment script for the Jianpenghuo V2.0 platform.

Flow:
  1. Verify API token and inspect available Python versions / existing webapps.
  2. Create a manual-configuration webapp (skip if it already exists).
  3. Upload every project file from the local source tree via the Files API.
  4. Point source directory, register the /static/ mapping, write the WSGI file.
  5. Reload the webapp and probe the public URL.

Usage:
  python deploy_pythonanywhere.py <api_token>
  or set environment variable JPH_PA_TOKEN before running.

The script never prints the token. All run output goes to the console and to
%TEMP%\\jph_deploy_log.txt.
"""
import os
import sys
import time
import json
import requests

# ==================== Configuration ====================
USERNAME = "menglongfei"
HOST = "https://www.pythonanywhere.com"
PROJECT_DIR = "/home/%s/jianpenghuo-platform" % USERNAME
DOMAIN = "%s.pythonanywhere.com" % USERNAME
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

EXCLUDE_DIR = {"data", "__pycache__", ".git"}
EXCLUDE_PREFIX = ("app_backup", "deploy_")
EXCLUDE_SUFFIX = (".log", ".pyc")
EXCLUDE_NAME = {"启动系统.bat"}

API = "%s/api/v0/user/%s" % (HOST, USERNAME)
LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "jph_deploy_log.txt")

_log = []


def log(msg=""):
    line = str(msg)
    _log.append(line)
    print(line, flush=True)


def flush_log():
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(_log))


def py_version_code(version):
    """'3.11' -> 'python311'; '3.6' -> 'python36'."""
    major, minor = version.split(".")[:2]
    return "python%s%s" % (major, minor)


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JPH_PA_TOKEN", "")
    if not token:
        log("ERROR: missing API token. Pass it as argv[1] or set JPH_PA_TOKEN.")
        flush_log()
        sys.exit(1)

    headers = {"Authorization": "Token %s" % token}
    s = requests.Session()
    s.headers.update(headers)

    # ---------- 1. Auth + environment ----------
    log("== 1. Verify token and account environment ==")
    r = s.get(API + "/cpu/", timeout=20)
    log("cpu: HTTP %s %s" % (r.status_code, r.text[:200]))
    if r.status_code != 200:
        log("FATAL: token rejected or endpoint unreachable.")
        flush_log()
        sys.exit(2)

    r = s.get(API + "/default_python3_version/", timeout=20)
    log("python versions: HTTP %s %s" % (r.status_code, r.text[:300]))
    ver_info = r.json() if r.status_code == 200 else {}
    available = ver_info.get("available_python3_versions", ["3.11"])
    chosen = "3.11" if "3.11" in available else available[-1]
    py_code = py_version_code(chosen)
    log("selected Python %s -> %s" % (chosen, py_code))

    # ---------- 2. List / create webapp ----------
    log("\n== 2. Webapp ==")
    r = s.get(API + "/webapps/", timeout=20)
    existing = r.json() if r.status_code == 200 else []
    log("existing webapps: HTTP %s %s" % (r.status_code, json.dumps(existing)[:300]))
    exists = any(w.get("domain_name") == DOMAIN for w in existing)

    if not exists:
        r = s.post(API + "/webapps/", data={
            "domain_name": DOMAIN,
            "python_version": py_code,
        }, timeout=30)
        log("create webapp: HTTP %s %s" % (r.status_code, r.text[:300]))
        if r.status_code not in (200, 201):
            log("FATAL: could not create webapp.")
            flush_log()
            sys.exit(3)
        time.sleep(3)
    else:
        log("webapp already exists, skip creation.")

    # ---------- 3. Upload project files ----------
    log("\n== 3. Upload project files ==")
    uploaded = []
    for dp, dns, fns in os.walk(LOCAL_ROOT):
        dns[:] = [d for d in dns if d not in EXCLUDE_DIR]
        for fn in fns:
            if fn in EXCLUDE_NAME or fn.startswith(EXCLUDE_PREFIX) or fn.endswith(EXCLUDE_SUFFIX):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, LOCAL_ROOT).replace("\\", "/")
            remote_path = "%s/%s" % (PROJECT_DIR, rel)
            with open(full, "rb") as fh:
                content = fh.read()
            mime = "text/plain; charset=utf-8" if rel.endswith((".py", ".txt", ".md", ".css", ".html", ".ico")) else "application/octet-stream"
            rr = s.post(API + "/files/path" + remote_path,
                        files={"content": (fn, content, mime)}, timeout=60)
            ok = rr.status_code in (200, 201)
            log("  [%s] %s (%dB)" % ("OK " if ok else "FAIL", rel, len(content)))
            if not ok:
                log("  upload failure: HTTP %s %s" % (rr.status_code, rr.text[:200]))
                flush_log()
                sys.exit(4)
            uploaded.append(rel)
    log("uploaded %d files." % len(uploaded))

    # ---------- 4. Source dir + static mapping ----------
    log("\n== 4. Configure source directory and static mapping ==")
    r = s.put(API + "/webapps/%s/" % DOMAIN, data={
        "source_directory": PROJECT_DIR,
    }, timeout=30)
    log("set source_directory: HTTP %s %s" % (r.status_code, r.text[:200]))

    r = s.get(API + "/webapps/%s/static_files/" % DOMAIN, timeout=20)
    mappings = r.json() if r.status_code == 200 else []
    has_static = any(m.get("url") == "/static/" for m in mappings)
    if not has_static:
        r = s.post(API + "/webapps/%s/static_files/" % DOMAIN, data={
            "url": "/static/",
            "path": PROJECT_DIR + "/static/",
        }, timeout=30)
        log("create static mapping: HTTP %s %s" % (r.status_code, r.text[:200]))
    else:
        log("static mapping already present.")

    # ---------- 5. Write WSGI file ----------
    log("\n== 5. Write WSGI configuration ==")
    wsgi_name = DOMAIN.replace(".", "_") + "_wsgi.py"
    wsgi_remote = "/var/www/%s" % wsgi_name
    wsgi_body = (
        "# -*- coding: utf-8 -*-\n"
        "import os\n"
        "import sys\n\n"
        "project = '%s'\n"
        "os.environ.setdefault('SMS_DEMO', '0')\n"
        "if project not in sys.path:\n"
        "    sys.path.insert(0, project)\n"
        "os.chdir(project)\n\n"
        "from wsgi import application  # noqa: E402\n"
    ) % PROJECT_DIR
    r = s.post(API + "/files/path" + wsgi_remote,
               files={"content": (wsgi_name, wsgi_body.encode("utf-8"), "text/plain; charset=utf-8")},
               timeout=30)
    log("write WSGI %s: HTTP %s %s" % (wsgi_remote, r.status_code, r.text[:200]))

    # ---------- 6. Reload ----------
    log("\n== 6. Reload webapp ==")
    r = s.post(API + "/webapps/%s/reload/" % DOMAIN, timeout=30)
    log("reload: HTTP %s %s" % (r.status_code, r.text[:200]))
    time.sleep(5)

    # ---------- 7. Public probe ----------
    log("\n== 7. Public probe ==")
    for path, expect in [("/", 200), ("/static/css/style.css", 200), ("/api/me", 401)]:
        try:
            rr = s.get(HOST + path, timeout=25, allow_redirects=False)
            log("  %-28s HTTP %s (%dB)" % (path, rr.status_code, len(rr.content)))
        except Exception as e:
            log("  %-28s ERROR %s" % (path, e))
    log("\nPublic URL: https://%s" % DOMAIN)
    log("Demo account: 13800000000 / 123456")
    flush_log()


if __name__ == "__main__":
    main()
