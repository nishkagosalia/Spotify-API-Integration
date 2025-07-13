# api/index.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv
import requests, os


app = FastAPI()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

TOKENS = {}

@app.get("/")
def root():
    return {"message": "Hello from FastAPI on Vercel"}

def get_access_token(refresh_token):
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = requests.utils.quote(auth_str.encode("utf-8").decode("latin1"))

    res = requests.post("https://accounts.spotify.com/api/token", data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    })

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Token refresh failed")

    return res.json()["access_token"]

@app.get("/login")
def login():
    scope = "user-read-playback-state user-modify-playback-state user-read-currently-playing user-top-read"
    url = (
        f"https://accounts.spotify.com/authorize?response_type=code"
        f"&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(url)

@app.get("/callback")
def callback(code: str):
    res = requests.post("https://accounts.spotify.com/api/token", data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    })

    if res.status_code != 200:
        raise HTTPException(status_code=500, detail="Token exchange failed")

    data = res.json()
    TOKENS["refresh_token"] = data["refresh_token"]
    return JSONResponse({"message": "Login successful", "refresh_token": data["refresh_token"]})

@app.get("/spotify/top-tracks")
def top_tracks():
    refresh_token = TOKENS.get("refresh_token")
    token = get_access_token(refresh_token)

    res = requests.get("https://api.spotify.com/v1/me/top/tracks?limit=10", headers={
        "Authorization": f"Bearer {token}"
    })

    return [
        {
            "name": t["name"],
            "artist": ", ".join([a["name"] for a in t["artists"]]),
            "uri": t["uri"]
        } for t in res.json()["items"]
    ]

@app.get("/spotify/now-playing")
def now_playing():
    refresh_token = TOKENS.get("refresh_token")
    token = get_access_token(refresh_token)

    res = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers={
        "Authorization": f"Bearer {token}"
    })

    if res.status_code == 204:
        return {"status": "Nothing is playing"}

    data = res.json()
    return {
        "name": data["item"]["name"],
        "artist": ", ".join([a["name"] for a in data["item"]["artists"]]),
        "is_playing": data["is_playing"]
    }

@app.post("/spotify/play")
async def play_track(request: Request):
    body = await request.json()
    uri = body.get("uri")
    token = get_access_token(TOKENS.get("refresh_token"))

    requests.put("https://api.spotify.com/v1/me/player/play", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }, json={"uris": [uri]})

    return {"status": f"Playing {uri}"}

@app.post("/spotify/pause")
def pause_track():
    token = get_access_token(TOKENS.get("refresh_token"))

    requests.put("https://api.spotify.com/v1/me/player/pause", headers={
        "Authorization": f"Bearer {token}"
    })

    return {"status": "Paused"}
