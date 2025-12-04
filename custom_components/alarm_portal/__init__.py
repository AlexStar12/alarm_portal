import logging
import aiohttp
from datetime import datetime, timezone

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, CONF_SERVER_URL, CONF_API_TOKEN, CONF_ALARM_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SERVER_URL): cv.url,
                vol.Required(CONF_API_TOKEN): cv.string,
                vol.Required(CONF_ALARM_ENTITY_ID): cv.entity_id,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Alarm Portal integration via YAML."""
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error("No configuration found for %s in configuration.yaml", DOMAIN)
        return False

    server_url = conf[CONF_SERVER_URL].rstrip("/")
    api_token = conf[CONF_API_TOKEN]
    alarm_entity_id = conf[CONF_ALARM_ENTITY_ID]

    session = aiohttp.ClientSession()

    async def send_alarm_event(new_state_str: str):
        url = f"{server_url}/api/alarm_event.php"
        payload = {
            "token": api_token,
            "entity_id": alarm_entity_id,
            "state": new_state_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error(
                        "Alarm Portal: HTTP %s: %s", resp.status, text[:200]
                    )
                else:
                    _LOGGER.debug("Alarm Portal: event sent successfully")
        except Exception as e:
            _LOGGER.exception("Alarm Portal: error sending event: %s", e)

    @callback
    async def alarm_state_changed(event):
        """Called when the alarm entity changes state."""
        entity = event.data.get("entity_id")
        if entity != alarm_entity_id:
            return

        new_state_obj = event.data.get("new_state")
        if new_state_obj is None:
            return

        new_state_str = new_state_obj.state
        _LOGGER.debug("Alarm entity changed to %s", new_state_str)

        # On envoie seulement pour certains états
        if new_state_str in ("triggered", "armed_away", "disarmed"):
            await send_alarm_event(new_state_str)

    async_track_state_change_event(
        hass,
        [alarm_entity_id],
        alarm_state_changed,
    )

    _LOGGER.info("Alarm Portal integration initialized")
    return True
