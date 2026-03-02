import json

result = []
with open("logs/errors.log", "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        try:
            obj = json.loads(line)
            exc = obj.get("exception", {}) or {}
            err = str(exc.get("message", ""))
            if "charmap" in err or "UnicodeEncodeError" in err:
                tb = exc.get("traceback", [])
                if isinstance(tb, list):
                    result.append("".join(tb))
                else:
                    result.append(str(tb))
        except Exception:
            pass

if result:
    print(result[-1][-3000:])
else:
    print("No charmap errors found in errors.log")
