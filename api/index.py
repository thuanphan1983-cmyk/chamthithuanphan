import sys
import os

# Thêm thư mục gốc vào PYTHONPATH để Vercel có thể import main
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from main import app
