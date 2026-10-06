# Python stdlib semantics a Rust port gets wrong (and how to prove them)

Recipe for any stdlib routine the reference leans on (number parsing, datetime, path resolution): port from the pinned CPython source, generate tables from the reference interpreter, prove with a seeded-mutation golden through the REAL function. Fetch source with `curl -sf https://raw.githubusercontent.com/python/cpython/v<X.Y.Z>/<path>` for the interpreter's exact patch version (`python3 --version`) — production runs the C implementation, not a pure-Python twin. When the golden disagrees with your reading, read the cited C function line by line before changing either side.

## int(str) / float(str)

Pipeline, in order (`Objects/unicodeobject.c::_PyUnicode_TransformDecimalAndSpaceToASCII`, `Python/pystrtod.c::_Py_string_to_number_with_underscores`, `Objects/floatobject.c`, `Objects/longobject.c`):

1. A non-ASCII string is rewritten char by char: code points < 127 pass through; Unicode whitespace becomes `' '`; Unicode decimal digits (category Nd) become ASCII digits; any other code point becomes `'?'` and the REST OF THE STRING IS DROPPED, so the parse then fails. An all-ASCII string is untouched.
2. The whitespace trimmed afterwards is the C-locale ASCII set (space, `\t \n \v \f \r`) — NOT `str.isspace()`: U+001C..U+001F are Unicode spaces yet are never trimmed.
3. `_` is legal only between two digits (never leading, trailing or doubled). `float` strips them in a pre-pass; `int` validates in-parse. The pre-pass `strchr`/scan stops at the first NUL, and an embedded NUL is an error whether or not an underscore is present — "truncate at the NUL" is wrong.
4. `int`: `[+-]?digits` only (no `0x`, no `1e3`; `int("3.5")` raises ValueError). Python ints are unbounded — port as `i128` and make a beyond-i128 result a distinct LOUD error, never a wrapped number. `float`: decimal/exponent forms plus `inf`, `infinity`, `nan` in any case with an optional sign.
5. Non-string inputs: `bool` coerces (1/0); `None`, list and dict raise TypeError; `int(float)` truncates toward zero, `int(nan)` is ValueError, `int(inf)` is OverflowError.
6. The Nd table comes from the REFERENCE interpreter (`unicodedata.decimal`): a generator script emits the sorted list of 10-wide run starts (assert the set really is a union of aligned 10-runs) and the port binary-searches it. Rust's Unicode version differs and `char::is_numeric` is the wrong set.

## os.path.realpath / Path.resolve

Port `Lib/posixpath.py` (`_joinrealpath`, `abspath`, `normpath`, `split`, `join`) and read the pinned `Lib/pathlib.py::resolve` for what it adds on top.

- `..` pops the last component of the path accumulated so far (symlinks already substituted into it), never the literal text; a walker that keeps `..` or canonicalises first diverges. `h1/../h3` is `h3` even when `h1` does not exist.
- A symlink loop returns the resolved prefix plus the untouched remainder (non-strict).
- A leading `//` collapses: realpath output never starts with two slashes, although `normpath` keeps exactly two.
- Relative inputs and relative link targets are `lstat`ed against the process cwd — a fake filesystem in a unit test must resolve against its fake cwd the same way.

## Path as a key

`Path` equality, hashing and `dict.fromkeys(Path(x) ...)` normalise: empty and `.` components dropped, repeated slashes collapsed, exactly two leading slashes kept as a distinct root (three or more collapse to one), `..` kept, the empty path is `.`. Group and dedupe keys must use the same normalisation, and the value that flows onward is the normalised path (a probe sees `rel`, not `./rel`).

## Golden recipe for a stdlib parser

- Corpus: hand-picked edges plus thousands of seeded (fixed `random.Random`) replace/insert/delete mutations of valid bases over a hostile alphabet — signs, exponent chars, `_`, ASCII and Unicode whitespace (U+001C..1F, U+0085, U+00A0, U+2003, U+3000), digits from several Nd blocks, non-Nd lookalikes (`²`, `①`), NUL, DEL, the letters of `inf`/`nan`, `İ ı ſ`. De-duplicate; keep the seed in the generator.
- Encode results canonically: ints as decimal text or the exception CLASS NAME; floats as 16 hex chars of the big-endian IEEE-754 bits, `nan` as a literal; a `BIG` bucket for values beyond the port's integer width. Compare exactly — no tolerance.
- A first-run diff here is a finding about your reading of the C, not noise.
- Filesystem-dependent routines (stat stamps, realpath): real files and symlinks in a per-scenario scratch dir, mtimes pinned with `os.utime(ns=...)`, the root replaced by a token in recorded output; the Rust side stats through an injectable `Fs` seam.
