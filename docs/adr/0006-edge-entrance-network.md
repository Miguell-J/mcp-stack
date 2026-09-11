# ADR 0006: A separate entrance network for the native edge

Status: superseded by ADR 0007; originally accepted

Docker 29 did not publish the configured localhost port for an edge attached
only to an internal bridge: HostConfig contained the binding, but
NetworkSettings.Ports reported null. In-container health checks still passed.

Only gateway-edge therefore joins a normal entrance bridge in addition to the
internal scientific network. Its only published port still binds 127.0.0.1.
MCP One, the compatibility bridge, collector and scientific adapters retain
internal-only networking and no published ports. No host networking is used.

The edge has potential outbound network access; its configured upstream remains
the internal MCP One URL. This tradeoff is preferable to giving every downstream
external egress or relying on host-specific Docker port behavior. Host-side E2E
tests complement container health checks to prevent recurrence.
