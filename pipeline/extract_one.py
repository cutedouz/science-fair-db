"""單獨處理一份 PDF（給 extract_fulltext 的補跑用），結果以 JSON 印到 stdout。"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_fulltext import work
sid, secs, status = work((int(sys.argv[1]), sys.argv[2]))
print(json.dumps({'sid': sid, 'secs': secs, 'status': status}, ensure_ascii=False))
