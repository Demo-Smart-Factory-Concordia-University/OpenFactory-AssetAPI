"""
Command-line management script for OpenFactory Routing Layer.

This script provides a simple CLI to manage the routing layer lifecycle:

Commands:
    deploy      - Create the required infrastructure and deploy the routing layer.
    teardown    - Remove deployed infrastructure and clean up resources.
    runserver   - Launch the FastAPI routing layer API using Uvicorn ASGI server.
    build       - Build all required Docker images.

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
import uvicorn
import subprocess
from pathlib import Path
from routing_layer.app.config import settings


# Resolve the project root dynamically based on this file's location
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


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
        print("Usage: python manage.py [deploy|teardown|runserver|build]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "deploy":
        from routing_layer.deployment.deploy import main as run_deployment
        run_deployment()

    elif command == "teardown":
        from routing_layer.deployment.teardown import main as run_teardown
        run_teardown()

    elif command == "runserver":
        uvicorn.run("routing_layer.app.main:app",
                    host="0.0.0.0", port=5555,
                    reload=True,
                    log_level=settings.log_level)

    elif command == "build":

        builds = [
            # (Dockerfile relative to project root, image tag, context relative to project root)
            ("routing_layer/Dockerfile", "ofa/routing-layer", "."),
            ("stream_api/non_replicated/Dockerfile", "ofa/stream-api-non-replicated", "stream_api/non_replicated"),
            ("state_api/Dockerfile", "ofa/state-api", "state_api"),
        ]

        for dockerfile_rel, tag, context_rel in builds:
            dockerfile = PROJECT_ROOT.joinpath(dockerfile_rel)
            context = PROJECT_ROOT.joinpath(context_rel)
            print(f"\n🔨 Building image: {tag} from {dockerfile} (context: {context})")

            try:
                subprocess.run([
                    "docker", "build",
                    "-f", dockerfile,
                    "-t", tag,
                    context
                ], check=True)
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to build {tag}")
                sys.exit(e.returncode)

        print("\n✅ All images built successfully.")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
