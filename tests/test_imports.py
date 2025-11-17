def test_package_imports() -> None:
    import rpi_simple_debugger

    app = rpi_simple_debugger.create_app()
    assert app.title == "rpi-simple-debugger"
