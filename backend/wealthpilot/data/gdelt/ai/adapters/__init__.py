"""Provider adapters for the AI-assisted annotation pipeline. **Nothing in this package is registered or enabled.**

A module here may define a provider class and a ``build`` factory, but it never writes to ``provider.ADAPTERS`` and is never
imported by the pipeline. Registering an adapter, lifting the build lock, creating Gate A to D records and an explicit
execution authorisation are separate, later, owner-controlled steps.
"""
