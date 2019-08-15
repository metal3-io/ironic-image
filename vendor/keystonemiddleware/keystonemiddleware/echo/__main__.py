from keystonemiddleware.echo import service


try:
    service.EchoService()
except KeyboardInterrupt:  # nosec
    # The user wants this application to exit.
    pass
