import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import wifi


class HttpResponseParseTest(unittest.TestCase):
    def test_single_chunk_response(self):
        chunks = [b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":true}"]
        status, body = wifi._parse_response_chunks(chunks)
        self.assertEqual(status, 200)
        self.assertEqual(body, b'{"ok":true}')

    def test_split_header_boundary_across_chunks(self):
        chunks = [
            b"HTTP/1.1 200 OK\r\nX-A: 1\r",
            b"\n\r\n{\"a\":",
            b"123}",
        ]
        status, body = wifi._parse_response_chunks(chunks)
        self.assertEqual(status, 200)
        self.assertEqual(body, b'{"a":123}')

    def test_non_200_status(self):
        chunks = [b"HTTP/1.0 503 Service Unavailable\r\n\r\nbusy"]
        status, body = wifi._parse_response_chunks(chunks)
        self.assertEqual(status, 503)
        self.assertEqual(body, b"busy")

    def test_empty_body(self):
        chunks = [b"HTTP/1.0 204 No Content\r\n\r\n"]
        status, body = wifi._parse_response_chunks(chunks)
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")

    def test_missing_header_end_raises(self):
        with self.assertRaises(OSError):
            wifi._parse_response_chunks([b"HTTP/1.0 200 OK\r\nno-terminator"])

    def test_bad_status_code_raises(self):
        with self.assertRaises(OSError):
            wifi._parse_response_chunks([b"HTTP/1.0 ABC OK\r\n\r\n"])


if __name__ == "__main__":
    unittest.main()
