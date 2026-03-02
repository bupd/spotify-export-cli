#!/usr/bin/env python3
"""Export Spotify liked songs and playlists to markdown files."""

import http.server
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token.json")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API = "https://api.spotify.com/v1"
SCOPES = "user-library-read playlist-read-private playlist-read-collaborative"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("No config.json found. Creating one.")
        client_id = input("Spotify Client ID: ").strip()
        client_secret = input("Spotify Client Secret: ").strip()
        redirect_uri = input("Redirect URI [http://127.0.0.1:3000/callback]: ").strip()
        if not redirect_uri:
            redirect_uri = "http://127.0.0.1:3000/callback"
        config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return config
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_token(token_data):
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)


def load_token():
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return json.load(f)
    return None


def get_auth_code(config):
    """Run a tiny HTTP server to capture the OAuth callback."""
    parsed = urllib.parse.urlparse(config["redirect_uri"])
    port = parsed.port or 3000
    auth_code = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if "code" in params:
                auth_code["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Done! You can close this tab.</h1>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code parameter")

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)

    params = urllib.parse.urlencode({
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": config["redirect_uri"],
        "scope": SCOPES,
    })
    url = f"{SPOTIFY_AUTH_URL}?{params}"
    print(f"Opening browser for Spotify login...")
    print(f"If it doesn't open, visit: {url}")
    webbrowser.open(url)

    server.handle_request()
    server.server_close()
    return auth_code.get("code")


def exchange_code(config, code):
    """Exchange auth code for access token."""
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }).encode()
    req = urllib.request.Request(SPOTIFY_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read())
    save_token(token_data)
    return token_data


def refresh_token(config, token_data):
    """Refresh an expired access token."""
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }).encode()
    req = urllib.request.Request(SPOTIFY_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        new_data = json.loads(resp.read())
    if "refresh_token" not in new_data:
        new_data["refresh_token"] = token_data["refresh_token"]
    save_token(new_data)
    return new_data


def api_get(token, endpoint, params=None):
    """Make a GET request to the Spotify API."""
    url = endpoint if endpoint.startswith("http") else f"{SPOTIFY_API}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API error {e.code}: {body}", file=sys.stderr)
        raise


def fetch_all_items(token, endpoint, params=None, limit=50):
    """Paginate through all items from a Spotify API endpoint."""
    if params is None:
        params = {}
    params["limit"] = limit
    params["offset"] = 0
    items = []
    while True:
        data = api_get(token, endpoint, params)
        items.extend(data.get("items", []))
        total = data.get("total", 0)
        print(f"  fetched {len(items)}/{total}", end="\r")
        if data.get("next") is None:
            break
        params["offset"] += limit
    print()
    return items


def get_token(config):
    """Get a valid access token, refreshing or re-authing as needed."""
    token_data = load_token()
    if token_data:
        try:
            api_get(token_data["access_token"], "/me")
            return token_data["access_token"]
        except Exception:
            try:
                token_data = refresh_token(config, token_data)
                return token_data["access_token"]
            except Exception:
                pass
    code = get_auth_code(config)
    if not code:
        print("Failed to get auth code.", file=sys.stderr)
        sys.exit(1)
    token_data = exchange_code(config, code)
    return token_data["access_token"]


def format_track(i, item, is_liked=False):
    """Format a single track as a markdown list item."""
    track = item["track"] if "track" in item else item
    name = track.get("name", "Unknown")
    artists = ", ".join(a["name"] for a in track.get("artists", []))
    album = track.get("album", {}).get("name", "")
    duration_ms = track.get("duration_ms", 0)
    mins, secs = divmod(duration_ms // 1000, 60)
    duration = f"{mins}:{secs:02d}"
    added_at = item.get("added_at", "")[:10] if is_liked else ""
    line = f"{i}. **{name}** - {artists}"
    if album:
        line += f" ({album})"
    line += f" [{duration}]"
    if added_at:
        line += f" - added {added_at}"
    return line


def export_liked_songs(token, output_dir):
    """Export liked songs to a markdown file."""
    print("Fetching liked songs...")
    items = fetch_all_items(token, "/me/tracks")
    if not items:
        print("No liked songs found.")
        return
    lines = [f"# Liked Songs ({len(items)} tracks)\n"]
    for i, item in enumerate(items, 1):
        lines.append(format_track(i, item, is_liked=True))
    path = os.path.join(output_dir, "liked-songs.md")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Saved {len(items)} liked songs to {path}")


def export_playlists(token, output_dir):
    """Export all playlists to markdown files."""
    print("Fetching playlists...")
    playlists = fetch_all_items(token, "/me/playlists")
    if not playlists:
        print("No playlists found.")
        return
    print(f"Found {len(playlists)} playlists\n")

    index_lines = [f"# Playlists ({len(playlists)})\n"]

    for pl in playlists:
        name = pl.get("name", "Untitled")
        playlist_id = pl["id"]
        total = pl["tracks"]["total"]
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in name).strip()
        safe_name = safe_name.replace(" ", "-").lower()
        filename = f"{safe_name}.md"

        index_lines.append(f"- [{name}]({filename}) ({total} tracks)")

        print(f"Exporting: {name} ({total} tracks)")
        tracks = fetch_all_items(token, f"/playlists/{playlist_id}/tracks")

        lines = [f"# {name}\n", f"Total: {len(tracks)} tracks\n"]
        for i, item in enumerate(tracks, 1):
            if item.get("track") is None:
                continue
            lines.append(format_track(i, item))
        path = os.path.join(output_dir, filename)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  saved to {path}")

    index_path = os.path.join(output_dir, "playlists-index.md")
    with open(index_path, "w") as f:
        f.write("\n".join(index_lines) + "\n")
    print(f"\nPlaylist index saved to {index_path}")


def main():
    config = load_config()
    token = get_token(config)

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "liked":
            export_liked_songs(token, output_dir)
        elif cmd == "playlists":
            export_playlists(token, output_dir)
        elif cmd == "all":
            export_liked_songs(token, output_dir)
            print()
            export_playlists(token, output_dir)
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: spotify-export.py [liked|playlists|all]")
    else:
        print("Usage: spotify-export.py [liked|playlists|all]")
        print("  liked     - export liked/saved songs")
        print("  playlists - export all playlists")
        print("  all       - export everything")


if __name__ == "__main__":
    main()
