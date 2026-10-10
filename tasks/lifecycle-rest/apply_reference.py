"""Apply the committed reference solution to a disposable snapshot only."""

import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
source = Path(__file__).parent / "reference/src/api/routes/context_lifecycle.py"
shutil.copy2(source, root / "src/api/routes/context_lifecycle.py")
p = root / "src/api/router.py"
s = p.read_text().replace(
    "from src.api.routes.context_edges import router as context_edges_router",
    "from src.api.routes.context_edges import router as context_edges_router\nfrom src.api.routes.context_lifecycle import router as context_lifecycle_router",
)
s = s.replace(
    "    context_edges_router,",
    "    context_edges_router,\n    context_lifecycle_router,",
)
p.write_text(s)
p = root / "surface_contract.json"
d = json.loads(p.read_text())
r = d["capabilities"]["context.lifecycle"]
r["rest"] = "POST /projects/{name}/contexts/{topic}/lifecycle"
r["waived"].pop("rest", None)
p.write_text(json.dumps(d, indent=2) + "\n")
