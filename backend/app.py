import os
import requests
import ipaddress
import logging
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("Rollcall-Backend")

app = Flask(__name__)
CORS(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

SITE_PASSWORD = os.getenv("SITE_PASSWORD", "admin")
PASS_HINT = os.getenv("PASS_HINT", "Ask the admin.")
WIKI_URL = os.getenv("WIKI_EXTERNAL_URL", "#")
HOME_URL = os.getenv("HOME_EXTERNAL_URL", "/")
EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "yourdomain.com")

def is_local_ip(ip):
    try: return ipaddress.ip_address(ip).is_private
    except: return False

@app.route('/verify', methods=['POST'])
def verify():
    if is_local_ip(request.remote_addr) or request.json.get('password') == SITE_PASSWORD:
        return jsonify({"authorized": True})
    return jsonify({"authorized": False}), 401

@app.route('/config', methods=['GET'])
def get_config():
    return jsonify({
        "jellyfin_url": os.getenv("JELLYFIN_EXTERNAL_URL"),
        "romm_url": os.getenv("ROMM_EXTERNAL_URL"),
        "synapse_url": os.getenv("SYNAPSE_EXTERNAL_URL"),
        "booklore_url": os.getenv("BOOKLORE_EXTERNAL_URL"),
        "filebrowser_url": os.getenv("FILEBROWSER_EXTERNAL_URL"),
        "immich_url": os.getenv("IMMICH_EXTERNAL_URL"),
        "wiki_url": WIKI_URL,
        "home_url": HOME_URL,
        "hint": PASS_HINT,
        "email_domain": EMAIL_DOMAIN,
        "is_local": is_local_ip(request.remote_addr)
    })

# --- SERVICE LOGIC ---

def create_jellyfin_user(u, p, mode='create'):
    base, token = os.getenv('JELLYFIN_INTERNAL_URL'), os.getenv('JELLYFIN_API_KEY')
    h = {"X-Emby-Token": token, "Content-Type": "application/json"}
    try:
        users = requests.get(f"{base}/Users", headers=h, timeout=10).json()
        user_exists = any(x['Name'].lower() == u.lower() for x in users)
        existing_user = next((x for x in users if x['Name'].lower() == u.lower()), None)
        
        if mode == 'create':
            if user_exists:
                return {"status": False, "reason": "User already exists"}
            res = requests.post(f"{base}/Users/New", json={"Name": u, "Password": p}, headers=h, timeout=10)
            return "created" if res.status_code == 200 else {"status": False, "reason": "Creation failed"}
        else:  # update mode
            if not user_exists:
                return {"status": False, "reason": "User does not exist"}
            if p:
                user_id = existing_user['Id']
                requests.post(f"{base}/Users/{user_id}/Password", json={"NewPw": p}, headers=h, timeout=10)
            return "updated"
    except Exception as e:
        logger.error(f"[Jellyfin] Error: {e}")
        return {"status": False, "reason": "Connection error"}

def create_romm_user(u, p, email, mode='create'):
    base = os.getenv('ROMM_INTERNAL_URL').rstrip('/')
    admin_u, admin_p = os.getenv('ROMM_ADMIN_USER'), os.getenv('ROMM_ADMIN_PASS')

    try:
        token_res = requests.post(
            f"{base}/api/token",
            data={"grant_type": "password", "username": admin_u, "password": admin_p, "scope": "users.read users.write"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15
        )
        
        if token_res.status_code != 200:
            auth = (admin_u, admin_p)
            users_res = requests.get(f"{base}/api/users", auth=auth, timeout=10)
            user_exists = False
            existing_user = None
            if users_res.status_code == 200:
                for x in users_res.json():
                    if x.get('username', '').lower() == u.lower():
                        user_exists = True
                        existing_user = x
                        break
            
            if mode == 'create':
                if user_exists:
                    return {"status": False, "reason": "User already exists"}
                res = requests.post(f"{base}/api/users", json={"username": u, "password": p, "email": email, "role": "viewer"}, auth=auth, timeout=15)
                if res.status_code in [200, 201]: return "created"
                return {"status": False, "reason": "Creation failed"}
            else:  # update mode
                if not user_exists:
                    return {"status": False, "reason": "User does not exist"}
                return "updated"
        
        access_token = token_res.json().get('access_token')
        auth_header = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        
        users_res = requests.get(f"{base}/api/users", headers=auth_header, timeout=10)
        user_exists = False
        existing_user = None
        if users_res.status_code == 200:
            for x in users_res.json():
                if x.get('username', '').lower() == u.lower():
                    user_exists = True
                    existing_user = x
                    break
        
        if mode == 'create':
            if user_exists:
                return {"status": False, "reason": "User already exists"}
            res = requests.post(f"{base}/api/users", json={"username": u, "password": p, "email": email, "role": "viewer"}, headers=auth_header, timeout=15)
            if res.status_code in [200, 201]: return "created"
            return {"status": False, "reason": "Creation failed"}
        else:  # update mode
            if not user_exists:
                return {"status": False, "reason": "User does not exist"}
            return "updated"
            
    except Exception as e:
        logger.error(f"[RomM] Error: {e}")
    return {"status": False, "reason": "Connection error"}
    
def create_booklore_user(u, p, email, mode='create'):
    base = os.getenv('BOOKLORE_INTERNAL_URL').rstrip('/')
    admin_u, admin_p = os.getenv('BOOKLORE_ADMIN_USER'), os.getenv('BOOKLORE_ADMIN_PASS')
    
    try:
        session = requests.Session()
        
        # Login
        login_res = session.post(f"{base}/api/v1/auth/login", json={"username": admin_u, "password": admin_p}, timeout=15)
        if login_res.status_code != 200:
            logger.error(f"[BookLore] Login failed: {login_res.status_code}")
            return {"status": False, "reason": "Admin login failed"}
        
        access_token = login_res.json().get('accessToken')
        auth_header = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
        
        # Get libraries
        libraries_res = session.get(f"{base}/api/v1/libraries", headers=auth_header, timeout=10)
        library_ids = [lib.get('id') for lib in libraries_res.json()] if libraries_res.status_code == 200 else []
        
        # Check if user exists
        user_id, user_exists = None, False
        users_res = session.get(f"{base}/api/v1/users", headers=auth_header, timeout=10)
        if users_res.status_code == 200:
            for existing in users_res.json():
                if existing.get('username', '').lower() == u.lower():
                    user_id, user_exists = existing.get('id'), True
                    break
        
        if mode == 'create':
            if user_exists:
                return {"status": False, "reason": "User already exists"}
            
            # Create user
            res = session.post(f"{base}/api/v1/auth/register", json={"name": u, "username": u, "email": email, "password": p}, headers=auth_header, timeout=15)
            if res.status_code not in [200, 201, 204]:
                if res.status_code == 400 and "already taken" in res.text.lower():
                    return {"status": False, "reason": "User already exists"}
                logger.error(f"[BookLore] Registration failed: {res.status_code}")
                return {"status": False, "reason": "Registration failed"}
            
            # Get new user ID
            users_res = session.get(f"{base}/api/v1/users", headers=auth_header, timeout=10)
            if users_res.status_code == 200:
                for existing in users_res.json():
                    if existing.get('username', '').lower() == u.lower():
                        user_id = existing.get('id')
                        break
        else:  # update mode
            if not user_exists:
                return {"status": False, "reason": "User does not exist"}
        
        # Update permissions (for both create and update)
        if user_id:
            update_payload = {
                "id": user_id, "name": u, "username": u, "email": email,
                "assignedLibraries": library_ids,
                "permissions": {
                    "canUpload": False, "canDownload": True, "canEditMetadata": False,
                    "canManageLibrary": False, "canSyncKoReader": True, "canSyncKobo": True,
                    "canEmailBook": False, "canDeleteBook": False, "canAccessOpds": True,
                    "canManageMetadataConfig": False, "canAccessBookdrop": False,
                    "canAccessLibraryStats": False, "canAccessUserStats": True,
                    "canAccessTaskManager": False, "canManageGlobalPreferences": False,
                    "canManageIcons": False, "canManageFonts": False,
                    "canBulkAutoFetchMetadata": False, "canBulkCustomFetchMetadata": False,
                    "canBulkEditMetadata": False, "canBulkRegenerateCover": False,
                    "canMoveOrganizeFiles": False, "canBulkLockUnlockMetadata": False,
                    "canBulkResetBookloreReadProgress": False, "canBulkResetKoReaderReadProgress": False,
                    "canBulkResetBookReadStatus": False, "demoUser": False, "admin": False
                }
            }
            session.put(f"{base}/api/v1/users/{user_id}", json=update_payload, headers=auth_header, timeout=15)
        
        return "updated" if mode == 'update' else "created"
            
    except Exception as e:
        logger.error(f"[BookLore] Error: {e}")
    return {"status": False, "reason": "Connection error"}
    
def create_synapse_user(u, p, mode='create'):
    domain = os.getenv('SYNAPSE_DOMAIN')
    base_url = os.getenv('SYNAPSE_INTERNAL_URL')
    token = os.getenv('SYNAPSE_ACCESS_TOKEN')
    user_id = f"@{u}:{domain}"
    url = f"{base_url}/_synapse/admin/v2/users/{user_id}"
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        check_res = requests.get(url, headers=h, timeout=10)
        user_exists = check_res.status_code == 200 and check_res.json().get('name') == user_id
        
        if mode == 'create':
            if user_exists:
                return {"status": False, "reason": "User already exists"}
            res = requests.put(url, json={"password": p, "displayname": u, "admin": False, "deactivated": False}, headers=h, timeout=10)
            return "created" if res.status_code in [200, 201] else {"status": False, "reason": "Creation failed"}
        else:  # update mode
            if not user_exists:
                return {"status": False, "reason": "User does not exist"}
            update_data = {"displayname": u, "admin": False, "deactivated": False}
            if p:
                update_data["password"] = p
            res = requests.put(url, json=update_data, headers=h, timeout=10)
            return "updated" if res.status_code in [200, 201] else {"status": False, "reason": "Update failed"}
    except Exception as e:
        logger.error(f"[Synapse] Error: {e}")
        return {"status": False, "reason": "Connection error"}

def create_filebrowser_user(u, p, mode='create'):
    base_url = os.getenv('FILEBROWSER_INTERNAL_URL', '').rstrip('/')
    api_key = os.getenv('FILEBROWSER_API_KEY')
    
    try:
        # Use API key as Bearer token (per Filebrowser Quantum wiki)
        auth_header = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # Get existing users to check if user exists
        users_res = requests.get(f"{base_url}/api/users", headers=auth_header, timeout=10)
        
        if users_res.status_code == 401 or users_res.status_code == 403:
            logger.error(f"[Filebrowser] API key authentication failed: {users_res.status_code} - {users_res.text}")
            return {"status": False, "reason": "API authentication failed"}
        
        user_exists = False
        existing_user = None
        
        if users_res.status_code == 200:
            for user in users_res.json():
                if user.get('username', '').lower() == u.lower():
                    user_exists = True
                    existing_user = user
                    break
        
        # User data structure for Filebrowser Quantum
        # Scopes are omitted to use source defaults (set defaultEnabled and defaultUserScope in FB config)
        user_data = {
            "which": [],
            "data": {
                "username": u,
                "password": p,
                "loginMethod": "password",
                "permissions": {
                    "admin": False,
                    "api": False,
                    "realtime": False,
                    "modify": True,
                    "share": True,
                    "create": True,
                    "rename": True,
                    "delete": True,
                    "download": True
                }
            }
        }
        
        if mode == 'create':
            if user_exists:
                return {"status": False, "reason": "User already exists"}
            
            res = requests.post(f"{base_url}/api/users", json=user_data, headers=auth_header, timeout=15)
            
            if res.status_code in [200, 201]:
                return "created"
            elif res.status_code == 409:
                return {"status": False, "reason": "User already exists"}
            else:
                logger.error(f"[Filebrowser] Creation failed: {res.status_code} - {res.text}")
                return {"status": False, "reason": "Creation failed"}
        
        else:  # update mode
            if not user_exists:
                return {"status": False, "reason": "User does not exist"}
            
            user_id = existing_user.get('id')
            update_data = user_data.copy()
            
            if not p:
                del update_data['data']['password']
            
            res = requests.put(f"{base_url}/api/users/{user_id}", json=update_data, headers=auth_header, timeout=15)
            
            if res.status_code in [200, 201]:
                return "updated"
            else:
                logger.error(f"[Filebrowser] Update failed: {res.status_code} - {res.text}")
                return {"status": False, "reason": "Update failed"}
                
    except Exception as e:
        logger.error(f"[Filebrowser] Error: {e}")
        return {"status": False, "reason": "Connection error"}

def create_immich_user(u, p, email, mode='create'):
    base_url = os.getenv('IMMICH_INTERNAL_URL', '').rstrip('/')
    api_key = os.getenv('IMMICH_API_KEY')
    
    try:
        auth_header = {"x-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}
        
        # Get existing users to check if user exists (admin endpoint)
        users_res = requests.get(f"{base_url}/api/admin/users", headers=auth_header, timeout=10)
        
        if users_res.status_code == 401 or users_res.status_code == 403:
            logger.error(f"[Immich] API key authentication failed: {users_res.status_code} - {users_res.text}")
            return {"status": False, "reason": "API authentication failed"}
        
        user_exists = False
        existing_user = None
        
        if users_res.status_code == 200:
            for user in users_res.json():
                if user.get('email', '').lower() == email.lower():
                    user_exists = True
                    existing_user = user
                    break
        
        if mode == 'create':
            if user_exists:
                return {"status": False, "reason": "User already exists"}
            
            user_data = {
                "email": email,
                "name": u,
                "password": p,
                "shouldChangePassword": False,
                "memoriesEnabled": True
            }
            
            res = requests.post(f"{base_url}/api/admin/users", json=user_data, headers=auth_header, timeout=15)
            
            if res.status_code in [200, 201]:
                return "created"
            elif res.status_code == 400 and "already" in res.text.lower():
                return {"status": False, "reason": "User already exists"}
            else:
                logger.error(f"[Immich] Creation failed: {res.status_code} - {res.text}")
                return {"status": False, "reason": "Creation failed"}
        
        else:  # update mode
            if not user_exists:
                return {"status": False, "reason": "User does not exist"}
            
            user_id = existing_user.get('id')
            update_data = {"name": u}
            if p:
                update_data["password"] = p
            
            res = requests.put(f"{base_url}/api/admin/users/{user_id}", json=update_data, headers=auth_header, timeout=15)
            
            if res.status_code in [200, 201]:
                return "updated"
            else:
                logger.error(f"[Immich] Update failed: {res.status_code} - {res.text}")
                return {"status": False, "reason": "Update failed"}
                
    except Exception as e:
        logger.error(f"[Immich] Error: {e}")
        return {"status": False, "reason": "Connection error"}

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    u, p, pre = data.get('username'), data.get('password', ''), data.get('email_prefix')
    services = data.get('services', [])
    mode = data.get('mode', 'create')  # 'create' or 'update'
    email = f"{pre}@{EMAIL_DOMAIN}"
    
    results = {}
    if 'jellyfin' in services: results['jellyfin'] = create_jellyfin_user(u, p, mode)
    if 'romm' in services: results['romm'] = create_romm_user(u, p, email, mode)
    if 'booklore' in services: results['booklore'] = create_booklore_user(u, p, email, mode)
    if 'synapse' in services: results['synapse'] = create_synapse_user(u, p, mode)
    if 'filebrowser' in services: results['filebrowser'] = create_filebrowser_user(u, p, mode)
    if 'immich' in services: results['immich'] = create_immich_user(u, p, email, mode)
    
    return jsonify({"success": True, "details": results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
