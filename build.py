from PyInstaller.__main__ import run


def main() -> None:
    run(
        [
            "main.py",
            "-F",
            "-w",
            "--clean",
            "--noconfirm",
            "--name",
            "GeekClock",
            "--icon=icon.ico",
            "--add-data",
            "sounds;sounds",
        ]
    )


if __name__ == "__main__":
    main()
