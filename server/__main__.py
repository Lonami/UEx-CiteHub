def main():
    import logging
    from . import server

    app = server.create_app()
    logging.info("server application is up and running")
    try:
        app.run()
    finally:
        logging.info("server was shut down")


if __name__ == "__main__":
    main()
