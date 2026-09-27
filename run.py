import os

try:
    #usa los certificados de Windows/macOS para requests (evita CERTIFICATE_VERIFY_FAILED detrás de antivirus/proxy)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from app import create_app

app_flask = create_app()

if __name__ == "__main__":
    app_flask.run(host="127.0.0.1", port=int(os.getenv("PORT", 5000)))
