"""Builds the MCP server and the ASGI app Vercel serves."""
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from flask_client import FlaskClient
from login import make_login_handlers
from oauth import SCOPE, SmallWinsOAuthProvider
from tools import register_tools

INSTRUCTIONS = (
    "Small Wins is a personal log of accomplishments grouped into topics "
    "(books read, runs, hikes, ...). Call list_topics first to learn topic "
    "slugs and field keys. Dates are YYYY-MM-DD."
)


def build_server(config, make_client=None):
    provider = SmallWinsOAuthProvider(config)
    if make_client is None:
        def make_client():
            return FlaskClient(config.api_url, config.service_token)

    mcp = MCPServer(
        name="Small Wins",
        instructions=INSTRUCTIONS,
        auth_server_provider=provider,
        auth=AuthSettings(
            issuer_url=config.base_url,
            resource_server_url=f"{config.base_url}/mcp",
            validate_token_resource=False,  # we only ever issue tokens for this server
            required_scopes=[SCOPE],
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
            ),
        ),
    )
    show, submit = make_login_handlers(provider, config.admin_password_hash)
    mcp.custom_route("/oauth/login", methods=["GET"])(show)
    mcp.custom_route("/oauth/login", methods=["POST"])(submit)
    register_tools(mcp, make_client)
    return mcp


def create_app(config, make_client=None):
    """ASGI app that starts the SDK's session manager per request.

    The SDK only works once its lifespan has run, and serverless platforms
    may never send lifespan events. Stateless mode keeps nothing between
    requests, so building a fresh app per request is cheap and always safe.
    """
    mcp = build_server(config, make_client)
    # Host/Origin pinning guards servers on localhost against DNS rebinding.
    # This one is public and every MCP request needs a bearer token, so the
    # check would only block browser-based clients and preview URLs.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        inner = mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=security)
        async with inner.router.lifespan_context(inner):
            await inner(scope, receive, send)

    return app
