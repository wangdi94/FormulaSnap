import uvicorn
from sidecar.api.server import app


def main():
    uvicorn.run(app, host="127.0.0.1", port=8477)


if __name__ == "__main__":
    main()
