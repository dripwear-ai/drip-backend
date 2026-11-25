"""Opt-in FastAPI dependency factory. No routes are protected or added here."""

import re
from collections.abc import Callable

from fastapi import Request

from drip.identity.contracts import ExternalPrincipal
from drip.identity.verifier import MAX_TOKEN_BYTES, Auth0TokenVerifier, AuthenticationFailed


def external_principal_dependency(
    verifier: Auth0TokenVerifier,
) -> Callable[[Request], ExternalPrincipal]:
    # A synchronous dependency is run in FastAPI's threadpool, not the event loop.
    def dependency(request: Request) -> ExternalPrincipal:
        values = request.headers.getlist("authorization")
        if len(values) != 1:
            raise AuthenticationFailed()
        if len(values[0]) > MAX_TOKEN_BYTES + 16:
            raise AuthenticationFailed()
        match = re.fullmatch(
            r"(?i:Bearer) +([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", values[0]
        )
        if match is None:
            raise AuthenticationFailed()
        return verifier.verify(match[1])

    return dependency
