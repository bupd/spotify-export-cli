# spotify-export-cli

Export Spotify liked songs and playlists to markdown files.

Zero dependencies - uses Python 3 standard library only.

## Requirements

- Python 3.x
- A Spotify account with **Premium subscription** (required by Spotify to enable Web API access)

## Spotify Developer Setup

1. Go to https://developer.spotify.com/dashboard and log in
2. Click **Create App**
3. Fill in a name and description
4. Set the Redirect URI to `http://127.0.0.1:3000/callback`
5. Under "Which API/SDKs are you planning to use?" select **Web API**
6. Save the app
7. Go to **Settings** and copy your **Client ID** and **Client Secret**
8. Go to **User Management** and add the email address linked to your Spotify account

> Note: Spotify apps are in Development Mode by default. You must explicitly add your Spotify email under User Management or all API calls will return 403.

## Configuration

On first run, the script will prompt for your credentials and create a `config.json`:

```
Spotify Client ID: <your client id>
Spotify Client Secret: <your client secret>
Redirect URI [http://127.0.0.1:3000/callback]: <enter to use default>
```

Credentials are saved locally in `config.json`. Keep this file private - it is gitignored by default.

## Usage

```sh
python3 spotify-export.py liked       # export liked/saved songs
python3 spotify-export.py playlists   # export all playlists
python3 spotify-export.py all         # export everything
```

On first run a browser window will open for Spotify OAuth login. After authorizing, the token is cached in `.token.json` so subsequent runs skip the login step.

Output files are written to `./output/`:

- `liked-songs.md` - all liked songs with artist, album, duration, and date added
- `<playlist-name>.md` - one file per playlist
- `playlists-index.md` - index of all playlists

## Output Format

```md
# Liked Songs (342 tracks)

1. **Song Name** - Artist Name (Album) [3:45] - added 2024-01-15
2. **Another Song** - Artist Name (Album) [4:12] - added 2024-01-10
...
```
