"""Generated Apex topic: invasive_damage"""

from pathlib import Path
import json

def build():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from apex_assembler import assemble_topic
    from apex_enrich import finalize_script
    data = json.loads((Path(__file__).parent / 'invasive_damage.json').read_text(encoding='utf-8'))
    return finalize_script(assemble_topic(data))
