"""Sensor platform for the MET Cloud Layers integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import MetCloudsConfigEntry, MetCloudsDataUpdateCoordinator
from .model import MetCloudsData


@dataclass(frozen=True, kw_only=True)
class MetCloudsSensorEntityDescription(SensorEntityDescription):
    """Describes a MET Cloud Layers sensor and how to derive its value."""

    value_fn: Callable[[MetCloudsData, datetime], StateType | datetime]
    attributes_fn: Callable[[MetCloudsData], dict] | None = None


def _round1(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


SENSOR_DESCRIPTIONS: tuple[MetCloudsSensorEntityDescription, ...] = (
    MetCloudsSensorEntityDescription(
        key="cloud_total",
        translation_key="cloud_total",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: _round1(data.current(now, lambda p: p.total)),
        attributes_fn=lambda data: {
            "updated_at": data.updated_at.isoformat() if data.updated_at else None,
            "hourly": data.hourly_attribute(),
        },
    ),
    MetCloudsSensorEntityDescription(
        key="cloud_low",
        translation_key="cloud_low",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: _round1(data.current(now, lambda p: p.low)),
    ),
    MetCloudsSensorEntityDescription(
        key="cloud_medium",
        translation_key="cloud_medium",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: _round1(data.current(now, lambda p: p.medium)),
    ),
    MetCloudsSensorEntityDescription(
        key="cloud_high",
        translation_key="cloud_high",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: _round1(data.current(now, lambda p: p.high)),
    ),
    MetCloudsSensorEntityDescription(
        key="fog",
        translation_key="fog",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: _round1(data.current(now, lambda p: p.fog)),
    ),
    MetCloudsSensorEntityDescription(
        key="transmittance_now",
        translation_key="transmittance_now",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: data.transmittance_now(now),
    ),
    MetCloudsSensorEntityDescription(
        key="cloud_low_next_3h",
        translation_key="cloud_low_next_3h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: data.cloud_low_next_3h(now),
    ),
    MetCloudsSensorEntityDescription(
        key="transmittance_next_3h",
        translation_key="transmittance_next_3h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: data.transmittance_next_3h(now),
    ),
    MetCloudsSensorEntityDescription(
        key="sky_quality_today_remaining",
        translation_key="sky_quality_today_remaining",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: data.sky_quality_today_remaining(now),
    ),
    MetCloudsSensorEntityDescription(
        key="sky_quality_tomorrow",
        translation_key="sky_quality_tomorrow",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data, now: data.sky_quality_tomorrow(now),
    ),
    MetCloudsSensorEntityDescription(
        key="forecast_updated",
        translation_key="forecast_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, now: data.updated_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MetCloudsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MET Cloud Layers sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        MetCloudsSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class MetCloudsSensor(
    CoordinatorEntity[MetCloudsDataUpdateCoordinator], SensorEntity
):
    """A MET Cloud Layers sensor backed by the shared coordinator data."""

    entity_description: MetCloudsSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: MetCloudsDataUpdateCoordinator,
        description: MetCloudsSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Locationforecast cloud layers",
            configuration_url="https://api.met.no/weatherapi/locationforecast/2.0/documentation",
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the derived value for the current time."""
        return self.entity_description.value_fn(self.coordinator.data, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra attributes (hourly series) when defined."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
