# Debugger Commands

## Default command set

The bundled script runs these commands by default:

- `!analyze -v`
  - Full exception summary
- `.ecxr`
  - Switch to exception context
- `r`
  - Show registers
- `kb`
  - Show current thread stack with parameters
- `~*kb`
  - Show all thread stacks
- `lm`
  - Show loaded modules
- `q`
  - Quit debugger

## What to look for

- `ExceptionCode`
  - Example: `c0000005`
- `ExceptionAddress`
  - Actual fault location
- `PROCESS_NAME`
  - Which process crashed
- `FAULTING_THREAD`
  - Which thread died
- `STACK_TEXT`
  - Top stack frames, usually the fastest way to compare two crashes

## Usage example

```powershell
python scripts/analyze_dump.py --dump-path "F:\messiah_h74\Messiah\Engine\Binaries\Win64\xxx_mini.dmp"
```

With symbols:

```powershell
python scripts/analyze_dump.py --dump-path "F:\...\xxx_mini.dmp" --symbol-path "srv*C:\symbols*https://msdl.microsoft.com/download/symbols"
```
