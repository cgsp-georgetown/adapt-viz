
import sys
from pathlib import Path
# Adds the parent directory to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))


from dashboard_lib import data

# national_df, long_df, cbp_df, tradserv_df = load_data()
# grad_df = load_grad_data()

national_df, long_df, cbp_df, tradserv_df = data.load_data()
grad_df = data.load_grad_data()

