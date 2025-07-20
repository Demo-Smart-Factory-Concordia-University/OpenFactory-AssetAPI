"""
Command-line management script for OpenFactory Routing Layer.

This script provides a simple CLI to manage the routing layer lifecycle:

Commands:
    deploy      - Create the required infrastructure and deploy the routing layer.
    teardown    - Remove deployed infrastructure and clean up resources.
    runserver   - Launch the FastAPI routing layer API using Uvicorn ASGI server.

Usage:
    python -m routing_layer.manage <command>

Example:
    python -m routing_layer.manage deploy
    python -m routing_layer.manage teardown
    python -m routing_layer.manage runserver

Environment Variable:
    OF_ROUTING_UVICORN
        Set automatically to "1" when running the API server to indicate Uvicorn context.
        Set to "0" when running deploy or teardown commands.
"""

import sys
import subprocess


def main():
    """
    Main entrypoint for the manage CLI.

    Parses the first command-line argument and dispatches to the
    appropriate functionality: deploy, teardown, or runserver.

    Raises:
        SystemExit: If no command or an unknown command is provided,
                    exits the program with a usage message.
    """
    if len(sys.argv) < 2:
        print("Usage: python manage.py [deploy|teardown|runserver]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "deploy":
        from routing_layer.deployment.deploy import main as run_deployment
        run_deployment()

    elif command == "teardown":
        from routing_layer.deployment.teardown import main as run_teardown
        run_teardown()

    elif command == "runserver":
        subprocess.run([
            "uvicorn", "routing_layer.app.main:app",
            "--host", "0.0.0.0", "--port", "5555",
            "--log-level", "info"
        ])

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
