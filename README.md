# asmview

**English** | [简体中文](README.zh-CN.md)

`asmview` is a lightweight local web tool for converting between x86/x64 Intel assembly and machine code. It also helps visualize control flow, highlight bad characters, map stack frames, and encode strings.

The server listens only on `127.0.0.1`. It requires no frontend build step and does not send your input to any external service.

![asmview screenshot](docs/asmview.png)

## Features

- Supports x86-32 and x86-64.
- Converts assembly to machine code and machine code to assembly, with automatic input detection.
- Supports labels, common Intel instructions, and `.byte`, `.ascii`, `.asciz`, `.string`, and `db/dw/dd/dq` data directives.
- Draws branch arrows in disassembly listings, with distinct styles for calls, unconditional jumps, and conditional jumps.
- Highlights configurable bad characters; defaults to `00`, `0a`, and `0d`.
- Produces `.byte`, `db`, compact hex, `\\xNN`, and comma-separated output.
- Maps stack-frame fields to offsets and Intel memory operands, with copyable reports.
- Converts between text, `push imm32`, `mov [reg+off], imm32`, escaped hex, and byte arrays.
- Provides resizable panels and saves the layout in browser local storage.

## Requirements

- Python 3.9 or later
- Capstone
- Keystone Engine

## Installation

Using a virtual environment is recommended.

Windows PowerShell:

```powershell
git clone https://github.com/longbenx/asmview.git
cd asmview
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux/macOS:

```bash
git clone https://github.com/longbenx/asmview.git
cd asmview
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Running

```bash
python asmview.py
```

Then open `http://127.0.0.1:8765` in your browser. To use a different port:

```bash
python asmview.py --port 9000
```

## Usage

### Assembly to machine code

Select `x86-32` or `x86-64`, set `mode` to `asm -> bytes` (or keep `auto`), and enter assembly in the left pane:

```asm
start:
    xor eax, eax
    push eax
    jmp start
```

The right pane updates live with addresses, machine code, branch arrows, and disassembly. Several byte formats are included at the bottom. Use `copy .byte` to copy the `.byte` line.

Instructions and data directives can be mixed:

```asm
xor eax, eax
.string "cmd.exe"
.byte 0x90, 0xcc
```

### Machine code to assembly

Set `mode` to `bytes -> asm`, or paste any supported format while using `auto`:

```text
31 c0 50 c3
31c050c3
\x31\xc0\x50\xc3
0x31, 0xc0, 0x50, 0xc3
.byte 0x31, 0xc0, 0x50, 0xc3
```

Use `base` to set the listing origin, such as `0x401000`. Use `bad` to configure highlighted bytes, such as `00,0a,0d,20`.

### Stack-frame tool

Click `frame` to open the stack-frame panel. Each line uses the format `size name notes`. A blank line, the base-register name, or `pivot` marks the frame-pointer position:

```text
4 ret  saved EIP
4 arg0 first argument
ebp
4 tmp  scratch space
8 info structure
```

The panel generates offsets relative to `ebp`, `rbp`, or a custom register, together with matching Intel memory operands. Use `copy report` to copy a Markdown report.

### String tool

Click `string` and enter plain text or paste existing `push`, `mov`, or byte-array code. The tool generates:

- Little-endian `push imm32` instructions.
- `mov dword ptr [...]` instructions using the selected register and offset.
- Decimal and hexadecimal byte arrays.
- `\\xNN` escapes and space-separated hexadecimal bytes.

The `nul` option appends a null byte to plain strings. `reg` and `off` control the generated `mov` destination.

## Command-line options

```text
usage: asmview.py [-h] [--port PORT]

options:
  -h, --help   show help
  --port PORT  local HTTP port (default: 8765)
```

## Tests

After installing the dependencies, run the built-in smoke tests:

```bash
python -m unittest discover -s tests -v
```

## Notes

- Only x86-32 and x86-64 are currently supported; ARM is not supported.
- Assembly syntax follows the Intel syntax supported by Keystone.
- The browser page has no authentication. Do not expose the server to a public interface without adding appropriate protection.
