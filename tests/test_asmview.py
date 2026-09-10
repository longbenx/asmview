import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import asmview


class ConversionTests(unittest.TestCase):
    def test_assemble_with_label(self):
        result = asmview.convert(
            "start:\n xor eax, eax\n jmp start",
            "x86-32",
            "asm",
            "0x401000",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["kind"], "asm")
        self.assertEqual(result["nbytes"], 4)
        self.assertIn("xor eax, eax", result["listing"])

    def test_disassemble_escaped_bytes(self):
        result = asmview.convert(
            r"\x31\xc0\xc3",
            "x86-64",
            "bytes",
            "0",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["kind"], "bytes")
        self.assertEqual(result["nbytes"], 3)
        self.assertIn("xor eax, eax", result["listing"])

    def test_string_directive(self):
        result = asmview.convert(
            '.string "cmd.exe"',
            "x86-32",
            "asm",
            "0",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["nbytes"], 8)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), asmview.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_home_page(self):
        with urlopen(self.base_url + "/", timeout=2) as response:
            page = response.read().decode("utf-8")

        self.assertEqual(response.status, 200)
        self.assertIn("<strong>asmview</strong>", page)

    def test_asm_api(self):
        payload = json.dumps(
            {
                "src": "xor eax, eax",
                "arch": "x86-32",
                "mode": "asm",
                "base": "0",
                "bad": "00,0a,0d",
            }
        ).encode("utf-8")
        request = Request(
            self.base_url + "/asm",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=2) as response:
            result = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertIsNone(result["error"])
        self.assertEqual(result["nbytes"], 2)


if __name__ == "__main__":
    unittest.main()
