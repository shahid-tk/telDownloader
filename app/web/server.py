import base64
import hashlib
import os
import re
import secrets
from typing import Dict, Any, Optional
from urllib.parse import parse_qs
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from config import settings
from services.download_tracker import tracker


def get_auth_token() -> str:
    user = settings.web_username or "admin"
    pwd = settings.web_password or ""
    data = f"{user}:{pwd}:teldownloader_secure".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def is_authenticated(request: Request) -> bool:
    cookie_token = request.cookies.get("tel_session")
    if cookie_token and secrets.compare_digest(cookie_token, get_auth_token()):
        return True

    # Also support Basic Auth header for API consumers/curl
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            if ":" in decoded:
                username, password = decoded.split(":", 1)
                expected_user = settings.web_username or "admin"
                expected_pass = settings.web_password or ""
                return secrets.compare_digest(username, expected_user) and secrets.compare_digest(password, expected_pass)
        except Exception:
            pass

    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always allow login and logout endpoints
        if path in ("/login", "/logout"):
            return await call_next(request)

        # Require session authentication for all pages & APIs
        if not is_authenticated(request):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Unauthorized: Please sign in."}, status_code=401)
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


app = FastAPI(title="telDownloader Web Dashboard", docs_url="/api/docs")

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sign In - telDownloader</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 font-sans selection:bg-blue-600 selection:text-white">
  <div class="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
    <div class="text-center space-y-2">
      <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 mx-auto flex items-center justify-center text-2xl shadow-lg shadow-blue-500/20">
        📥
      </div>
      <h1 class="text-xl font-bold text-white tracking-wide">telDownloader</h1>
      <p class="text-xs text-slate-400">Media Ingestion & Live Monitor</p>
    </div>

    {error_placeholder}

    <form method="POST" action="/login" class="space-y-4">
      <div>
        <label class="block text-xs font-medium text-slate-300 mb-1.5">Username</label>
        <input type="text" name="username" value="{username_val}" required autofocus class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition">
      </div>
      <div>
        <label class="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
        <input type="password" name="password" placeholder="••••••••" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition">
      </div>
      <button type="submit" class="w-full py-2.5 px-4 rounded-xl text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition duration-150">
        Sign In
      </button>
    </form>
  </div>
</body>
</html>"""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>telDownloader Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 500: '#3b82f6', 600: '#2563eb' }
          }
        }
      }
    }
  </script>
  <style>
    @keyframes pulse-subtle { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
    .animate-pulse-subtle { animation: pulse-subtle 2s infinite ease-in-out; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col font-sans selection:bg-blue-600 selection:text-white">

  <!-- Top Navbar -->
  <header class="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-xl shadow-lg shadow-blue-500/20">
          📥
        </div>
        <div>
          <h1 class="text-lg font-bold text-white tracking-wide">telDownloader</h1>
          <p class="text-xs text-slate-400">Media Ingestion & Live Monitor</p>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <span id="ws-badge" class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          Live Stream
        </span>
        <button onclick="toggleTab('downloads')" id="tab-btn-downloads" class="px-3.5 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white shadow-sm transition">Monitor</button>
        <button onclick="toggleTab('library')" id="tab-btn-library" class="px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition">Library</button>
        <button onclick="toggleTab('config')" id="tab-btn-config" class="px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition">Configuration</button>
        <a href="/logout" title="Sign Out" class="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-400 hover:bg-slate-800/80 transition flex items-center gap-1 border border-transparent hover:border-rose-500/20">Sign Out</a>
      </div>
    </div>
  </header>

  <!-- Main Content Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">

    <!-- Stat Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Downloads</div>
        <div class="mt-2 text-3xl font-extrabold text-white flex items-baseline justify-between">
          <span id="stat-active">0</span>
          <span class="text-blue-500 text-sm">⚡ Live</span>
        </div>
      </div>
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Movies</div>
        <div class="mt-2 text-3xl font-extrabold text-white flex items-baseline justify-between">
          <span id="stat-movies">--</span>
          <span class="text-slate-500 text-sm">🎬</span>
        </div>
      </div>
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Shows</div>
        <div class="mt-2 text-3xl font-extrabold text-white flex items-baseline justify-between">
          <span id="stat-shows">--</span>
          <span class="text-slate-500 text-sm">📺</span>
        </div>
      </div>
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm">
        <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Media Servers</div>
        <div class="mt-2 text-sm font-semibold text-slate-200" id="stat-servers">
          Loading...
        </div>
      </div>
    </div>

    <!-- TAB 1: DOWNLOADS MONITOR -->
    <section id="section-downloads" class="space-y-6">
      <!-- Active Section -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <h2 class="text-lg font-bold text-white flex items-center space-x-2">
            <span>Active Ingestion Queue</span>
            <span id="active-count-badge" class="ml-2 px-2 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-400 font-medium">0 active</span>
          </h2>
        </div>

        <div id="active-list" class="mt-6 space-y-4">
          <div class="py-12 text-center text-slate-500">
            <svg class="mx-auto h-12 w-12 text-slate-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <p class="text-sm font-medium">No active downloads right now.</p>
            <p class="text-xs text-slate-500 mt-1">Send a video or episode to your Telegram bot to start downloading.</p>
          </div>
        </div>
      </div>

      <!-- Recent History Section -->
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <h2 class="text-lg font-bold text-white pb-4 border-b border-slate-800">Recent Completed & Processed</h2>
        <div class="mt-4 overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-300">
            <thead>
              <tr class="text-xs uppercase text-slate-500">
                <th class="py-3 px-4 font-semibold">Media Name</th>
                <th class="py-3 px-4 font-semibold">Type</th>
                <th class="py-3 px-4 font-semibold">Status</th>
                <th class="py-3 px-4 font-semibold">Completed Time</th>
              </tr>
            </thead>
            <tbody id="history-tbody" class="divide-y divide-slate-800/60">
              <tr>
                <td colspan="4" class="py-6 text-center text-slate-500">No recent history yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 2: LIBRARY EXPLORER -->
    <section id="section-library" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
          <h2 class="text-lg font-bold text-white">Ingested Media Library</h2>
          <input type="text" id="lib-search" oninput="filterLibrary()" placeholder="Search movies, shows..." class="bg-slate-950 border border-slate-700 px-3 py-1.5 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 w-full sm:w-64">
        </div>
        <div class="mt-4 overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-300">
            <thead>
              <tr class="text-xs uppercase text-slate-500">
                <th class="py-3 px-4 font-semibold">Title</th>
                <th class="py-3 px-4 font-semibold">Type</th>
                <th class="py-3 px-4 font-semibold">Season / Episode</th>
                <th class="py-3 px-4 font-semibold">File Name</th>
                <th class="py-3 px-4 font-semibold">Ingested Date</th>
              </tr>
            </thead>
            <tbody id="library-tbody" class="divide-y divide-slate-800/60">
              <tr>
                <td colspan="5" class="py-8 text-center text-slate-500">Loading library...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 3: CONFIGURATION EDITOR -->
    <section id="section-config" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <div class="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h2 class="text-lg font-bold text-white">Environment & Parameters</h2>
            <p class="text-xs text-slate-400 mt-1">Configure your bot, media servers, and directories safely from this web interface.</p>
          </div>
          <button onclick="saveConfig()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold shadow-md transition">Save & Restart App</button>
        </div>

        <form id="config-form" class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="space-y-4">
            <h3 class="text-sm font-semibold text-blue-400 uppercase tracking-wider">Telegram Credentials</h3>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Telegram Bot Token</label>
              <input type="text" id="cfg-BOT_TOKEN" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Admin Telegram User ID</label>
              <input type="text" id="cfg-ADMIN_USER_ID" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Telethon API ID</label>
                <input type="text" id="cfg-API_ID" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Telethon API Hash</label>
                <input type="text" id="cfg-API_HASH" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Telethon Source Chat (Optional)</label>
              <input type="text" id="cfg-TELETHON_SOURCE_CHAT" placeholder="Leave empty for private bot chat" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
            </div>
          </div>

          <div class="space-y-4">
            <h3 class="text-sm font-semibold text-blue-400 uppercase tracking-wider">Media & Auto-Scan Config</h3>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Movies Directory</label>
              <input type="text" id="cfg-MOVIES_DIR" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Shows Directory</label>
              <input type="text" id="cfg-SHOWS_DIR" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Jellyfin URL</label>
                <input type="text" id="cfg-JELLYFIN_URL" placeholder="http://jellyfin:8096" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Jellyfin API Key</label>
                <input type="text" id="cfg-JELLYFIN_API_KEY" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Plex URL</label>
                <input type="text" id="cfg-PLEX_URL" placeholder="http://plex:32400" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1">Plex Token</label>
                <input type="text" id="cfg-PLEX_TOKEN" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Log Level</label>
              <select id="cfg-LOG_LEVEL" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
                <option value="INFO">INFO</option>
                <option value="DEBUG">DEBUG</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
              </select>
            </div>
            <div class="border-t border-slate-800 pt-4 mt-2">
              <div class="flex items-center justify-between mb-3">
                <h4 class="text-xs font-semibold text-blue-400 uppercase tracking-wider">Web Dashboard Security</h4>
                <span id="auth-status-badge" class="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">No Password (Open Access)</span>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-400 mb-1">Web Username</label>
                  <input type="text" id="cfg-WEB_USERNAME" value="admin" placeholder="admin" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-400 mb-1">Web Password</label>
                  <input type="password" id="cfg-WEB_PASSWORD" placeholder="Enter password to secure dashboard" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500">
                </div>
              </div>
              <p class="text-[11px] text-slate-500 mt-2">Default username is <strong class="text-slate-400">admin</strong> with no password set. Enter a password above to secure this web dashboard.</p>
            </div>
          </div>
        </form>

        <div id="cfg-alert" class="hidden mt-4 p-3 rounded-lg text-sm"></div>
      </div>
    </section>

  </main>

  <script>
    let libraryData = [];

    function toggleTab(tab) {
      ['downloads', 'library', 'config'].forEach(t => {
        const sec = document.getElementById('section-' + t);
        const btn = document.getElementById('tab-btn-' + t);
        if (t === tab) {
          sec.classList.remove('hidden');
          btn.className = "px-3.5 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white shadow-sm transition";
        } else {
          sec.classList.add('hidden');
          btn.className = "px-3.5 py-1.5 rounded-lg text-sm font-medium text-slate-300 hover:bg-slate-800 transition";
        }
      });
      if (tab === 'library') loadLibrary();
      if (tab === 'config') loadConfig();
    }

    // Connect WebSocket
    function connectWS() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/downloads`);

      ws.onopen = () => {
        document.getElementById('ws-badge').innerHTML = '<span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Live Stream';
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        renderDownloads(data);
      };

      ws.onclose = () => {
        document.getElementById('ws-badge').innerHTML = '<span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-rose-400"></span>Disconnected';
        setTimeout(connectWS, 3000);
      };
    }

    function renderDownloads(data) {
      const active = data.active || [];
      const history = data.history || [];

      document.getElementById('stat-active').textContent = active.length;
      document.getElementById('active-count-badge').textContent = `${active.length} active`;

      const activeList = document.getElementById('active-list');
      if (active.length === 0) {
        activeList.innerHTML = `
          <div class="py-12 text-center text-slate-500">
            <svg class="mx-auto h-12 w-12 text-slate-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <p class="text-sm font-medium">No active downloads right now.</p>
            <p class="text-xs text-slate-500 mt-1">Send a video or episode to your Telegram bot to start downloading.</p>
          </div>
        `;
      } else {
        activeList.innerHTML = active.map(item => `
          <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-3">
                <span class="text-2xl">${item.media_type === 'movie' ? '🎬' : '📺'}</span>
                <div>
                  <h3 class="font-semibold text-white text-base">${item.name}</h3>
                  <p class="text-xs text-slate-400 capitalize">${item.media_type} Mode &bull; Status: <span class="text-blue-400 font-medium">${item.status}</span></p>
                </div>
              </div>
              <div class="text-right flex items-center space-x-4">
                <div>
                  <span class="text-lg font-bold text-blue-400">${item.percent}%</span>
                  <p class="text-xs text-slate-400">${item.speed_str} &bull; ETA: ${item.eta_str}</p>
                </div>
                <button onclick="cancelDownload('${item.id}')" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-500/15 text-rose-400 hover:bg-rose-500/30 border border-rose-500/30 transition">Cancel</button>
              </div>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
              <div class="bg-gradient-to-r from-blue-600 to-indigo-500 h-2.5 rounded-full transition-all duration-300" style="width: ${item.percent}%"></div>
            </div>
          </div>
        `).join('');
      }

      // History Table
      const historyTbody = document.getElementById('history-tbody');
      if (history.length === 0) {
        historyTbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-slate-500">No recent history yet.</td></tr>`;
      } else {
        historyTbody.innerHTML = history.map(item => `
          <tr class="hover:bg-slate-800/40 transition">
            <td class="py-3 px-4 font-medium text-white">${item.name}</td>
            <td class="py-3 px-4 uppercase text-xs font-semibold text-slate-400">${item.media_type}</td>
            <td class="py-3 px-4">
              <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${item.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}">
                ${item.status}
              </span>
            </td>
            <td class="py-3 px-4 text-xs text-slate-400">${item.completed_at ? new Date(item.completed_at * 1000).toLocaleString() : '--'}</td>
          </tr>
        `).join('');
      }
    }

    async function loadStats() {
      try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        document.getElementById('stat-movies').textContent = data.movies_count;
        document.getElementById('stat-shows').textContent = data.shows_count;
        
        let serverText = [];
        if (data.jellyfin_configured) serverText.push('Jellyfin ✅');
        if (data.plex_configured) serverText.push('Plex ✅');
        document.getElementById('stat-servers').textContent = serverText.length > 0 ? serverText.join(' & ') : 'None Configured';
      } catch (e) {
        console.error(e);
      }
    }

    async function cancelDownload(taskId) {
      if (!confirm("Are you sure you want to cancel this download?")) return;
      try {
        const res = await fetch('/api/downloads/' + encodeURIComponent(taskId) + '/cancel', { method: 'POST' });
        if (res.ok) {
          console.log("Download cancel requested for", taskId);
        }
      } catch (e) {
        console.error("Failed to cancel download:", e);
      }
    }

    async function loadLibrary() {
      try {
        const res = await fetch('/api/library');
        libraryData = await res.json();
        filterLibrary();
      } catch (e) {
        console.error(e);
      }
    }

    function filterLibrary() {
      const q = (document.getElementById('lib-search').value || '').toLowerCase();
      const filtered = libraryData.filter(item => {
        const name = (item.movie_name || item.show_name || item.filename || '').toLowerCase();
        return name.includes(q);
      });

      const tbody = document.getElementById('library-tbody');
      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-slate-500">No media found.</td></tr>`;
        return;
      }

      tbody.innerHTML = filtered.map(item => `
        <tr class="hover:bg-slate-800/40 transition">
          <td class="py-3 px-4 font-semibold text-white">${item.type === 'movie' ? item.movie_name : item.show_name}</td>
          <td class="py-3 px-4 uppercase text-xs text-slate-400">${item.type}</td>
          <td class="py-3 px-4 text-xs text-slate-300">${item.type === 'show' ? `Season ${item.season} &bull; Ep ${item.episode}` : 'N/A'}</td>
          <td class="py-3 px-4 text-xs font-mono text-slate-400">${item.filename}</td>
          <td class="py-3 px-4 text-xs text-slate-400">${item.uploaded_at ? item.uploaded_at.substring(0, 19).replace('T', ' ') : '--'}</td>
        </tr>
      `).join('');
    }

    async function loadConfig() {
      try {
        const res = await fetch('/api/config');
        const data = await res.json();
        for (const [k, v] of Object.entries(data)) {
          const input = document.getElementById('cfg-' + k);
          if (input) input.value = v;
        }
        if (!document.getElementById('cfg-WEB_USERNAME').value) {
          document.getElementById('cfg-WEB_USERNAME').value = 'admin';
        }
        const badge = document.getElementById('auth-status-badge');
        if (badge) {
          if (data.WEB_PASSWORD) {
            badge.className = "px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
            badge.textContent = "🔒 Password Protected";
          } else {
            badge.className = "px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20";
            badge.textContent = "🔓 No Password (Open Access)";
          }
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function saveConfig() {
      const alertDiv = document.getElementById('cfg-alert');
      alertDiv.className = "mt-4 p-3 rounded-lg text-sm bg-blue-500/20 text-blue-300 border border-blue-500/30";
      alertDiv.textContent = "Saving configuration...";
      alertDiv.classList.remove('hidden');

      const payload = {
        BOT_TOKEN: document.getElementById('cfg-BOT_TOKEN').value,
        ADMIN_USER_ID: document.getElementById('cfg-ADMIN_USER_ID').value,
        API_ID: document.getElementById('cfg-API_ID').value,
        API_HASH: document.getElementById('cfg-API_HASH').value,
        TELETHON_SOURCE_CHAT: document.getElementById('cfg-TELETHON_SOURCE_CHAT').value,
        MOVIES_DIR: document.getElementById('cfg-MOVIES_DIR').value,
        SHOWS_DIR: document.getElementById('cfg-SHOWS_DIR').value,
        JELLYFIN_URL: document.getElementById('cfg-JELLYFIN_URL').value,
        JELLYFIN_API_KEY: document.getElementById('cfg-JELLYFIN_API_KEY').value,
        PLEX_URL: document.getElementById('cfg-PLEX_URL').value,
        PLEX_TOKEN: document.getElementById('cfg-PLEX_TOKEN').value,
        WEB_USERNAME: document.getElementById('cfg-WEB_USERNAME')?.value || 'admin',
        WEB_PASSWORD: document.getElementById('cfg-WEB_PASSWORD')?.value || '',
        LOG_LEVEL: document.getElementById('cfg-LOG_LEVEL').value,
      };

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
          alertDiv.className = "mt-4 p-3 rounded-lg text-sm bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
          alertDiv.textContent = "Configuration saved successfully!";
        } else {
          alertDiv.className = "mt-4 p-3 rounded-lg text-sm bg-rose-500/20 text-rose-300 border border-rose-500/30";
          alertDiv.textContent = "Error saving config: " + (result.detail || "Unknown error");
        }
      } catch (e) {
        alertDiv.className = "mt-4 p-3 rounded-lg text-sm bg-rose-500/20 text-rose-300 border border-rose-500/30";
        alertDiv.textContent = "Failed connecting to server: " + e.message;
      }
    }

    // Startup
    connectWS();
    loadStats();
    setInterval(loadStats, 10000);
  </script>
</body>
</html>
"""


@app.api_route("/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def login_get(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    username = settings.web_username or "admin"
    content = LOGIN_HTML.replace("{error_placeholder}", "").replace("{username_val}", username)
    return HTMLResponse(content=content)


@app.post("/login")
async def login_post(request: Request):
    username = ""
    password = ""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        username = payload.get("username", "")
        password = payload.get("password", "")
    else:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body)
        username = parsed.get("username", [""])[0]
        password = parsed.get("password", [""])[0]

    expected_user = settings.web_username or "admin"
    expected_pass = settings.web_password or ""

    user_valid = secrets.compare_digest(username.strip(), expected_user)
    pass_valid = secrets.compare_digest(password, expected_pass)

    if user_valid and pass_valid:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="tel_session",
            value=get_auth_token(),
            httponly=True,
            samesite="lax",
            path="/",
            max_age=86400 * 30,
        )
        return response

    error_html = """
    <div class="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
      <span class="text-rose-400">⚠️</span> Invalid username or password.
    </div>
    """
    content = LOGIN_HTML.replace("{error_placeholder}", error_html).replace("{username_val}", username or expected_user)
    return HTMLResponse(content=content, status_code=401)


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("tel_session", path="/")
    return response


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def get_index():
    return HTMLResponse(content=HTML_CONTENT)


@app.get("/api/downloads")
async def get_downloads():
    return JSONResponse(tracker.get_all())


@app.post("/api/downloads/{task_id}/cancel")
async def cancel_download_endpoint(task_id: str):
    success = tracker.cancel_task(task_id)
    if success:
        return {"status": "cancelled", "task_id": task_id}
    tracker.set_status(task_id, "failed", "Cancelled via Web UI")
    return {"status": "marked_failed", "task_id": task_id}


@app.websocket("/ws/downloads")
async def websocket_downloads(websocket: WebSocket):
    cookie_token = websocket.cookies.get("tel_session")
    query_token = websocket.query_params.get("auth")
    valid = (cookie_token and secrets.compare_digest(cookie_token, get_auth_token())) or (
        query_token and secrets.compare_digest(query_token, get_auth_token())
    )
    if not valid:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    # Send immediate state
    await websocket.send_json(tracker.get_all())
    q = tracker.subscribe()
    try:
        while True:
            # Wait for tracker update or send periodic keepalive
            try:
                data = await asyncio.wait_for(q.get(), timeout=2.0)
                await websocket.send_json(data)
            except asyncio.TimeoutError:
                await websocket.send_json(tracker.get_all())
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        tracker.unsubscribe(q)


@app.get("/api/stats")
async def get_stats():
    from database.sqlite import get_db
    from database.repositories.uploads_repo import UploadsRepository

    db = await get_db(settings.sqlite_path)
    repo = UploadsRepository(db.conn)
    movies = await repo.get_movies()
    shows = await repo.get_shows()

    return {
        "movies_count": len(movies),
        "shows_count": len(shows),
        "jellyfin_configured": bool(settings.jellyfin_url and settings.jellyfin_api_key),
        "plex_configured": bool(settings.plex_url and settings.plex_token),
    }


@app.get("/api/library")
async def get_library():
    from database.sqlite import get_db
    from database.repositories.uploads_repo import UploadsRepository

    db = await get_db(settings.sqlite_path)
    repo = UploadsRepository(db.conn)
    items = await repo.get_recent_uploads(limit=200)
    return JSONResponse(items)


@app.get("/api/config")
async def get_config():
    # Read current .env
    env_path = ".env"
    cfg = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")

    if not cfg.get("WEB_USERNAME"):
        cfg["WEB_USERNAME"] = settings.web_username or "admin"
    if "WEB_PASSWORD" not in cfg:
        cfg["WEB_PASSWORD"] = settings.web_password or ""

    return JSONResponse(cfg)


class ConfigPayload(BaseModel):
    BOT_TOKEN: str
    ADMIN_USER_ID: str
    API_ID: str
    API_HASH: str
    TELETHON_SOURCE_CHAT: str = ""
    MOVIES_DIR: str
    SHOWS_DIR: str
    JELLYFIN_URL: str = ""
    JELLYFIN_API_KEY: str = ""
    PLEX_URL: str = ""
    PLEX_TOKEN: str = ""
    WEB_USERNAME: str = "admin"
    WEB_PASSWORD: str = ""
    LOG_LEVEL: str = "INFO"


@app.post("/api/config")
async def save_config(payload: ConfigPayload):
    # Update in-memory settings
    settings.web_username = payload.WEB_USERNAME or "admin"
    settings.web_password = payload.WEB_PASSWORD
    settings.log_level = payload.LOG_LEVEL

    env_path = ".env"
    existing_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    updates = payload.model_dump()
    new_lines = []
    updated_keys = set()

    for line in existing_lines:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#") and "=" in trimmed:
            k = trimmed.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                updated_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    response = JSONResponse({"status": "saved"})
    response.set_cookie(
        key="tel_session",
        value=get_auth_token(),
        httponly=True,
        samesite="lax",
        path="/",
        max_age=86400 * 30,
    )
    return response
