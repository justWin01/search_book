import json
import ssl
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import firebase_admin
from firebase_admin import credentials, db

# Firebase setup
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://my-book-database-4382f-default-rtdb.firebaseio.com/'
})

PORT = 8000
context = ssl._create_unverified_context()  # Bypass SSL verification (for Open Library)

class BookHandler(BaseHTTPRequestHandler):

    def _send_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/books":
            search_term = query.get("q", [""])[0]
            print(f"[INFO] Book search query: {search_term}")

            if not search_term:
                self._send_response(400, {"error": "Missing query"})
                return

            url = f"https://openlibrary.org/search.json?q={urllib.parse.quote(search_term)}"
            print(f"[INFO] Fetching from: {url}")

            try:
                with urllib.request.urlopen(url, context=context) as res:
                    raw = res.read()
                    print("[INFO] Received response from Open Library")
                    data = json.loads(raw)

                books = [{
                    "title": doc.get("title"),
                    "author": ", ".join(doc.get("author_name", ["Unknown"])),
                    "year": doc.get("first_publish_year", "N/A")
                } for doc in data.get("docs", [])[:10]]

                self._send_response(200, books)
            except Exception as e:
                print(f"[ERROR] Open Library fetch failed: {e}")
                self._send_response(500, {"error": str(e)})

        elif path == "/saved":
            print("[INFO] Retrieving saved books from Firebase")
            try:
                ref = db.reference("saved_books")
                data = ref.get()
                books = list(data.values()) if data else []
                self._send_response(200, books)
            except Exception as e:
                print(f"[ERROR] Firebase fetch failed: {e}")
                self._send_response(500, {"error": str(e)})

        else:
            self._send_response(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/save":
            print("[INFO] Saving book to Firebase...")
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                book_data = json.loads(body)
                print(f"[DEBUG] Book to save: {book_data}")

                ref = db.reference("saved_books")
                ref.push(book_data)

                self._send_response(200, {"status": "Book saved to Firebase"})
            except Exception as e:
                print(f"[ERROR] Save failed: {e}")
                self._send_response(500, {"error": str(e)})
        else:
            self._send_response(404, {"error": "Not found"})


def run():
    print(f"[SERVER] Running at http://localhost:{PORT}")
    server = HTTPServer(("", PORT), BookHandler)
    server.serve_forever()

if __name__ == "__main__":
    run()
