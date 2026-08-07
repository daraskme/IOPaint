# Distribution helpers

- `install_windows.bat` creates `.iopaint-env`, installs the appropriate PyTorch build, and installs `iopaint-ng`.
- `start_windows.bat` activates that environment and starts IOPaint on port 8080.
- `build_docker.sh [VERSION]` builds `iopaint-ng:VERSION-cuda` and `iopaint-ng:VERSION-cpu`.
- `check_package_contents.py dist` verifies that a wheel and sdist contain the embedded frontend and model configuration files.
