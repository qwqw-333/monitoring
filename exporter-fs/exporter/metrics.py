from prometheus_client import Gauge

freeswitch_up = Gauge(
    "freeswitch_up",
    "FreeSWITCH availability",
    ["instance"]
)

freeswitch_calls_active = Gauge(
    "freeswitch_calls_active",
    "Active calls",
    ["instance"]
)

freeswitch_channels_active = Gauge(
    "freeswitch_channels_active",
    "Active channels",
    ["instance"]
)

freeswitch_registrations_active = Gauge(
    "freeswitch_registrations_active",
    "Registered endpoints",
    ["instance"]
)

freeswitch_gateway_up = Gauge(
    "freeswitch_gateway_up",
    "Gateway status",
    ["instance", "gateway"]
)

exporter_target_up = Gauge(
    "exporter_target_up",
    "Exporter target state",
    ["instance"]
)

exporter_last_update = Gauge(
    "exporter_last_update_timestamp",
    "Last successful scrape",
    ["instance"]
)
