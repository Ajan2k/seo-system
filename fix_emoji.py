"""Strip all non-ASCII characters from print() statements in search_trends.py."""
import re

path = r"app\utils\search_trends.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace all emoji/unicode in print() string literals with ASCII equivalents
def ascii_safe(text: str) -> str:
    return text.encode("ascii", errors="replace").decode("ascii")

# Handle f-string prints: print(f"...emoji...")
content = re.sub(
    r'(print\(f")([^"]*?)(")',
    lambda m: m.group(1) + ascii_safe(m.group(2)) + m.group(3),
    content,
)
# Handle plain string prints: print("...emoji...")
content = re.sub(
    r'(print\(")([^"]*?)(")',
    lambda m: m.group(1) + ascii_safe(m.group(2)) + m.group(3),
    content,
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# Verify no non-ASCII remains in print() calls
remaining = re.findall(r'print\([^)]*[^\x00-\x7F][^)]*\)', content)
if remaining:
    print(f"WARNING - still has non-ASCII in {len(remaining)} print() calls:")
    for r in remaining[:5]:
        print(f"  {r[:80]}")
else:
    print("OK - all print() statements are now ASCII-safe")
