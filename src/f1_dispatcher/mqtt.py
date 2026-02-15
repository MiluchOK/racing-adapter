"""MQTT publisher for F1 telemetry data."""

import json

import paho.mqtt.client as mqtt

from f1_telemetry.packets import PacketType


class MqttPublisher:
    """Publishes F1 telemetry data to an MQTT broker on granular topics."""

    def __init__(self, host: str = "10.0.0.102", port: int = 1883):
        self._host = host
        self._port = port
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._connected = False

    def connect(self):
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.connect_async(self._host, self._port)
        self._client.loop_start()

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self._connected = True

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False

    def _publish(self, topic: str, payload):
        if not self._connected:
            return
        self._client.publish(topic, payload, qos=0)

    # -- Handler methods registered on the dispatcher --

    def handle_car_telemetry(self, header, data):
        self._publish("f1/steering", str(data.steer))
        self._publish("f1/throttle", str(data.throttle))
        self._publish("f1/brake", str(data.brake))
        self._publish("f1/speed", str(data.speed))
        self._publish("f1/gear", str(data.gear))
        self._publish("f1/rpm", str(data.engine_rpm))
        self._publish("f1/drs", str(data.drs))

    def handle_car_status(self, header, data):
        self._publish("f1/fuel", json.dumps({
            "remaining": data.fuel_remaining,
            "remaining_laps": data.fuel_remaining_laps,
            "mix": data.fuel_mix.name if hasattr(data.fuel_mix, "name") else str(data.fuel_mix),
        }))
        self._publish("f1/ers", json.dumps({
            "store_energy": data.ers_store_energy,
            "deploy_mode": data.ers_deploy_mode.name if hasattr(data.ers_deploy_mode, "name") else str(data.ers_deploy_mode),
        }))
        self._publish("f1/tyres", json.dumps({
            "compound": data.actual_tyre_compound.name if hasattr(data.actual_tyre_compound, "name") else str(data.actual_tyre_compound),
            "age_laps": data.tyre_age_laps,
        }))

    def handle_lap_data(self, header, data):
        self._publish("f1/lap", json.dumps({
            "current_lap": data.current_lap,
            "position": data.position,
            "current_time_ms": data.current_lap_time_ms,
            "last_lap_time_ms": data.last_lap_time_ms,
        }))

    def handle_session(self, header, data):
        self._publish("f1/session", json.dumps({
            "track": data.track.name if hasattr(data.track, "name") else str(data.track),
            "session_type": data.session_type.name if hasattr(data.session_type, "name") else str(data.session_type),
            "weather": data.weather.name if hasattr(data.weather, "name") else str(data.weather),
            "track_temp": data.track_temperature,
            "air_temp": data.air_temperature,
        }))

    def register(self, dispatcher):
        """Register all handlers on an F1Dispatcher instance."""
        dispatcher.on(PacketType.CAR_TELEMETRY, self.handle_car_telemetry)
        dispatcher.on(PacketType.CAR_STATUS, self.handle_car_status)
        dispatcher.on(PacketType.LAP_DATA, self.handle_lap_data)
        dispatcher.on(PacketType.SESSION, self.handle_session)
