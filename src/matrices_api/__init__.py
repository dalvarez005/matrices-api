def main() -> None:
    """Servidor de desarrollo: `uv run matrices-api`."""
    import uvicorn

    uvicorn.run("matrices_api.app:app", host="0.0.0.0", port=5120, reload=True)
