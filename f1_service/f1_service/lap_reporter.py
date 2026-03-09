"""Lap Reporter - POSTs best lap records to the scoreboard API on session end."""

import json
import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv

from .packets import PacketType, Weather, Track, Team, SessionType

load_dotenv()


@dataclass
class _SessionState:
    """Accumulated session state, reset after each report."""
    track: Optional[Track] = None
    weather: Optional[Weather] = None
    session_type: Optional[SessionType] = None
    driver_name: Optional[str] = None
    team: Optional[Team] = None
    best_lap_time_s: float = 0.0
    num_laps: int = 0
    # Session history for player car: {lap_num: (s1_ms, s2_ms, s3_ms)}
    lap_sectors: dict = field(default_factory=dict)
    best_lap_num: int = 0


# Weather enum → API weather string
_WEATHER_MAP = {
    Weather.CLEAR: "clear",
    Weather.LIGHT_CLOUD: "clear",
    Weather.OVERCAST: "cloudy",
    Weather.LIGHT_RAIN: "rain",
    Weather.HEAVY_RAIN: "rain",
    Weather.STORM: "storm",
}

# Track enum → human-readable name (supplement SessionData.track_name)
_TRACK_NAMES = {
    Track.MELBOURNE: "Melbourne",
    Track.PAUL_RICARD: "Paul Ricard",
    Track.SHANGHAI: "Shanghai",
    Track.BAHRAIN: "Sakhir",
    Track.CATALUNYA: "Catalunya",
    Track.MONACO: "Monaco",
    Track.MONTREAL: "Montreal",
    Track.SILVERSTONE: "Silverstone",
    Track.HOCKENHEIM: "Hockenheim",
    Track.HUNGARORING: "Hungaroring",
    Track.SPA: "Spa",
    Track.MONZA: "Monza",
    Track.SINGAPORE: "Singapore",
    Track.SUZUKA: "Suzuka",
    Track.ABU_DHABI: "Abu Dhabi",
    Track.TEXAS: "Texas",
    Track.BRAZIL: "Brazil",
    Track.AUSTRIA: "Austria",
    Track.SOCHI: "Sochi",
    Track.MEXICO: "Mexico",
    Track.BAKU: "Baku",
    Track.ZANDVOORT: "Zandvoort",
    Track.IMOLA: "Imola",
    Track.PORTIMAO: "Portimão",
    Track.JEDDAH: "Jeddah",
    Track.MIAMI: "Miami",
    Track.LAS_VEGAS: "Las Vegas",
    Track.LOSAIL: "Losail",
}


class LapReporter:
    """Listens for session end + final classification and POSTs the best lap to the API."""

    def __init__(self):
        self._api_url = os.environ.get("API_URL", "").rstrip("/")
        self._api_key = os.environ.get("API_KEY", "")
        self._club_id = os.environ.get("CLUB_ID", "")
        self._player_id = os.environ.get("PLAYER_ID", "")
        self._state = _SessionState()

        missing = []
        if not self._api_url:
            missing.append("API_URL")
        if not self._api_key:
            missing.append("API_KEY")
        if not self._club_id:
            missing.append("CLUB_ID")
        if not self._player_id:
            missing.append("PLAYER_ID")
        if missing:
            print(f"[LapReporter] WARNING: missing env vars: {', '.join(missing)} — lap reporting disabled")
            self._enabled = False
        else:
            self._enabled = True
            print(f"[LapReporter] Reporting to {self._api_url}/api/racing/lap-record")

    def register(self, dispatcher):
        """Register handlers on an F1Dispatcher instance."""
        dispatcher.on(PacketType.SESSION, self._handle_session)
        dispatcher.on(PacketType.PARTICIPANTS, self._handle_participants)
        dispatcher.on(PacketType.SESSION_HISTORY, self._handle_session_history)
        dispatcher.on(PacketType.EVENT, self._handle_event)
        dispatcher.on(PacketType.FINAL_CLASSIFICATION, self._handle_final_classification)

    def _handle_session(self, header, data):
        self._state.track = data.track
        self._state.weather = data.weather
        self._state.session_type = data.session_type

    def _handle_participants(self, header, data):
        self._state.driver_name = data.name
        self._state.team = data.team

    def _handle_session_history(self, header, data):
        # Only cache the player car's history
        if data.car_index != header.player_car_index:
            return
        self._state.best_lap_num = data.best_lap_time_lap_num
        for i, lap in enumerate(data.lap_history):
            if lap.lap_time_ms > 0:
                self._state.lap_sectors[i + 1] = (
                    lap.sector1_time_ms,
                    lap.sector2_time_ms,
                    lap.sector3_time_ms,
                )

    def _handle_event(self, header, data):
        if data.event_code == "SEND":
            print("[LapReporter] Session ended — waiting for final classification...")

    def _handle_final_classification(self, header, data):
        if not self._enabled:
            return

        if data.best_lap_time <= 0:
            print("[LapReporter] No valid best lap time — skipping")
            self._reset()
            return

        self._state.best_lap_time_s = data.best_lap_time
        self._state.num_laps = data.num_laps
        self._report()
        self._reset()

    def _report(self):
        track_name = _TRACK_NAMES.get(self._state.track, str(self._state.track))
        car_name = self._state.team.name.replace("_", " ").title() if isinstance(self._state.team, Team) else str(self._state.team)
        weather = _WEATHER_MAP.get(self._state.weather)
        session_label = self._state.session_type.name.replace("_", " ").title() if isinstance(self._state.session_type, SessionType) else "Unknown"

        lap_time_ms = int(self._state.best_lap_time_s * 1000)

        payload = {
            "clubId": self._club_id,
            "playerId": self._player_id,
            "trackName": track_name,
            "carName": car_name,
            "lapTimeMs": lap_time_ms,
            "totalLaps": self._state.num_laps,
            "simPlatform": "F1 24",
            "notes": f"Session: {session_label}",
        }

        # Add sector times if available
        sectors = self._state.lap_sectors.get(self._state.best_lap_num)
        if sectors:
            payload["sectorTimes"] = {
                "s1": sectors[0],
                "s2": sectors[1],
                "s3": sectors[2],
            }

        if weather:
            payload["weather"] = weather

        print(f"[LapReporter] Posting lap record: {json.dumps(payload, indent=2)}")

        try:
            req = Request(
                f"{self._api_url}/api/racing/lap-record",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            with urlopen(req) as resp:
                body = json.loads(resp.read().decode())
                print(f"[LapReporter] Lap record created ({resp.status}): {body.get('id', body)}")
        except HTTPError as e:
            print(f"[LapReporter] Failed ({e.code}): {e.read().decode()}")
        except URLError as e:
            print(f"[LapReporter] Connection error: {e.reason}")

    def _reset(self):
        self._state = _SessionState()
        print("[LapReporter] Session state reset — ready for next session")
