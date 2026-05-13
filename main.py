"""8D Audio Studio — entry point."""

from ui.app import App


def main() -> None:
    app = App()
    app.setup()
    app.run()


if __name__ == "__main__":
    main()
